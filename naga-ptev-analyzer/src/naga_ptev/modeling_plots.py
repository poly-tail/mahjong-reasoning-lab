from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px

from naga_ptev.modeling_dataset import bucketize_abs_gap


def _write(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(path), include_plotlyjs="cdn")


def write_modeling_plots(pred_df: pd.DataFrame, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    fig = px.scatter(pred_df, x="ptev_true", y="ptev_pred", title="Actual vs Predicted ptEV")
    low = min(float(pred_df["ptev_true"].min()), float(pred_df["ptev_pred"].min()))
    high = max(float(pred_df["ptev_true"].max()), float(pred_df["ptev_pred"].max()))
    fig.add_shape(type="line", x0=low, y0=low, x1=high, y1=high, line={"color": "black", "width": 1})
    _write(fig, out / "actual_vs_predicted_ptev.html")
    _write(
        px.histogram(pred_df, x="ptev_error", nbins=50, title="Residual Distribution", labels={"ptev_error": "ptEV Error"}),
        out / "residual_distribution.html",
    )
    _write(
        px.scatter(pred_df, x="gap_to_1st", y="p1_true", color="current_rank", title="Gap to 1st vs P1"),
        out / "gap_to_1st_vs_p1.html",
    )
    _write(
        px.scatter(pred_df, x="gap_to_4th", y="p4_true", color="current_rank", title="Gap to 4th vs P4"),
        out / "gap_to_4th_vs_p4.html",
    )

    curve = pred_df.copy()
    curve["gap_to_next_rank_bucket"] = bucketize_abs_gap(curve["gap_to_next_rank"])
    grouped = curve.groupby(["current_rank", "gap_to_next_rank_bucket"], dropna=False)["ptev_true"].mean().reset_index()
    _write(
        px.line(
            grouped,
            x="gap_to_next_rank_bucket",
            y="ptev_true",
            color="current_rank",
            markers=True,
            title="ptEV by Current Rank and Gap-to-Next-Rank Bucket",
        ),
        out / "ptev_by_current_rank_and_gap_to_next_rank_bucket.html",
    )

    heat = pred_df.pivot_table(
        index="current_rank",
        columns="score_range_bucket",
        values="abs_ptev_error",
        aggfunc="mean",
    )
    _write(
        px.imshow(
            heat,
            title="Error Heatmap by Current Rank and Score Range Bucket",
            labels={"x": "Score Range Bucket", "y": "Current Rank", "color": "ptEV MAE"},
            aspect="auto",
        ),
        out / "error_heatmap_by_current_rank_and_score_range_bucket.html",
    )
