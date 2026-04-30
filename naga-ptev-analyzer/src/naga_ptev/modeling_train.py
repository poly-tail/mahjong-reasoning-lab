from __future__ import annotations

import itertools
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from naga_ptev.modeling_dataset import FEATURE_COLUMNS, TARGET_COLUMNS, normalize_probabilities, ptev_from_probs


CATEGORICAL_COLUMNS = ["seat", "current_rank", "is_dealer"]
NUMERIC_COLUMNS = [column for column in FEATURE_COLUMNS if column not in CATEGORICAL_COLUMNS]


class TabularPreprocessor:
    def __init__(self, *, one_hot: bool) -> None:
        self.one_hot = bool(one_hot)
        self.numeric_mean: pd.Series | None = None
        self.numeric_std: pd.Series | None = None
        self.category_values: dict[str, list[int]] = {}
        self.columns_: list[str] = []

    def fit(self, df: pd.DataFrame) -> "TabularPreprocessor":
        self.numeric_mean = df[NUMERIC_COLUMNS].mean()
        self.numeric_std = df[NUMERIC_COLUMNS].std().replace(0, 1.0).fillna(1.0)
        if self.one_hot:
            self.category_values = {
                column: sorted(int(value) for value in df[column].dropna().unique())
                for column in CATEGORICAL_COLUMNS
            }
        transformed = self.transform(df)
        self.columns_ = list(transformed.columns)
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.numeric_mean is None or self.numeric_std is None:
            raise RuntimeError("preprocessor is not fitted")
        numeric = (df[NUMERIC_COLUMNS] - self.numeric_mean) / self.numeric_std
        pieces = [numeric.reset_index(drop=True)]
        if self.one_hot:
            for column in CATEGORICAL_COLUMNS:
                values = self.category_values.get(column, [])
                for value in values:
                    pieces.append((df[column].astype(int).reset_index(drop=True) == value).astype(float).to_frame(f"{column}_{value}"))
        else:
            pieces.append(df[CATEGORICAL_COLUMNS].astype(float).reset_index(drop=True))
        return pd.concat(pieces, axis=1)


class NumpyRidgeMulti:
    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = float(alpha)
        self.coef_: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "NumpyRidgeMulti":
        design = np.column_stack([np.ones(len(x)), np.asarray(x, dtype=float)])
        penalty = np.eye(design.shape[1]) * self.alpha
        penalty[0, 0] = 0.0
        self.coef_ = np.linalg.pinv(design.T @ design + penalty) @ design.T @ np.asarray(y, dtype=float)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("model is not fitted")
        design = np.column_stack([np.ones(len(x)), np.asarray(x, dtype=float)])
        return design @ self.coef_


class KNNRegressor:
    def __init__(self, k: int = 35) -> None:
        self.k = int(k)
        self.x: np.ndarray | None = None
        self.y: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "KNNRegressor":
        self.x = np.asarray(x, dtype=float)
        self.y = np.asarray(y, dtype=float)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self.x is None or self.y is None:
            raise RuntimeError("model is not fitted")
        query = np.asarray(x, dtype=float)
        preds = []
        for row in query:
            distances = np.sqrt(((self.x - row) ** 2).sum(axis=1))
            idx = np.argsort(distances)[: max(1, min(self.k, len(distances)))]
            weights = 1.0 / np.maximum(distances[idx], 1e-6)
            preds.append((self.y[idx] * weights[:, None]).sum(axis=0) / weights.sum())
        return np.vstack(preds)


class BucketMeanRegressor:
    def __init__(self) -> None:
        self.global_mean: np.ndarray | None = None
        self.lookup: dict[tuple[int, int, int, int], np.ndarray] = {}
        self.rank_lookup: dict[int, np.ndarray] = {}

    def fit(self, df: pd.DataFrame, y: np.ndarray) -> "BucketMeanRegressor":
        target = pd.DataFrame(y, columns=TARGET_COLUMNS)
        train = pd.concat([df.drop(columns=TARGET_COLUMNS, errors="ignore").reset_index(drop=True), target], axis=1)
        self.global_mean = target.mean().to_numpy(dtype=float)
        for key, group in train.groupby(["current_rank", "seat", "honba", "kyotaku"]):
            self.lookup[tuple(int(v) for v in key)] = group[TARGET_COLUMNS].mean().to_numpy(dtype=float)
        for key, group in train.groupby("current_rank"):
            self.rank_lookup[int(key)] = group[TARGET_COLUMNS].mean().to_numpy(dtype=float)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if self.global_mean is None:
            raise RuntimeError("model is not fitted")
        preds = []
        for _, row in df.iterrows():
            key = (int(row["current_rank"]), int(row["seat"]), int(row["honba"]), int(row["kyotaku"]))
            pred = self.lookup.get(key)
            if pred is None:
                pred = self.rank_lookup.get(int(row["current_rank"]), self.global_mean)
            preds.append(pred)
        return np.vstack(preds)


class SurrogateModel:
    def __init__(self, name: str, estimator: Any, preprocessor: TabularPreprocessor | None, uses_raw_df: bool = False) -> None:
        self.name = str(name)
        self.estimator = estimator
        self.preprocessor = preprocessor
        self.uses_raw_df = bool(uses_raw_df)

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if self.uses_raw_df:
            raw = self.estimator.predict(df)
        else:
            if self.preprocessor is None:
                raise RuntimeError("preprocessor is missing")
            raw = self.estimator.predict(self.preprocessor.transform(df).to_numpy(dtype=float))
        return normalize_probabilities(np.asarray(raw, dtype=float))


def _fit_ridge(train_df: pd.DataFrame) -> SurrogateModel:
    pre = TabularPreprocessor(one_hot=True).fit(train_df)
    est = NumpyRidgeMulti(alpha=1.0).fit(
        pre.transform(train_df).to_numpy(dtype=float),
        train_df[TARGET_COLUMNS].to_numpy(dtype=float),
    )
    return SurrogateModel("ridge_baseline", est, pre)


def _fit_knn(train_df: pd.DataFrame) -> SurrogateModel:
    pre = TabularPreprocessor(one_hot=False).fit(train_df)
    est = KNNRegressor(k=35).fit(
        pre.transform(train_df).to_numpy(dtype=float),
        train_df[TARGET_COLUMNS].to_numpy(dtype=float),
    )
    return SurrogateModel("local_knn_fallback", est, pre)


def _fit_bucket_mean(train_df: pd.DataFrame) -> SurrogateModel:
    est = BucketMeanRegressor().fit(train_df, train_df[TARGET_COLUMNS].to_numpy(dtype=float))
    return SurrogateModel("rank_bucket_mean_fallback", est, None, uses_raw_df=True)


def _fit_sklearn_models_if_available(train_df: pd.DataFrame) -> list[SurrogateModel]:
    models: list[SurrogateModel] = []
    try:
        from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
        from sklearn.multioutput import MultiOutputRegressor
    except Exception:
        return models

    pre = TabularPreprocessor(one_hot=False).fit(train_df)
    x = pre.transform(train_df).to_numpy(dtype=float)
    y = train_df[TARGET_COLUMNS].to_numpy(dtype=float)
    best_hist: tuple[float, Any, str] | None = None
    for max_iter, learning_rate, max_leaf_nodes in itertools.product((100, 200), (0.03, 0.06), (15, 31)):
        est = MultiOutputRegressor(
            HistGradientBoostingRegressor(
                max_iter=max_iter,
                learning_rate=learning_rate,
                max_leaf_nodes=max_leaf_nodes,
                random_state=42,
            )
        )
        est.fit(x, y)
        pred = normalize_probabilities(est.predict(x))
        score = float(np.abs(pred - y).mean())
        name = f"histgb_iter{max_iter}_lr{learning_rate}_leaf{max_leaf_nodes}"
        if best_hist is None or score < best_hist[0]:
            best_hist = (score, est, name)
    if best_hist is not None:
        models.append(SurrogateModel(best_hist[2], best_hist[1], pre))

    rf = RandomForestRegressor(n_estimators=100, min_samples_leaf=2, random_state=42, n_jobs=-1)
    rf.fit(x, y)
    models.append(SurrogateModel("random_forest", rf, pre))
    et = ExtraTreesRegressor(n_estimators=100, min_samples_leaf=2, random_state=42, n_jobs=-1)
    et.fit(x, y)
    models.append(SurrogateModel("extra_trees", et, pre))
    return models


def fit_models(train_df: pd.DataFrame) -> list[SurrogateModel]:
    models = [_fit_ridge(train_df)]
    models.extend(_fit_sklearn_models_if_available(train_df))
    try:
        from lightgbm import LGBMRegressor
        from sklearn.multioutput import MultiOutputRegressor
    except Exception:
        pass
    else:
        pre = TabularPreprocessor(one_hot=False).fit(train_df)
        est = MultiOutputRegressor(LGBMRegressor(random_state=42, n_estimators=300))
        est.fit(pre.transform(train_df).to_numpy(dtype=float), train_df[TARGET_COLUMNS].to_numpy(dtype=float))
        models.append(SurrogateModel("lightgbm", est, pre))
    models.extend([_fit_knn(train_df), _fit_bucket_mean(train_df)])
    return models


def save_model(model: SurrogateModel, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        pickle.dump(model, handle)
    return target


def load_model(path: str | Path) -> SurrogateModel:
    with Path(path).open("rb") as handle:
        return pickle.load(handle)


def prediction_frame(model: SurrogateModel, test_df: pd.DataFrame) -> pd.DataFrame:
    pred = model.predict(test_df)
    true = test_df[TARGET_COLUMNS].to_numpy(dtype=float)
    out = test_df[
        [
            "state_id",
            "seat",
            "current_rank",
            "score_self",
            "score_0",
            "score_1",
            "score_2",
            "score_3",
            "gap_to_1st",
            "gap_to_4th",
            "honba",
            "kyotaku",
            "score_range",
            "gap_to_next_rank",
        ]
    ].copy()
    for index, column in enumerate(TARGET_COLUMNS):
        out[f"{column}_true"] = true[:, index]
        out[f"{column}_pred"] = pred[:, index]
    out["ptev_true"] = ptev_from_probs(true)
    out["ptev_pred"] = ptev_from_probs(pred)
    out["ptev_error"] = out["ptev_pred"] - out["ptev_true"]
    out["abs_ptev_error"] = out["ptev_error"].abs()
    out["model"] = model.name
    return out
