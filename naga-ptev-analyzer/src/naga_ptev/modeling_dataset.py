from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


STATE_KEY_COLUMNS = ["kyoku", "honba", "kyotaku", "score_0", "score_1", "score_2", "score_3"]
FEATURE_COLUMNS = [
    "honba",
    "kyotaku",
    "seat",
    "score_self",
    "score_0",
    "score_1",
    "score_2",
    "score_3",
    "current_rank",
    "gap_to_1st",
    "gap_to_2nd",
    "gap_to_3rd",
    "gap_to_4th",
    "gap_to_next_rank",
    "gap_from_prev_rank",
    "score_range",
    "score_std",
    "is_dealer",
    "dealer_score",
    "kyotaku_value",
]
TARGET_COLUMNS = ["p1", "p2", "p3", "p4"]
RANK_POINTS = np.array([75.0, 30.0, 0.0, -105.0], dtype=float)
LOCAL_MODEL_NOTICE = (
    "今回のモデルは kyoku=5 固定、hands_remaining=3 固定、is_oorasu=0 固定データに基づく局所近似です。"
    "全局対応モデルとして扱わないでください。"
)


def add_state_id(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in STATE_KEY_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"missing state key columns: {missing}")
    out = df.copy()
    out["state_id"] = out[STATE_KEY_COLUMNS].astype(str).agg("|".join, axis=1)
    return out


def load_base_dataset(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = add_state_id(df)
    for column in FEATURE_COLUMNS + TARGET_COLUMNS + ["ptev_default"]:
        if column not in df.columns:
            raise ValueError(f"missing required column: {column}")
    return df


def probability_sum_report(df: pd.DataFrame) -> dict[str, float]:
    sums = df[TARGET_COLUMNS].sum(axis=1)
    return {
        "min": float(sums.min()),
        "max": float(sums.max()),
        "mean": float(sums.mean()),
        "max_abs_error_from_1": float((sums - 1.0).abs().max()),
    }


def describe_series(series: pd.Series) -> dict[str, float]:
    desc = series.describe()
    return {str(index): float(value) for index, value in desc.items()}


def distribution(series: pd.Series) -> dict[str, int]:
    return {str(key): int(value) for key, value in series.value_counts(dropna=False).sort_index().items()}


def build_quality_report(df: pd.DataFrame) -> dict[str, object]:
    unique_state_count = int(df["state_id"].nunique())
    return {
        "notice": LOCAL_MODEL_NOTICE,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "unique_state_count": unique_state_count,
        "kyoku_distribution": distribution(df["kyoku"]),
        "honba_distribution": distribution(df["honba"]),
        "kyotaku_distribution": distribution(df["kyotaku"]),
        "current_rank_distribution": distribution(df["current_rank"]),
        "hands_remaining_distribution": distribution(df["hands_remaining"]),
        "is_oorasu_distribution": distribution(df["is_oorasu"]),
        "probability_sum_check": probability_sum_report(df),
        "ptev_default_describe": describe_series(df["ptev_default"]),
    }


def write_quality_report(df: pd.DataFrame, out_dir: str | Path) -> tuple[Path, Path]:
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    report = build_quality_report(df)
    json_path = target_dir / "base_data_quality_report.json"
    md_path = target_dir / "modeling_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 麻雀順位価値関数 近似モデル レポート",
        "",
        f"**制約:** {LOCAL_MODEL_NOTICE}",
        "",
        "## base_predictions.csv データ確認",
        "",
        f"- row count: {report['row_count']}",
        f"- column count: {report['column_count']}",
        f"- unique state count: {report['unique_state_count']}",
        f"- kyoku distribution: `{report['kyoku_distribution']}`",
        f"- honba distribution: `{report['honba_distribution']}`",
        f"- kyotaku distribution: `{report['kyotaku_distribution']}`",
        f"- current_rank distribution: `{report['current_rank_distribution']}`",
        f"- hands_remaining distribution: `{report['hands_remaining_distribution']}`",
        f"- is_oorasu distribution: `{report['is_oorasu_distribution']}`",
        f"- probability sum check: `{report['probability_sum_check']}`",
        f"- ptev_default describe: `{report['ptev_default_describe']}`",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def group_shuffle_split_state_ids(
    state_ids: Sequence[str],
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[set[str], set[str]]:
    unique = np.array(sorted(set(str(value) for value in state_ids)), dtype=object)
    rng = np.random.default_rng(random_state)
    shuffled = unique.copy()
    rng.shuffle(shuffled)
    test_count = max(1, int(round(len(shuffled) * float(test_size))))
    test_ids = set(str(value) for value in shuffled[:test_count])
    train_ids = set(str(value) for value in shuffled[test_count:])
    return train_ids, test_ids


def split_dataframe_by_state(
    df: pd.DataFrame,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_ids, test_ids = group_shuffle_split_state_ids(
        df["state_id"].astype(str),
        test_size=test_size,
        random_state=random_state,
    )
    train_df = df[df["state_id"].isin(train_ids)].copy()
    test_df = df[df["state_id"].isin(test_ids)].copy()
    return train_df, test_df


def normalize_probabilities(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(values, dtype=float), 0.0, None)
    sums = clipped.sum(axis=1, keepdims=True)
    return np.divide(clipped, sums, out=np.full_like(clipped, 0.25), where=sums > 0)


def ptev_from_probs(values: np.ndarray) -> np.ndarray:
    return normalize_probabilities(values).dot(RANK_POINTS)


def bucketize_abs_gap(series: pd.Series) -> pd.Series:
    bins = [-1, 10, 30, 60, 100, 200, float("inf")]
    labels = ["000-010", "011-030", "031-060", "061-100", "101-200", "201+"]
    return pd.cut(series.abs(), bins=bins, labels=labels).astype(str)


def bucketize_score_range(series: pd.Series) -> pd.Series:
    bins = [-1, 50, 100, 150, 200, 300, float("inf")]
    labels = ["000-050", "051-100", "101-150", "151-200", "201-300", "301+"]
    return pd.cut(series, bins=bins, labels=labels).astype(str)

