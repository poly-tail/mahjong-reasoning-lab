from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from naga_ptev.modeling_dataset import bucketize_abs_gap, bucketize_score_range
from naga_ptev.modeling_train import SurrogateModel, prediction_frame


def r2_score_np(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    residual = float(((y_true - y_pred) ** 2).sum())
    total = float(((y_true - y_true.mean()) ** 2).sum())
    return 0.0 if total == 0 else 1.0 - residual / total


def metrics_from_predictions(pred_df: pd.DataFrame) -> dict[str, float | str]:
    rows: dict[str, float | str] = {"model": str(pred_df["model"].iloc[0])}
    prob_abs_errors = []
    for column in ("p1", "p2", "p3", "p4"):
        err = (pred_df[f"{column}_pred"] - pred_df[f"{column}_true"]).abs()
        rows[f"{column}_MAE"] = float(err.mean())
        prob_abs_errors.append(err.to_numpy(dtype=float))
    stacked = np.vstack(prob_abs_errors)
    rows["probability_mean_MAE"] = float(stacked.mean())
    rows["probability_max_absolute_error"] = float(stacked.max())
    ptev_err = pred_df["ptev_pred"] - pred_df["ptev_true"]
    rows["ptEV_MAE"] = float(ptev_err.abs().mean())
    rows["ptEV_RMSE"] = float(np.sqrt((ptev_err**2).mean()))
    rows["ptEV_max_absolute_error"] = float(ptev_err.abs().max())
    rows["ptEV_R2"] = r2_score_np(pred_df["ptev_true"].to_numpy(dtype=float), pred_df["ptev_pred"].to_numpy(dtype=float))
    return rows


def evaluate_models(models: list[SurrogateModel], test_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    pred_frames = [prediction_frame(model, test_df) for model in models]
    all_predictions = pd.concat(pred_frames, ignore_index=True)
    metrics = pd.DataFrame([metrics_from_predictions(frame) for frame in pred_frames]).sort_values("ptEV_MAE")
    best_model = str(metrics.iloc[0]["model"])
    best_predictions = all_predictions[all_predictions["model"] == best_model].copy()
    best_predictions["score_range_bucket"] = bucketize_score_range(best_predictions["score_range"])
    best_predictions["gap_to_1st_bucket"] = bucketize_abs_gap(best_predictions["gap_to_1st"])
    best_predictions["gap_to_4th_bucket"] = bucketize_abs_gap(best_predictions["gap_to_4th"])

    grouped = {
        "error_by_current_rank": best_predictions.groupby("current_rank", dropna=False)["abs_ptev_error"].mean().reset_index(),
        "error_by_honba": best_predictions.groupby("honba", dropna=False)["abs_ptev_error"].mean().reset_index(),
        "error_by_kyotaku": best_predictions.groupby("kyotaku", dropna=False)["abs_ptev_error"].mean().reset_index(),
        "error_by_score_range_bucket": best_predictions.groupby("score_range_bucket", dropna=False)["abs_ptev_error"].mean().reset_index(),
        "error_by_gap_to_1st_bucket": best_predictions.groupby("gap_to_1st_bucket", dropna=False)["abs_ptev_error"].mean().reset_index(),
        "error_by_gap_to_4th_bucket": best_predictions.groupby("gap_to_4th_bucket", dropna=False)["abs_ptev_error"].mean().reset_index(),
    }
    return metrics, grouped, best_predictions


def write_evaluation_outputs(
    *,
    metrics: pd.DataFrame,
    grouped: dict[str, pd.DataFrame],
    best_predictions: pd.DataFrame,
    reports_dir: str | Path,
) -> None:
    out = Path(reports_dir)
    out.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(out / "model_metrics.csv", index=False)
    columns = [
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
        "p1_true",
        "p2_true",
        "p3_true",
        "p4_true",
        "p1_pred",
        "p2_pred",
        "p3_pred",
        "p4_pred",
        "ptev_true",
        "ptev_pred",
        "abs_ptev_error",
    ]
    best_predictions[columns].to_csv(out / "test_predictions.csv", index=False)
    grouped["error_by_current_rank"].to_csv(out / "error_by_current_rank.csv", index=False)
    grouped["error_by_kyotaku"].to_csv(out / "error_by_kyotaku.csv", index=False)
    grouped["error_by_score_range_bucket"].to_csv(out / "error_by_score_range_bucket.csv", index=False)
    grouped["error_by_honba"].to_csv(out / "error_by_honba.csv", index=False)
    grouped["error_by_gap_to_1st_bucket"].to_csv(out / "error_by_gap_to_1st_bucket.csv", index=False)
    grouped["error_by_gap_to_4th_bucket"].to_csv(out / "error_by_gap_to_4th_bucket.csv", index=False)

