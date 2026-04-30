from __future__ import annotations

from pathlib import Path

import pandas as pd


KEY_COLUMNS = ["kyoku", "honba", "kyotaku", "score_0", "score_1", "score_2", "score_3", "seat"]
BASE_COLUMNS = [*KEY_COLUMNS, "p1", "p2", "p3", "p4", "ptev_default"]
BRANCH_COLUMNS = [
    *KEY_COLUMNS,
    "p1",
    "p2",
    "p3",
    "p4",
    "ptev_default",
    "category",
    "branch_index",
    "actor",
    "target",
    "score_mv",
]


def build_branch_delta(
    *,
    base_csv: str | Path,
    branch_csv: str | Path,
    reports_dir: str | Path,
    max_rows: int = 200_000,
) -> dict[str, object]:
    out = Path(reports_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = pd.read_csv(base_csv, usecols=BASE_COLUMNS)
    branch = pd.read_csv(branch_csv, usecols=BRANCH_COLUMNS, nrows=max_rows)
    merged = branch.merge(base, on=KEY_COLUMNS, suffixes=("_branch", "_base"), how="inner")
    for column in ("p1", "p2", "p3", "p4"):
        merged[f"delta_{column}"] = merged[f"{column}_branch"] - merged[f"{column}_base"]
    merged["delta_ptev"] = merged["ptev_default_branch"] - merged["ptev_default_base"]

    keep = [
        *KEY_COLUMNS,
        "category",
        "branch_index",
        "actor",
        "target",
        "score_mv",
        "delta_p1",
        "delta_p2",
        "delta_p3",
        "delta_p4",
        "delta_ptev",
    ]
    merged[keep].head(max_rows).to_csv(out / "branch_delta_sample.csv", index=False)
    merged.groupby("category", dropna=False)[["delta_p1", "delta_p2", "delta_p3", "delta_p4", "delta_ptev"]].agg(
        ["count", "mean", "std", "min", "max"]
    ).to_csv(out / "branch_delta_summary_by_category.csv")
    merged.assign(score_mv_bucket=pd.cut(merged["score_mv"], bins=[-999, -120, -80, -40, 0, 40, 80, 120, 999])).groupby(
        ["category", "score_mv_bucket"], dropna=False
    )[["delta_ptev"]].agg(["count", "mean", "std", "min", "max"]).to_csv(
        out / "branch_delta_summary_by_category_score_mv.csv"
    )
    return {
        "branch_rows_read": int(len(branch)),
        "merged_rows": int(len(merged)),
        "max_rows": int(max_rows),
        "truncated": bool(len(branch) >= int(max_rows)),
    }

