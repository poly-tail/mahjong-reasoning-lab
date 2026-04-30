from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from naga_ptev.modeling import TARGET_COLUMNS, load_model, ptev_from_probabilities


SplitKind = Literal["random", "kyoku_holdout", "south_round_holdout"]


def _split_mask(df: pd.DataFrame, split: str) -> pd.Series:
    normalized = str(split or "random").strip().lower()
    if normalized == "kyoku_holdout":
        return df["kyoku"].isin([6, 7])
    if normalized == "south_round_holdout":
        return df["is_south_round"].astype(bool)
    rng = np.random.default_rng(1)
    return pd.Series(rng.random(len(df)) < 0.2, index=df.index)


def _gap_bucket(value: float) -> str:
    absolute = abs(float(value))
    if absolute <= 10:
        return "000-010"
    if absolute <= 30:
        return "011-030"
    if absolute <= 60:
        return "031-060"
    if absolute <= 100:
        return "061-100"
    return "101+"


def evaluate_model(
    *,
    dataset: str | Path,
    model: str | Path,
    out: str | Path = "out/eval",
    split: str = "random",
) -> tuple[Path, Path]:
    df = pd.read_csv(dataset)
    test_mask = _split_mask(df, split)
    test_df = df.loc[test_mask].copy()
    if test_df.empty:
        test_df = df.copy()
    loaded = load_model(model)
    pred = loaded.predict_proba(test_df)
    actual = test_df[TARGET_COLUMNS].to_numpy(dtype=float)
    errors = np.abs(pred - actual)
    actual_ptev = test_df["ptev_default"].to_numpy(dtype=float)
    pred_ptev = ptev_from_probabilities(pred)
    ptev_error = np.abs(pred_ptev - actual_ptev)

    error_df = test_df.copy()
    for index, column in enumerate(TARGET_COLUMNS):
        error_df[f"pred_{column}"] = pred[:, index]
        error_df[f"err_{column}"] = pred[:, index] - actual[:, index]
        error_df[f"abs_err_{column}"] = errors[:, index]
    error_df["pred_ptev"] = pred_ptev
    error_df["err_ptev"] = pred_ptev - actual_ptev
    error_df["abs_err_ptev"] = ptev_error
    error_df["score_gap_bucket"] = error_df["gap_to_next_rank"].map(_gap_bucket)
    error_df["near_rank_boundary"] = error_df["gap_to_next_rank"].abs() <= 30

    metrics: dict[str, object] = {
        "split": split,
        "rows": int(len(test_df)),
        "ptEV_MAE": float(ptev_error.mean()),
        "ptEV_max_error": float(ptev_error.max()),
    }
    for index, column in enumerate(TARGET_COLUMNS):
        metrics[f"MAE_{column}"] = float(errors[:, index].mean())
        metrics[f"max_error_{column}"] = float(errors[:, index].max())

    metrics["error_by_kyoku"] = error_df.groupby("kyoku")["abs_err_ptev"].mean().to_dict()
    metrics["error_by_current_rank"] = error_df.groupby("current_rank")["abs_err_ptev"].mean().to_dict()
    metrics["error_by_score_gap_bucket"] = error_df.groupby("score_gap_bucket")["abs_err_ptev"].mean().to_dict()
    metrics["error_near_rank_boundary"] = error_df.groupby("near_rank_boundary")["abs_err_ptev"].mean().to_dict()

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / "metrics.json"
    errors_path = out_dir / "errors.csv"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    error_df.to_csv(errors_path, index=False)
    return metrics_path, errors_path

