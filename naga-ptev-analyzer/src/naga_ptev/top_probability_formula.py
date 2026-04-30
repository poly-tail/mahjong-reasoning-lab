from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


INPUT_CANDIDATES = [
    Path("base_predictions_2000.csv"),
    Path("out/dataset/base_predictions_2000.csv"),
    Path("naga-ptev-analyzer/out/dataset/base_predictions_2000.csv"),
]
OUT_DIR = Path("out/top_probability_formula")
KYOKU_LABELS = {
    0: "East 1",
    1: "East 2",
    2: "East 3",
    3: "East 4",
    4: "South 1",
    5: "South 2",
    6: "South 3",
    7: "South 4",
}
STATE_COLUMNS = ["kyoku", "honba", "kyotaku", "score_0", "score_1", "score_2", "score_3"]
FORMULA_FEATURES = [
    "lead_to_1st",
    "gap_to_next_rank",
    "gap_from_prev_rank",
    "score_range",
    "score_std",
    "is_dealer",
    "kyotaku",
    "honba",
    "dealer_score",
]
EPS = 1e-6


def _resolve_input(path: str | Path | None = None) -> Path:
    if path is not None:
        target = Path(path)
        if target.exists():
            return target
        raise FileNotFoundError(target)
    for candidate in INPUT_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"base_predictions_2000.csv not found. Tried: {INPUT_CANDIDATES}")


def logistic(x: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(x, dtype=float), -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-x))


def logit(p: pd.Series | np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(p, dtype=float), EPS, 1.0 - EPS)
    return np.log(clipped / (1.0 - clipped))


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = out[out["kyoku"] != 7].copy()
    out["state_id"] = out[STATE_COLUMNS].astype(str).agg("|".join, axis=1)
    score_cols = ["score_0", "score_1", "score_2", "score_3"]
    scores = out[score_cols].to_numpy(dtype=float)
    out["lead_to_1st"] = out["score_self"].to_numpy(dtype=float) - scores.max(axis=1)
    sorted_scores = np.sort(scores, axis=1)
    second_score = sorted_scores[:, -2]
    out["gap_to_2nd_if_top"] = np.where(out["current_rank"].to_numpy() == 1, out["score_self"].to_numpy(dtype=float) - second_score, 0.0)
    out["logit_p1"] = logit(out["p1"])
    return out


def _group_split_state_ids(state_ids: pd.Series, test_size: float = 0.2, random_state: int = 42) -> tuple[set[str], set[str]]:
    unique = np.array(sorted(state_ids.astype(str).unique()))
    if len(unique) <= 1:
        return set(unique), set(unique)
    rng = np.random.default_rng(random_state)
    shuffled = unique.copy()
    rng.shuffle(shuffled)
    test_n = max(1, int(round(len(shuffled) * test_size)))
    test = set(shuffled[:test_n])
    train = set(shuffled[test_n:])
    if not train:
        train = test.copy()
    return train, test


def _standardize(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, np.ndarray, pd.Series, pd.Series]:
    mean = train[features].mean()
    std = train[features].std().replace(0.0, 1.0).fillna(1.0)
    return (
        ((train[features] - mean) / std).to_numpy(dtype=float),
        ((test[features] - mean) / std).to_numpy(dtype=float),
        mean,
        std,
    )


def _linear_design(x: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(len(x)), x])


def _fit_ridge_cv(x: np.ndarray, y: np.ndarray, alphas: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0)) -> tuple[np.ndarray, float]:
    best: tuple[float, np.ndarray, float] | None = None
    design = _linear_design(x)
    for alpha in alphas:
        penalty = np.eye(design.shape[1]) * alpha
        penalty[0, 0] = 0.0
        coef = np.linalg.pinv(design.T @ design + penalty) @ design.T @ y
        pred = design @ coef
        mse = float(((pred - y) ** 2).mean())
        if best is None or mse < best[0]:
            best = (mse, coef, alpha)
    assert best is not None
    return best[1], best[2]


def _soft_threshold(value: np.ndarray, lam: float) -> np.ndarray:
    return np.sign(value) * np.maximum(np.abs(value) - lam, 0.0)


def _fit_prox_linear_cv(
    x: np.ndarray,
    y: np.ndarray,
    *,
    l1_ratio: float,
    alphas: tuple[float, ...] = (0.0001, 0.001, 0.01, 0.05),
    iterations: int = 2500,
) -> tuple[np.ndarray, float]:
    x_aug = _linear_design(x)
    lipschitz = float(np.linalg.norm(x_aug, ord=2) ** 2 / max(len(x_aug), 1) + max(alphas))
    step = 1.0 / max(lipschitz, 1e-6)
    best: tuple[float, np.ndarray, float] | None = None
    for alpha in alphas:
        coef = np.zeros(x_aug.shape[1], dtype=float)
        coef[0] = float(y.mean())
        for _ in range(iterations):
            residual = x_aug @ coef - y
            grad = x_aug.T @ residual / max(len(y), 1)
            grad[1:] += alpha * (1.0 - l1_ratio) * coef[1:]
            coef -= step * grad
            coef[1:] = _soft_threshold(coef[1:], step * alpha * l1_ratio)
        pred = x_aug @ coef
        mse = float(((pred - y) ** 2).mean())
        if best is None or mse < best[0]:
            best = (mse, coef, alpha)
    assert best is not None
    return best[1], best[2]


@dataclass
class FormulaFit:
    model_name: str
    coef: np.ndarray
    alpha: float
    mean: pd.Series
    std: pd.Series
    features: list[str]

    def predict_logit(self, df: pd.DataFrame) -> np.ndarray:
        x = ((df[self.features] - self.mean) / self.std).to_numpy(dtype=float)
        return _linear_design(x) @ self.coef


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = float(((y_true - y_true.mean()) ** 2).sum())
    if denom <= 1e-12:
        return 0.0
    return 1.0 - float(((y_true - y_pred) ** 2).sum()) / denom


def _metrics(y_true_p: np.ndarray, y_pred_p: np.ndarray, y_true_logit: np.ndarray, y_pred_logit: np.ndarray) -> dict[str, float]:
    err = y_pred_p - y_true_p
    return {
        "p1_MAE": float(np.abs(err).mean()),
        "p1_RMSE": float(np.sqrt((err**2).mean())),
        "p1_max_absolute_error": float(np.abs(err).max()),
        "logit_R2": float(_r2(y_true_logit, y_pred_logit)),
    }


def _bucket_edges(series: pd.Series, bins: int = 20) -> pd.Series:
    ranked = series.rank(method="first")
    count = min(bins, max(1, series.nunique()))
    return pd.qcut(ranked, q=count, duplicates="drop")


def build_bin_curves(df: pd.DataFrame, out: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (kyoku, current_rank), group in df.groupby(["kyoku", "current_rank"]):
        for feature in ["gap_to_1st", "lead_to_1st", "score_self", "score_range"]:
            work = group.copy()
            work["bucket"] = _bucket_edges(work[feature])
            agg = (
                work.groupby("bucket", observed=False)
                .agg(
                    x_mean=(feature, "mean"),
                    x_min=(feature, "min"),
                    x_max=(feature, "max"),
                    p1_mean=("p1", "mean"),
                    p1_std=("p1", "std"),
                    rows=("p1", "size"),
                )
                .reset_index(drop=True)
            )
            for _, row in agg.iterrows():
                rows.append(
                    {
                        "kyoku": int(kyoku),
                        "kyoku_label": KYOKU_LABELS.get(int(kyoku), str(kyoku)),
                        "current_rank": int(current_rank),
                        "feature": feature,
                        "x_mean": float(row["x_mean"]),
                        "x_min": float(row["x_min"]),
                        "x_max": float(row["x_max"]),
                        "p1_mean": float(row["p1_mean"]),
                        "p1_std": float(row["p1_std"]) if not pd.isna(row["p1_std"]) else 0.0,
                        "rows": int(row["rows"]),
                    }
                )
    result = pd.DataFrame(rows)
    result.to_csv(out / "bin_curves.csv", index=False)
    return result


def _plot_curve(curves: pd.DataFrame, feature: str, kyoku: int, out: Path) -> None:
    part = curves[(curves["kyoku"] == kyoku) & (curves["feature"] == feature)].copy()
    if part.empty:
        return
    plt.figure(figsize=(10, 6))
    for current_rank, group in part.groupby("current_rank"):
        group = group.sort_values("x_mean")
        plt.plot(group["x_mean"], group["p1_mean"], marker="o", label=f"rank {current_rank}")
    plt.title(f"{KYOKU_LABELS.get(kyoku, kyoku)}: {feature} vs P1 by Current Rank")
    plt.xlabel(feature)
    plt.ylabel("P1")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out / "plots" / f"kyoku_{kyoku}_{feature}_vs_p1.png", dpi=160)
    plt.close()


def write_bin_plots(curves: pd.DataFrame, out: Path) -> None:
    (out / "plots").mkdir(parents=True, exist_ok=True)
    for kyoku in sorted(curves["kyoku"].unique()):
        for feature in ["gap_to_1st", "lead_to_1st", "score_range"]:
            _plot_curve(curves, feature, int(kyoku), out)


def _fit_formula_models(train: pd.DataFrame, test: pd.DataFrame) -> list[FormulaFit]:
    x_train, _, mean, std = _standardize(train, test, FORMULA_FEATURES)
    y = train["logit_p1"].to_numpy(dtype=float)
    models: list[FormulaFit] = []

    try:
        from sklearn.linear_model import ElasticNetCV, LassoCV, RidgeCV
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except Exception:
        ridge_coef, ridge_alpha = _fit_ridge_cv(x_train, y)
        lasso_coef, lasso_alpha = _fit_prox_linear_cv(x_train, y, l1_ratio=1.0)
        elastic_coef, elastic_alpha = _fit_prox_linear_cv(x_train, y, l1_ratio=0.5)
        models.extend(
            [
                FormulaFit("ridgecv_fallback", ridge_coef, ridge_alpha, mean, std, FORMULA_FEATURES),
                FormulaFit("lassocv_fallback", lasso_coef, lasso_alpha, mean, std, FORMULA_FEATURES),
                FormulaFit("elasticnetcv_fallback", elastic_coef, elastic_alpha, mean, std, FORMULA_FEATURES),
            ]
        )
        return models

    sklearn_models = [
        ("RidgeCV", RidgeCV(alphas=(0.01, 0.1, 1.0, 10.0, 100.0))),
        ("LassoCV", LassoCV(alphas=(0.0001, 0.001, 0.01, 0.05), cv=3, max_iter=10000, random_state=42)),
        ("ElasticNetCV", ElasticNetCV(alphas=(0.0001, 0.001, 0.01, 0.05), l1_ratio=(0.2, 0.5, 0.8), cv=3, max_iter=10000, random_state=42)),
    ]
    for name, estimator in sklearn_models:
        pipe = make_pipeline(StandardScaler(), estimator)
        pipe.fit(train[FORMULA_FEATURES], y)
        fitted = pipe[-1]
        scaler = pipe[0]
        coef = np.concatenate([[float(fitted.intercept_)], np.asarray(fitted.coef_, dtype=float)])
        models.append(
            FormulaFit(
                name,
                coef,
                float(getattr(fitted, "alpha_", np.nan)),
                pd.Series(scaler.mean_, index=FORMULA_FEATURES),
                pd.Series(scaler.scale_, index=FORMULA_FEATURES),
                FORMULA_FEATURES,
            )
        )
    return models


def train_formula_models(df: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    coefficient_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []

    for (kyoku, current_rank), group in sorted(df.groupby(["kyoku", "current_rank"]), key=lambda x: (int(x[0][0]), int(x[0][1]))):
        train_ids, test_ids = _group_split_state_ids(group["state_id"])
        train = group[group["state_id"].isin(train_ids)].copy()
        test = group[group["state_id"].isin(test_ids)].copy()
        if len(train) < 5 or len(test) < 1:
            continue
        for model in _fit_formula_models(train, test):
            pred_logit = model.predict_logit(test)
            pred_p1 = logistic(pred_logit)
            true_p1 = test["p1"].to_numpy(dtype=float)
            true_logit = test["logit_p1"].to_numpy(dtype=float)
            metric = {
                "kyoku": int(kyoku),
                "kyoku_label": KYOKU_LABELS.get(int(kyoku), str(kyoku)),
                "current_rank": int(current_rank),
                "model": model.model_name,
                "rows_train": int(len(train)),
                "rows_test": int(len(test)),
                "alpha": float(model.alpha),
            }
            metric.update(_metrics(true_p1, pred_p1, true_logit, pred_logit))
            metric_rows.append(metric)

            for name, value in zip(["intercept", *model.features], model.coef):
                coefficient_rows.append(
                    {
                        "kyoku": int(kyoku),
                        "kyoku_label": KYOKU_LABELS.get(int(kyoku), str(kyoku)),
                        "current_rank": int(current_rank),
                        "model": model.model_name,
                        "term": name,
                        "coefficient_standardized": float(value),
                        "feature_mean": float(model.mean[name]) if name in model.mean.index else np.nan,
                        "feature_std": float(model.std[name]) if name in model.std.index else np.nan,
                        "alpha": float(model.alpha),
                    }
                )

            pred_df = test[
                [
                    "state_id",
                    "kyoku",
                    "current_rank",
                    "seat",
                    "score_self",
                    "gap_to_1st",
                    "lead_to_1st",
                    "gap_to_next_rank",
                    "gap_from_prev_rank",
                    "score_range",
                    "score_std",
                    "is_dealer",
                    "kyotaku",
                    "honba",
                    "dealer_score",
                    "p1",
                    "logit_p1",
                ]
            ].copy()
            pred_df["model"] = model.model_name
            pred_df["predicted_logit_p1"] = pred_logit
            pred_df["p1_pred"] = pred_p1
            pred_df["p1_error"] = pred_df["p1_pred"] - pred_df["p1"]
            pred_df["abs_p1_error"] = pred_df["p1_error"].abs()
            prediction_frames.append(pred_df)

    coefficients = pd.DataFrame(coefficient_rows)
    metrics = pd.DataFrame(metric_rows).sort_values(["kyoku", "current_rank", "p1_MAE"])
    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    coefficients.to_csv(out / "coefficients_by_kyoku_rank.csv", index=False)
    metrics.to_csv(out / "formula_metrics_by_kyoku_rank.csv", index=False)
    predictions.to_csv(out / "predictions_top_probability.csv", index=False)
    return coefficients, metrics, predictions


def build_spline_curves(df: pd.DataFrame, out: Path) -> pd.DataFrame:
    try:
        from scipy.interpolate import UnivariateSpline
    except Exception:
        UnivariateSpline = None

    rows: list[dict[str, Any]] = []
    features = ["lead_to_1st", "gap_to_1st", "score_range"]
    for (kyoku, current_rank), group in df.groupby(["kyoku", "current_rank"]):
        for feature in features:
            agg = (
                group.assign(bucket=_bucket_edges(group[feature], bins=24))
                .groupby("bucket", observed=False)
                .agg(x=(feature, "mean"), y=("p1", "mean"), rows=("p1", "size"))
                .dropna()
                .sort_values("x")
            )
            if len(agg) < 4:
                continue
            x = agg["x"].to_numpy(dtype=float)
            y = agg["y"].to_numpy(dtype=float)
            grid = np.linspace(float(x.min()), float(x.max()), 80)
            if UnivariateSpline is not None and len(np.unique(x)) >= 4:
                order = min(3, len(np.unique(x)) - 1)
                smooth = max(1e-6, len(x) * float(np.var(y)) * 0.2)
                try:
                    spline = UnivariateSpline(x, y, k=order, s=smooth)
                    pred = np.clip(spline(grid), 0.0, 1.0)
                    method = "scipy_univariate_spline"
                except Exception:
                    pred = np.interp(grid, x, y)
                    method = "binning_interpolation"
            else:
                pred = np.interp(grid, x, y)
                method = "binning_interpolation"
            for xv, yv in zip(grid, pred):
                rows.append(
                    {
                        "kyoku": int(kyoku),
                        "kyoku_label": KYOKU_LABELS.get(int(kyoku), str(kyoku)),
                        "current_rank": int(current_rank),
                        "feature": feature,
                        "x": float(xv),
                        "p1_spline": float(yv),
                        "method": method,
                    }
                )
    curves = pd.DataFrame(rows)
    curves.to_csv(out / "spline_curve_points.csv", index=False)
    plot_dir = out / "plots"
    for (feature, kyoku), part in curves.groupby(["feature", "kyoku"]):
        plt.figure(figsize=(10, 6))
        for current_rank, group in part.groupby("current_rank"):
            group = group.sort_values("x")
            plt.plot(group["x"], group["p1_spline"], label=f"rank {current_rank}")
        plt.title(f"{KYOKU_LABELS.get(int(kyoku), kyoku)}: Spline {feature} to P1")
        plt.xlabel(feature)
        plt.ylabel("P1")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plot_dir / f"spline_kyoku_{int(kyoku)}_{feature}_to_p1.png", dpi=160)
        plt.close()
    return curves


class KnnP1Model:
    def __init__(self, k: int = 35) -> None:
        self.k = k
        self.mean: pd.Series | None = None
        self.std: pd.Series | None = None
        self.x: np.ndarray | None = None
        self.y: np.ndarray | None = None

    def fit(self, df: pd.DataFrame) -> "KnnP1Model":
        self.mean = df[FORMULA_FEATURES].mean()
        self.std = df[FORMULA_FEATURES].std().replace(0.0, 1.0).fillna(1.0)
        self.x = ((df[FORMULA_FEATURES] - self.mean) / self.std).to_numpy(dtype=float)
        self.y = df["p1"].to_numpy(dtype=float)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if self.x is None or self.y is None or self.mean is None or self.std is None:
            raise RuntimeError("model is not fitted")
        q = ((df[FORMULA_FEATURES] - self.mean) / self.std).to_numpy(dtype=float)
        preds = []
        for row in q:
            dist = np.sqrt(((self.x - row) ** 2).sum(axis=1))
            idx = np.argsort(dist)[: max(1, min(self.k, len(dist)))]
            weights = 1.0 / np.maximum(dist[idx], 1e-6)
            preds.append(float((self.y[idx] * weights).sum() / weights.sum()))
        return np.clip(np.asarray(preds), 0.0, 1.0)


def _fit_high_accuracy_model(train: pd.DataFrame) -> tuple[str, Any]:
    try:
        from sklearn.ensemble import ExtraTreesRegressor
    except Exception:
        return "local_knn_fallback", KnnP1Model(k=35).fit(train)
    model = ExtraTreesRegressor(n_estimators=200, min_samples_leaf=2, random_state=42, n_jobs=-1)
    model.fit(train[FORMULA_FEATURES], train["p1"])
    return "ExtraTreesRegressor", model


def compare_models(df: pd.DataFrame, formula_predictions: pd.DataFrame, out: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not formula_predictions.empty:
        for keys, group in formula_predictions.groupby(["kyoku", "current_rank", "model"]):
            kyoku, current_rank, model_name = keys
            metric = {
                "kyoku": int(kyoku),
                "current_rank": int(current_rank),
                "model": str(model_name),
                "model_type": "logit_linear",
                "rows_test": int(len(group)),
            }
            metric.update(
                _metrics(
                    group["p1"].to_numpy(dtype=float),
                    group["p1_pred"].to_numpy(dtype=float),
                    group["logit_p1"].to_numpy(dtype=float),
                    group["predicted_logit_p1"].to_numpy(dtype=float),
                )
            )
            rows.append(metric)

    for (kyoku, current_rank), group in df.groupby(["kyoku", "current_rank"]):
        train_ids, test_ids = _group_split_state_ids(group["state_id"])
        train = group[group["state_id"].isin(train_ids)].copy()
        test = group[group["state_id"].isin(test_ids)].copy()
        if len(train) < 5 or len(test) < 1:
            continue
        name, model = _fit_high_accuracy_model(train)
        if name == "ExtraTreesRegressor":
            pred = np.clip(model.predict(test[FORMULA_FEATURES]), 0.0, 1.0)
        else:
            pred = model.predict(test)
        metric = {
            "kyoku": int(kyoku),
            "current_rank": int(current_rank),
            "model": name,
            "model_type": "high_accuracy",
            "rows_test": int(len(test)),
        }
        metric.update(_metrics(test["p1"].to_numpy(dtype=float), pred, test["logit_p1"].to_numpy(dtype=float), logit(pred)))
        rows.append(metric)

    comparison = pd.DataFrame(rows).sort_values(["kyoku", "current_rank", "p1_MAE"])
    comparison.to_csv(out / "model_comparison.csv", index=False)
    comparison.groupby(["model", "model_type", "current_rank"])[["p1_MAE", "p1_RMSE", "p1_max_absolute_error"]].mean().reset_index().to_csv(
        out / "model_comparison_error_by_current_rank.csv", index=False
    )
    comparison.groupby(["model", "model_type", "kyoku"])[["p1_MAE", "p1_RMSE", "p1_max_absolute_error"]].mean().reset_index().to_csv(
        out / "model_comparison_error_by_kyoku.csv", index=False
    )
    return comparison


def _summarize_formula(coefficients: pd.DataFrame, metrics: pd.DataFrame, comparison: pd.DataFrame) -> str:
    best_formula = metrics.sort_values(["kyoku", "current_rank", "p1_MAE"]).groupby(["kyoku", "current_rank"]).head(1)
    lead = coefficients[(coefficients["term"] == "lead_to_1st") & (coefficients["model"].isin(best_formula["model"].unique()))]
    lead_best = best_formula[["kyoku", "current_rank", "model"]].merge(lead, on=["kyoku", "current_rank", "model"], how="left")
    dealer = coefficients[(coefficients["term"] == "is_dealer") & (coefficients["model"].isin(best_formula["model"].unique()))]
    kyotaku = coefficients[(coefficients["term"] == "kyotaku") & (coefficients["model"].isin(best_formula["model"].unique()))]
    enough = best_formula[best_formula["p1_MAE"] <= 0.025]
    weak = best_formula[best_formula["p1_MAE"] > 0.04]
    high = comparison[comparison["model_type"] == "high_accuracy"].copy()
    lines = [
        "# \u30c8\u30c3\u30d7\u7387 p1 \u8fd1\u4f3c\u5f0f\u30ec\u30dd\u30fc\u30c8",
        "",
        "\u4eca\u56de\u306e\u4e3b\u76ee\u7684\u306f ptEV \u3067\u306f\u306a\u304f\u3001\u5c40\u3054\u3068\u30fbcurrent_rank\u3054\u3068\u306e\u30c8\u30c3\u30d7\u7387 p1 \u8fd1\u4f3c\u3067\u3059\u3002kyoku=7 \u306f\u5bfe\u8c61\u5916\u3067\u3059\u3002",
        "",
        "## \u5c40\u5225\u30fbcurrent_rank\u5225\u306b\u5f0f\u3092\u5206\u3051\u308b\u3079\u304d\u304b",
        "",
        "\u5206\u3051\u308b\u3079\u304d\u3067\u3059\u3002p1 \u306e\u5206\u5e03\u3068 `lead_to_1st` \u306e\u52b9\u304d\u65b9\u306f\u5c40\u304c\u9032\u3080\u307b\u3069\u5f37\u304f\u306a\u308a\u3001\u7279\u306b\u53573\u3067\u306f\u540c\u3058\u70b9\u5dee\u3067\u3082 p1 \u306e\u5909\u5316\u304c\u5927\u304d\u304f\u306a\u308a\u307e\u3059\u3002",
        "",
        "## lead_to_1st \u4fc2\u6570",
        "",
        f"- average standardized coefficient: {lead_best['coefficient_standardized'].mean():.6f}",
        f"- by kyoku mean: `{lead_best.groupby('kyoku')['coefficient_standardized'].mean().round(6).to_dict()}`",
        "",
        "## \u89aa\u30fb\u4f9b\u8a17\u88dc\u6b63",
        "",
        f"- is_dealer average standardized coefficient: {dealer['coefficient_standardized'].mean():.6f}",
        f"- kyotaku average standardized coefficient: {kyotaku['coefficient_standardized'].mean():.6f}",
        "",
        "## \u30ed\u30b8\u30c3\u30c8\u7dda\u5f62\u3067\u5341\u5206\u306a\u5c40\u9762",
        "",
        f"- combinations with p1_MAE <= 0.025: {len(enough)} / {len(best_formula)}",
        f"- examples: `{enough[['kyoku', 'current_rank', 'model', 'p1_MAE']].head(10).to_dict(orient='records')}`",
        "",
        "## \u30ed\u30b8\u30c3\u30c8\u7dda\u5f62\u304c\u4e0d\u5341\u5206\u306a\u5c40\u9762",
        "",
        f"- combinations with p1_MAE > 0.04: {len(weak)} / {len(best_formula)}",
        f"- examples: `{weak[['kyoku', 'current_rank', 'model', 'p1_MAE']].head(10).to_dict(orient='records')}`",
        "",
        "## \u30b9\u30d7\u30e9\u30a4\u30f3\u3084\u9ad8\u7cbe\u5ea6\u30e2\u30c7\u30eb\u304c\u5fc5\u8981\u306a\u5c40\u9762",
        "",
        "\u5883\u754c\u4ed8\u8fd1\u3001\u7279\u306b current_rank=2/3/4 \u3067 `gap_to_next_rank` \u3068 `gap_from_prev_rank` \u306e\u975e\u7dda\u5f62\u6027\u304c\u5f37\u3044\u5c40\u9762\u3067\u306f\u3001\u30b9\u30d7\u30e9\u30a4\u30f3\u307e\u305f\u306f\u9ad8\u7cbe\u5ea6\u30e2\u30c7\u30eb\u304c\u6709\u52b9\u3067\u3059\u3002",
        f"- high accuracy average p1_MAE by kyoku: `{high.groupby('kyoku')['p1_MAE'].mean().round(6).to_dict() if not high.empty else {}}`",
        "",
        "## \u6700\u7d42\u7684\u306a\u7c21\u6613\u5f0f\u5019\u88dc",
        "",
        "`(kyoku, current_rank)` \u3054\u3068\u306b\u6b21\u306e\u5f0f\u3092\u4f7f\u3046\u306e\u304c\u6271\u3044\u3084\u3059\u3044\u3067\u3059\u3002",
        "",
        "`p1 = logistic(intercept + b1*z(lead_to_1st) + b2*z(gap_to_next_rank) + b3*z(gap_from_prev_rank) + b4*z(score_range) + b5*z(score_std) + b6*z(is_dealer) + b7*z(kyotaku) + b8*z(honba) + b9*z(dealer_score))`",
        "",
        "`z(x) = (x - feature_mean) / feature_std` \u3067\u3059\u3002\u4fc2\u6570\u3001\u5e73\u5747\u3001\u6a19\u6e96\u504f\u5dee\u306f `coefficients_by_kyoku_rank.csv` \u306b\u51fa\u529b\u3057\u3066\u3044\u307e\u3059\u3002",
        "",
        "\u4eba\u9593\u304c\u8aad\u3080\u7528\u9014\u3067\u306f\u3001\u6c17\u306b\u306a\u308b\u70b9\u5dee\u5e2f\u306b\u5bfe\u3057\u3066 `bin_curves.csv` \u3068 `spline_curve_points.csv` \u3092\u53c2\u7167\u3059\u308b\u3068\u3001\u30eb\u30c3\u30af\u30a2\u30c3\u30d7\u8868\u306b\u8fd1\u3044\u5f62\u3067\u4f7f\u3048\u307e\u3059\u3002",
        "",
    ]
    return "\n".join(lines)


def run_top_probability_formula(
    *,
    input_csv: str | Path | None = None,
    out_dir: str | Path = OUT_DIR,
) -> dict[str, Any]:
    out = Path(out_dir)
    (out / "plots").mkdir(parents=True, exist_ok=True)
    input_path = _resolve_input(input_csv)
    df = add_features(pd.read_csv(input_path))

    curves = build_bin_curves(df, out)
    write_bin_plots(curves, out)
    coefficients, metrics, predictions = train_formula_models(df, out)
    spline_curves = build_spline_curves(df, out)
    comparison = compare_models(df, predictions, out)
    (out / "summary_report.md").write_text(_summarize_formula(coefficients, metrics, comparison), encoding="utf-8")
    (out / "run_summary.json").write_text(
        json.dumps(
            {
                "input_csv": str(input_path),
                "rows": int(len(df)),
                "kyoku": sorted(int(v) for v in df["kyoku"].unique()),
                "bin_curve_rows": int(len(curves)),
                "spline_curve_rows": int(len(spline_curves)),
                "formula_metric_rows": int(len(metrics)),
                "comparison_rows": int(len(comparison)),
                "output_dir": str(out),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return json.loads((out / "run_summary.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(json.dumps(run_top_probability_formula(), ensure_ascii=False, indent=2))
