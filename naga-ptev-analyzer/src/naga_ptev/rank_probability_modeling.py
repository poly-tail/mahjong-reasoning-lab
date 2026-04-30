from __future__ import annotations

import json
import math
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from naga_ptev.modeling_dataset import (
    FEATURE_COLUMNS,
    RANK_POINTS,
    TARGET_COLUMNS,
    add_state_id,
    bucketize_abs_gap,
    bucketize_score_range,
    group_shuffle_split_state_ids,
    normalize_probabilities,
    ptev_from_probs,
)
from naga_ptev.modeling_train import fit_models


KYOKU_LABELS = {
    0: "East 1",
    1: "East 2",
    2: "East 3",
    3: "East 4",
    4: "South 1",
    5: "South 2",
    6: "South 3",
    7: "South 4 / Oorasu",
}
OUTPUT_ROOT = Path("out/rank_probability_modeling")
MODEL_NOTICE = (
    "今回の主目的は局ごとの順位確率 p1,p2,p3,p4 の近似であり、ptEV近似ではありません。"
    "ptEVは予測順位確率から計算する参考値です。kyoku=7（南4/オーラス）は今回の対象外です。"
    "南2 kyoku=5 のデータが多いことは許容し、最終比較では macro average by kyoku を重視します。"
)


def _font(size: int = 12) -> ImageFont.ImageFont:
    for path in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _state_id_df(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = add_state_id(df)
    return df[df["kyoku"] != 7].copy()


def _distribution_table(df: pd.DataFrame, index: str, columns: str) -> str:
    table = pd.crosstab(df[index], df[columns])
    return _df_to_markdown(table.reset_index())


def _df_to_markdown(df: pd.DataFrame) -> str:
    columns = [str(column) for column in df.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in df.columns) + " |")
    return "\n".join(lines)


def write_data_quality_report(df: pd.DataFrame, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    prob_sum = df[TARGET_COLUMNS].sum(axis=1)
    lines = [
        "# Rank Probability Modeling Data Quality Report",
        "",
        MODEL_NOTICE,
        "",
        "## Basic Counts",
        "",
        f"- row count: {len(df)}",
        f"- unique state count: {df['state_id'].nunique()}",
        f"- kyoku distribution: `{df['kyoku'].value_counts().sort_index().to_dict()}`",
        "",
        "## current_rank distribution by kyoku",
        "",
        _distribution_table(df, "kyoku", "current_rank"),
        "",
        "## honba distribution by kyoku",
        "",
        _distribution_table(df, "kyoku", "honba"),
        "",
        "## kyotaku distribution by kyoku",
        "",
        _distribution_table(df, "kyoku", "kyotaku"),
        "",
        "## p1+p2+p3+p4 Check",
        "",
        f"- min: {prob_sum.min():.12f}",
        f"- max: {prob_sum.max():.12f}",
        f"- mean: {prob_sum.mean():.12f}",
        f"- max abs error from 1: {(prob_sum - 1.0).abs().max():.12g}",
        "",
        "## p1,p2,p3,p4 describe by kyoku",
        "",
        df.groupby("kyoku")[TARGET_COLUMNS].describe().to_string(),
        "",
        "## p1,p4 describe by kyoku and current_rank",
        "",
        df.groupby(["kyoku", "current_rank"])[["p1", "p4"]].describe().to_string(),
        "",
    ]
    (out / "data_quality_report.md").write_text("\n".join(lines), encoding="utf-8")


def _split_by_state(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_ids, test_ids = group_shuffle_split_state_ids(df["state_id"], test_size=0.2, random_state=42)
    return df[df["state_id"].isin(train_ids)].copy(), df[df["state_id"].isin(test_ids)].copy()


def _predict_frame(model: Any, test_df: pd.DataFrame, kyoku: int) -> pd.DataFrame:
    pred = normalize_probabilities(model.predict(test_df))
    true = test_df[TARGET_COLUMNS].to_numpy(dtype=float)
    out = test_df[
        [
            "state_id",
            "kyoku",
            "seat",
            "current_rank",
            "honba",
            "kyotaku",
            "score_self",
            "score_0",
            "score_1",
            "score_2",
            "score_3",
            "gap_to_1st",
            "gap_to_4th",
            "gap_to_next_rank",
            "gap_from_prev_rank",
            "score_range",
        ]
    ].copy()
    for index, col in enumerate(TARGET_COLUMNS):
        out[f"{col}_true"] = true[:, index]
        out[f"{col}_pred"] = pred[:, index]
        out[f"{col}_error"] = pred[:, index] - true[:, index]
        out[f"abs_{col}_error"] = np.abs(pred[:, index] - true[:, index])
    out["ptev_true"] = ptev_from_probs(true)
    out["ptev_pred"] = pred.dot(RANK_POINTS)
    out["abs_ptev_error"] = (out["ptev_pred"] - out["ptev_true"]).abs()
    out["model"] = model.name
    out["kyoku"] = int(kyoku)
    out["score_range_bucket"] = bucketize_score_range(out["score_range"])
    out["gap_to_1st_bucket"] = bucketize_abs_gap(out["gap_to_1st"])
    out["gap_to_4th_bucket"] = bucketize_abs_gap(out["gap_to_4th"])
    out["gap_to_next_rank_bucket"] = bucketize_abs_gap(out["gap_to_next_rank"])
    out["gap_from_prev_rank_bucket"] = bucketize_abs_gap(out["gap_from_prev_rank"])
    return out


def _kl_divergence(true: np.ndarray, pred: np.ndarray, eps: float = 1e-9) -> float:
    t = np.clip(true, eps, 1.0)
    p = np.clip(pred, eps, 1.0)
    return float((t * np.log(t / p)).sum(axis=1).mean())


def _metrics(pred_df: pd.DataFrame) -> dict[str, Any]:
    true = pred_df[[f"{c}_true" for c in TARGET_COLUMNS]].to_numpy(dtype=float)
    pred = pred_df[[f"{c}_pred" for c in TARGET_COLUMNS]].to_numpy(dtype=float)
    row: dict[str, Any] = {
        "kyoku": int(pred_df["kyoku"].iloc[0]),
        "model": str(pred_df["model"].iloc[0]),
        "row_count": int(len(pred_df)),
    }
    abs_err = np.abs(pred - true)
    for i, col in enumerate(TARGET_COLUMNS):
        row[f"{col}_MAE"] = float(abs_err[:, i].mean())
        row[f"{col}_max_absolute_error"] = float(abs_err[:, i].max())
    row["mean_probability_MAE"] = float(abs_err.mean())
    row["p1_p4_focus_MAE"] = float((row["p1_MAE"] + row["p4_MAE"]) / 2.0)
    row["Brier_score"] = float(((pred - true) ** 2).sum(axis=1).mean())
    row["KL_divergence"] = _kl_divergence(true, pred)
    row["ptEV_MAE_reference"] = float(pred_df["abs_ptev_error"].mean())
    return row


def _save_pickle(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(obj, f)


def _save_feature_columns(path: Path) -> None:
    path.write_text(json.dumps(FEATURE_COLUMNS, indent=2), encoding="utf-8")


def _axis_limits(values: pd.Series | np.ndarray) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    lo = float(np.nanmin(arr))
    hi = float(np.nanmax(arr))
    if math.isclose(lo, hi):
        lo -= 1.0
        hi += 1.0
    pad = (hi - lo) * 0.05
    return lo - pad, hi + pad


def _draw_scatter(df: pd.DataFrame, x: str, y: str, color_col: str, title: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 560), "#ffffff")
    d = ImageDraw.Draw(img)
    font = _font(13)
    title_font = _font(18)
    left, top, right, bottom = 72, 54, 860, 500
    d.text((left, 18), title, fill="#111111", font=title_font)
    d.rectangle((left, top, right, bottom), outline="#333333")
    xlo, xhi = _axis_limits(df[x])
    ylo, yhi = _axis_limits(df[y])
    palette = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#4b5563"]
    for idx, key in enumerate(sorted(df[color_col].dropna().unique())):
        sub = df[df[color_col] == key]
        color = palette[idx % len(palette)]
        for _, row in sub.sample(min(len(sub), 1200), random_state=idx).iterrows():
            px = left + (float(row[x]) - xlo) / (xhi - xlo) * (right - left)
            py = bottom - (float(row[y]) - ylo) / (yhi - ylo) * (bottom - top)
            d.ellipse((px - 2, py - 2, px + 2, py + 2), fill=color)
        d.text((right - 120, top + 18 * idx), f"{color_col}={key}", fill=color, font=font)
    d.text((left, bottom + 28), x, fill="#111111", font=font)
    d.text((8, top + 8), y, fill="#111111", font=font)
    d.text((left - 46, bottom - 8), f"{ylo:.2f}", fill="#555555", font=font)
    d.text((left - 46, top - 8), f"{yhi:.2f}", fill="#555555", font=font)
    img.save(path)


def _draw_hist(series: pd.Series, title: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 520), "#ffffff")
    d = ImageDraw.Draw(img)
    font = _font(13)
    title_font = _font(18)
    left, top, right, bottom = 70, 54, 860, 470
    d.text((left, 18), title, fill="#111111", font=title_font)
    counts, edges = np.histogram(series.to_numpy(dtype=float), bins=40)
    max_count = max(int(counts.max()), 1)
    d.rectangle((left, top, right, bottom), outline="#333333")
    for i, count in enumerate(counts):
        x0 = left + i / len(counts) * (right - left)
        x1 = left + (i + 1) / len(counts) * (right - left)
        y0 = bottom - count / max_count * (bottom - top)
        d.rectangle((x0, y0, x1, bottom), fill="#2563eb", outline="#ffffff")
    d.text((left, bottom + 26), f"{series.name or 'error'}", fill="#111111", font=font)
    d.text((left, bottom + 44), f"min={edges[0]:.4f} max={edges[-1]:.4f}", fill="#555555", font=font)
    img.save(path)


def _draw_line(df: pd.DataFrame, x: str, y_cols: list[str], group: str, title: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (920, 560), "#ffffff")
    d = ImageDraw.Draw(img)
    font = _font(12)
    title_font = _font(18)
    left, top, right, bottom = 78, 54, 860, 500
    d.text((left, 18), title, fill="#111111", font=title_font)
    d.rectangle((left, top, right, bottom), outline="#333333")
    palette = ["#2563eb", "#dc2626", "#16a34a", "#9333ea"]
    grouped = df.groupby([group, x])[y_cols].mean().reset_index()
    xlo, xhi = _axis_limits(grouped[x])
    ylo, yhi = _axis_limits(grouped[y_cols].to_numpy().ravel())
    legend_i = 0
    for gval, sub in grouped.groupby(group):
        sub = sub.sort_values(x)
        for yi, y in enumerate(y_cols):
            points = []
            for _, row in sub.iterrows():
                px = left + (float(row[x]) - xlo) / (xhi - xlo) * (right - left)
                py = bottom - (float(row[y]) - ylo) / (yhi - ylo) * (bottom - top)
                points.append((px, py))
            if len(points) >= 2:
                d.line(points, fill=palette[yi % len(palette)], width=2)
            for px, py in points:
                d.ellipse((px - 2, py - 2, px + 2, py + 2), fill=palette[yi % len(palette)])
        if legend_i < 8:
            d.text((right - 126, top + 16 * legend_i), f"{group}={gval}", fill="#111111", font=font)
        legend_i += 1
    d.text((left, bottom + 28), x, fill="#111111", font=font)
    d.text((8, top + 8), ",".join(y_cols), fill="#111111", font=font)
    img.save(path)


def _draw_heatmap(pivot: pd.DataFrame, title: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = pivot.fillna(0).to_numpy(dtype=float)
    img = Image.new("RGB", (900, 560), "#ffffff")
    d = ImageDraw.Draw(img)
    font = _font(11)
    title_font = _font(18)
    left, top, right, bottom = 120, 70, 850, 500
    d.text((left, 22), title, fill="#111111", font=title_font)
    rows, cols = values.shape
    vmax = float(values.max()) if values.size else 1.0
    vmax = max(vmax, 1e-9)
    cell_w = (right - left) / max(cols, 1)
    cell_h = (bottom - top) / max(rows, 1)
    for r in range(rows):
        for c in range(cols):
            ratio = float(values[r, c]) / vmax
            color = (255, int(245 - 160 * ratio), int(245 - 210 * ratio))
            x0, y0 = left + c * cell_w, top + r * cell_h
            d.rectangle((x0, y0, x0 + cell_w, y0 + cell_h), fill=color, outline="#ffffff")
            d.text((x0 + 3, y0 + 3), f"{values[r,c]:.3f}", fill="#111111", font=font)
    for c, col in enumerate(pivot.columns):
        d.text((left + c * cell_w + 2, bottom + 8), str(col), fill="#111111", font=font)
    for r, idx in enumerate(pivot.index):
        d.text((left - 70, top + r * cell_h + 4), str(idx), fill="#111111", font=font)
    img.save(path)


def _curve_points(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    specs = [
        ("gap_to_1st", "p1", "gap_to_1st_to_p1"),
        ("gap_to_4th", "p4", "gap_to_4th_to_p4"),
        ("gap_to_next_rank", "p1", "gap_to_next_rank_to_improve_p1"),
        ("gap_from_prev_rank", "p4", "gap_from_prev_rank_to_drop_p4"),
    ]
    for (kyoku, rank), sub in df.groupby(["kyoku", "current_rank"]):
        for x, y, curve_name in specs:
            binned = sub.copy()
            binned["bin"] = pd.qcut(binned[x].rank(method="first"), q=min(20, len(binned)), duplicates="drop")
            agg = binned.groupby("bin", observed=False).agg(x_value=(x, "mean"), y_value=(y, "mean"), row_count=(y, "size")).reset_index(drop=True)
            for _, row in agg.iterrows():
                rows.append(
                    {
                        "kyoku": int(kyoku),
                        "current_rank": int(rank),
                        "curve": curve_name,
                        "x_feature": x,
                        "y_target": y,
                        "x_value": float(row["x_value"]),
                        "y_value": float(row["y_value"]),
                        "row_count": int(row["row_count"]),
                    }
                )
    return pd.DataFrame(rows)


def _write_plots(df: pd.DataFrame, all_pred: pd.DataFrame, metrics_best: pd.DataFrame, out: Path) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    for kyoku, sub in df.groupby("kyoku"):
        kdir = out / f"kyoku_{int(kyoku)}"
        pred = all_pred[all_pred["kyoku"] == kyoku]
        _draw_scatter(sub, "gap_to_1st", "p1", "current_rank", f"Kyoku {kyoku}: Gap to 1st vs P1", kdir / "gap_to_1st_vs_p1_by_current_rank.png")
        _draw_scatter(sub, "gap_to_4th", "p4", "current_rank", f"Kyoku {kyoku}: Gap to 4th vs P4", kdir / "gap_to_4th_vs_p4_by_current_rank.png")
        _draw_line(sub, "gap_to_next_rank", TARGET_COLUMNS, "current_rank", f"Kyoku {kyoku}: Gap to Next Rank vs Probabilities", kdir / "gap_to_next_rank_vs_probabilities.png")
        _draw_line(sub, "gap_from_prev_rank", TARGET_COLUMNS, "current_rank", f"Kyoku {kyoku}: Gap from Previous Rank vs Probabilities", kdir / "gap_from_prev_rank_vs_probabilities.png")
        _draw_scatter(pred, "p1_true", "p1_pred", "current_rank", f"Kyoku {kyoku}: Actual vs Predicted P1", kdir / "actual_vs_predicted_p1.png")
        _draw_scatter(pred, "p4_true", "p4_pred", "current_rank", f"Kyoku {kyoku}: Actual vs Predicted P4", kdir / "actual_vs_predicted_p4.png")
        _draw_hist(pred["p1_error"].rename("P1 Error"), f"Kyoku {kyoku}: Residual Distribution for P1", kdir / "residual_distribution_p1.png")
        _draw_hist(pred["p4_error"].rename("P4 Error"), f"Kyoku {kyoku}: Residual Distribution for P4", kdir / "residual_distribution_p4.png")
        heat = pred.pivot_table(index="current_rank", columns="score_range_bucket", values="abs_p1_error", aggfunc="mean")
        _draw_heatmap(heat, f"Kyoku {kyoku}: P1 Error Heatmap", kdir / "error_heatmap_by_current_rank_and_score_range_bucket.png")

    _draw_line(df, "gap_to_next_rank", ["p1"], "kyoku", "P1 Curve by Kyoku and Current Rank Proxy", out / "p1_curve_by_kyoku.png")
    _draw_line(df, "gap_from_prev_rank", ["p4"], "kyoku", "P4 Curve by Kyoku and Current Rank Proxy", out / "p4_curve_by_kyoku.png")
    _draw_scatter(metrics_best, "kyoku", "mean_probability_MAE", "model", "Mean Probability MAE by Kyoku", out / "mean_probability_mae_by_kyoku.png")
    _draw_line(metrics_best, "kyoku", ["p1_MAE", "p4_MAE"], "model", "P1 MAE / P4 MAE by Kyoku", out / "p1_p4_mae_by_kyoku.png")

    curves = _curve_points(df)
    for curve_name, sub in curves.groupby("curve"):
        _draw_line(sub, "x_value", ["y_value"], "current_rank", f"Curve: {curve_name}", out / f"curve_{curve_name}.png")
    return curves


def _group_errors(pred: pd.DataFrame, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    specs = {
        "error_by_kyoku.csv": ["kyoku"],
        "error_by_current_rank.csv": ["current_rank"],
        "error_by_kyoku_current_rank.csv": ["kyoku", "current_rank"],
        "error_by_honba.csv": ["honba"],
        "error_by_kyotaku.csv": ["kyotaku"],
        "error_by_score_range_bucket.csv": ["score_range_bucket"],
        "error_by_gap_to_1st_bucket.csv": ["gap_to_1st_bucket"],
        "error_by_gap_to_4th_bucket.csv": ["gap_to_4th_bucket"],
        "error_by_gap_to_next_rank_bucket.csv": ["gap_to_next_rank_bucket"],
        "error_by_gap_from_prev_rank_bucket.csv": ["gap_from_prev_rank_bucket"],
    }
    value_cols = ["abs_p1_error", "abs_p2_error", "abs_p3_error", "abs_p4_error", "abs_ptev_error"]
    for filename, keys in specs.items():
        pred.groupby(keys, dropna=False)[value_cols].mean().reset_index().to_csv(out / filename, index=False)


def _summary_report(metrics: pd.DataFrame, macro: pd.DataFrame, pred: pd.DataFrame, out: Path) -> None:
    best = metrics.sort_values(["p1_p4_focus_MAE", "mean_probability_MAE"]).groupby("kyoku").head(1).copy()
    worst_kyoku = best.sort_values("p1_p4_focus_MAE", ascending=False).head(3)
    rank_err = pred.groupby("current_rank")[["abs_p1_error", "abs_p4_error"]].mean()
    worst_rank = rank_err.assign(focus=lambda x: (x["abs_p1_error"] + x["abs_p4_error"]) / 2).sort_values("focus", ascending=False)
    lines = [
        "# Rank Probability Modeling Summary",
        "",
        MODEL_NOTICE,
        "",
        "## Important Interpretation",
        "",
        "- The objective is p1,p2,p3,p4 approximation, not ptEV approximation.",
        "- ptEV is reported only as a reference value derived from predicted rank probabilities.",
        "- kyoku=7 is not included and is not treated as a problem in this run.",
        "- South 2 has more rows. Final comparison should prioritize macro average by kyoku over row-weighted average.",
        "",
        "## Best Model by Kyoku",
        "",
        _df_to_markdown(best[["kyoku", "model", "p1_MAE", "p4_MAE", "mean_probability_MAE", "Brier_score", "KL_divergence"]]),
        "",
        "## Macro Average by Kyoku",
        "",
        _df_to_markdown(macro),
        "",
        "## Kyoku with Larger P1/P4 Errors",
        "",
        _df_to_markdown(worst_kyoku[["kyoku", "model", "p1_MAE", "p4_MAE", "p1_p4_focus_MAE"]]),
        "",
        "## current_rank with Larger Errors",
        "",
        _df_to_markdown(worst_rank.reset_index()),
        "",
        "## Suggested Additional Collection",
        "",
        "- Add states for kyoku/current_rank combinations with the largest p1/p4 focus errors.",
        "- Add more boundary states around small `gap_to_1st`, `gap_to_4th`, `gap_to_next_rank`, and `gap_from_prev_rank` buckets.",
        "- Keep collecting kyoku separately; do not rely only on row-weighted global averages.",
        "",
    ]
    (out / "summary_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_rank_probability_pipeline(
    *,
    base_csv: str | Path = "naga-ptev-analyzer/out/dataset/base_predictions_2000.csv",
    out_dir: str | Path = OUTPUT_ROOT,
) -> dict[str, Any]:
    out = Path(out_dir)
    plots_dir = out / "plots"
    models_dir = out / "models"
    predictions_dir = out / "predictions"
    for directory in (out, plots_dir, models_dir, predictions_dir):
        directory.mkdir(parents=True, exist_ok=True)

    df = _state_id_df(base_csv)
    write_data_quality_report(df, out)
    metric_rows: list[dict[str, Any]] = []
    best_prediction_frames: list[pd.DataFrame] = []
    best_model_rows: list[dict[str, Any]] = []
    for kyoku, kdf in sorted(df.groupby("kyoku"), key=lambda item: int(item[0])):
        train_df, test_df = _split_by_state(kdf)
        models = fit_models(train_df)
        predictions = []
        for model in models:
            pred = _predict_frame(model, test_df, int(kyoku))
            metric_rows.append(_metrics(pred))
            predictions.append((model, pred))
        metrics_for_k = pd.DataFrame([_metrics(pred) for _model, pred in predictions]).sort_values(
            ["p1_p4_focus_MAE", "mean_probability_MAE"]
        )
        best_name = str(metrics_for_k.iloc[0]["model"])
        best_model = next(model for model, _pred in predictions if model.name == best_name)
        best_pred = next(pred for model, pred in predictions if model.name == best_name)
        k_model_dir = models_dir / f"kyoku_{int(kyoku)}"
        _save_pickle(best_model, k_model_dir / "best_model.pkl")
        _save_feature_columns(k_model_dir / "feature_columns.json")
        best_pred.to_csv(predictions_dir / f"kyoku_{int(kyoku)}_test_predictions.csv", index=False)
        best_prediction_frames.append(best_pred)
        best_model_rows.append(metrics_for_k.iloc[0].to_dict())

    metrics = pd.DataFrame(metric_rows).sort_values(["kyoku", "p1_p4_focus_MAE", "mean_probability_MAE"])
    metrics.to_csv(out / "model_metrics_by_kyoku.csv", index=False)
    macro = metrics.groupby("model", dropna=False).mean(numeric_only=True).reset_index()
    weighted_rows = []
    for model, group in metrics.groupby("model", dropna=False):
        weights = group["row_count"].to_numpy(dtype=float)
        row: dict[str, Any] = {"model": model, "average_type": "weighted_by_row_count"}
        for col in [c for c in metrics.columns if c not in {"model"}]:
            if col == "kyoku":
                continue
            row[col] = float(np.average(group[col].to_numpy(dtype=float), weights=weights))
        weighted_rows.append(row)
    macro_out = macro.copy()
    macro_out.insert(1, "average_type", "macro_by_kyoku")
    combined_macro = pd.concat([macro_out, pd.DataFrame(weighted_rows)], ignore_index=True, sort=False)
    combined_macro.to_csv(out / "model_metrics_macro.csv", index=False)

    best_metrics = pd.DataFrame(best_model_rows)
    all_best_pred = pd.concat(best_prediction_frames, ignore_index=True)
    _group_errors(all_best_pred, out)
    curves = _write_plots(df, all_best_pred, best_metrics, plots_dir)
    curves.to_csv(out / "curve_points_by_kyoku_rank.csv", index=False)
    _summary_report(best_metrics, combined_macro, all_best_pred, out)
    return {
        "kyoku_count": int(df["kyoku"].nunique()),
        "row_count": int(len(df)),
        "models_evaluated": sorted(metrics["model"].unique().tolist()),
        "output_dir": str(out),
    }


if __name__ == "__main__":
    print(json.dumps(run_rank_probability_pipeline(), ensure_ascii=False, indent=2))
