from __future__ import annotations

from pathlib import Path

import pandas as pd


def _ensure_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _save_scatter(df: pd.DataFrame, *, x: str, y: str, color: str, title: str, out: Path) -> None:
    plt = _ensure_matplotlib()
    fig, ax = plt.subplots(figsize=(8, 5))
    for key, group in df.groupby(color):
        ax.scatter(group[x], group[y], s=12, alpha=0.55, label=str(key))
    ax.set_title(title)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.legend(title=color, fontsize=8)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def _save_line(df: pd.DataFrame, *, x: str, y: str, group: str, title: str, out: Path) -> None:
    plt = _ensure_matplotlib()
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped = df.groupby([group, x])[y].mean().reset_index()
    for key, sub in grouped.groupby(group):
        ax.plot(sub[x], sub[y], marker="o", label=str(key))
    ax.set_title(title)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.legend(title=group, fontsize=8)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def build_plots(
    *,
    dataset: str | Path,
    pred: str | Path | None = None,
    out: str | Path = "out/plots",
) -> Path:
    df = pd.read_csv(dataset)
    pred_df = pd.read_csv(pred) if pred is not None and Path(pred).exists() else None
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)

    _save_scatter(df, x="gap_to_1st", y="p1", color="kyoku", title="Gap to 1st vs P1 by Kyoku", out=out_dir / "gap_to_1st_vs_p1_by_kyoku.png")
    _save_scatter(df, x="gap_to_4th", y="p4", color="kyoku", title="Gap to 4th vs P4 by Kyoku", out=out_dir / "gap_to_4th_vs_p4_by_kyoku.png")
    _save_line(df, x="current_rank", y="ptev_default", group="kyoku", title="ptEV Curve by Current Rank", out=out_dir / "ptev_curve_by_current_rank.png")
    _save_line(df, x="kyotaku", y="ptev_default", group="current_rank", title="Kyotaku Effect Curve", out=out_dir / "kyotaku_effect_curve.png")
    _save_line(df, x="honba", y="ptev_default", group="current_rank", title="Honba Effect Curve", out=out_dir / "honba_effect_curve.png")
    _save_line(df, x="gap_to_next_rank", y="ptev_default", group="is_oorasu", title="Oorasu Condition Curve", out=out_dir / "oorasu_condition_curve.png")

    if pred_df is not None and {"pred_ptev", "ptev_default"}.issubset(pred_df.columns):
        plt = _ensure_matplotlib()
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.scatter(pred_df["ptev_default"], pred_df["pred_ptev"], s=12, alpha=0.6)
        low = min(pred_df["ptev_default"].min(), pred_df["pred_ptev"].min())
        high = max(pred_df["ptev_default"].max(), pred_df["pred_ptev"].max())
        ax.plot([low, high], [low, high], color="black", linewidth=1)
        ax.set_title("Actual vs Predicted ptEV")
        ax.set_xlabel("Actual ptEV")
        ax.set_ylabel("Predicted ptEV")
        fig.tight_layout()
        fig.savefig(out_dir / "actual_vs_predicted_ptev.png")
        plt.close(fig)

    if pred_df is not None and {"kyoku", "score_gap_bucket", "abs_err_ptev"}.issubset(pred_df.columns):
        plt = _ensure_matplotlib()
        pivot = pred_df.pivot_table(index="kyoku", columns="score_gap_bucket", values="abs_err_ptev", aggfunc="mean")
        fig, ax = plt.subplots(figsize=(8, 5))
        image = ax.imshow(pivot.fillna(0).to_numpy(), aspect="auto", cmap="magma")
        ax.set_title("Residual Heatmap by Kyoku and Score Gap Bucket")
        ax.set_xlabel("Score Gap Bucket")
        ax.set_ylabel("Kyoku")
        ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(pivot.index)), pivot.index)
        fig.colorbar(image, ax=ax, label="ptEV Absolute Error")
        fig.tight_layout()
        fig.savefig(out_dir / "residual_heatmap_by_kyoku_and_score_gap_bucket.png")
        plt.close(fig)

    return out_dir

