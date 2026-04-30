from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


INPUT_PATH = Path("base_predictions_2000.csv")
FALLBACK_INPUT_PATH = Path("out/dataset/base_predictions_2000.csv")
OUT_DIR = Path("out/rank_probability_variance")
OUT_DIR.mkdir(parents=True, exist_ok=True)


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


def resolve_input_path() -> Path:
    if INPUT_PATH.exists():
        return INPUT_PATH
    if FALLBACK_INPUT_PATH.exists():
        return FALLBACK_INPUT_PATH
    raise FileNotFoundError(
        f"Input CSV not found. Tried {INPUT_PATH} and {FALLBACK_INPUT_PATH}."
    )


def add_distribution_metrics(df: pd.DataFrame) -> pd.DataFrame:
    prob_cols = ["p1", "p2", "p3", "p4"]
    out = df.copy()

    probs = out[prob_cols].to_numpy(dtype=float)

    out["sharpness"] = ((probs - 0.25) ** 2).sum(axis=1)

    eps = 1e-12
    out["entropy"] = -(probs * np.log(probs + eps)).sum(axis=1)

    out["max_prob"] = probs.max(axis=1)
    out["p1_p4_spread"] = out["p1"] - out["p4"]

    return out


def add_state_hash_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    if "state_hash" in df.columns:
        return df
    missing = [col for col in STATE_COLUMNS if col not in df.columns]
    if missing:
        return df

    out = df.copy()
    out["state_hash"] = out[STATE_COLUMNS].astype(str).agg("|".join, axis=1)
    return out


def make_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby("kyoku")
        .agg(
            rows=("kyoku", "size"),
            states=("state_hash", "nunique") if "state_hash" in df.columns else ("kyoku", "size"),
            p1_mean=("p1", "mean"),
            p1_std=("p1", "std"),
            p1_var=("p1", "var"),
            p4_mean=("p4", "mean"),
            p4_std=("p4", "std"),
            p4_var=("p4", "var"),
            p2_std=("p2", "std"),
            p3_std=("p3", "std"),
            sharpness_mean=("sharpness", "mean"),
            sharpness_std=("sharpness", "std"),
            entropy_mean=("entropy", "mean"),
            entropy_std=("entropy", "std"),
            max_prob_mean=("max_prob", "mean"),
            score_range_mean=("score_range", "mean"),
            score_range_std=("score_range", "std"),
        )
        .reset_index()
    )
    summary["kyoku_label"] = summary["kyoku"].map(KYOKU_LABELS)
    summary["prob_std_mean"] = summary[["p1_std", "p2_std", "p3_std", "p4_std"]].mean(axis=1)
    return summary


def plot_bar(summary: pd.DataFrame, y_cols: list[str], title: str, ylabel: str, filename: str) -> None:
    x = np.arange(len(summary))
    width = 0.8 / len(y_cols)

    plt.figure(figsize=(11, 6))

    for i, col in enumerate(y_cols):
        offset = (i - (len(y_cols) - 1) / 2) * width
        plt.bar(x + offset, summary[col], width=width, label=col)

    plt.xticks(x, summary["kyoku_label"], rotation=30)
    plt.title(title)
    plt.xlabel("Round")
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_DIR / filename, dpi=160)
    plt.close()


def plot_line(summary: pd.DataFrame, y_col: str, title: str, ylabel: str, filename: str) -> None:
    plt.figure(figsize=(10, 6))
    plt.plot(summary["kyoku_label"], summary[y_col], marker="o")
    plt.title(title)
    plt.xlabel("Round")
    plt.ylabel(ylabel)
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(OUT_DIR / filename, dpi=160)
    plt.close()


def plot_box_by_kyoku(df: pd.DataFrame, value_col: str, title: str, ylabel: str, filename: str) -> None:
    labels = []
    values = []

    for kyoku in sorted(df["kyoku"].unique()):
        labels.append(KYOKU_LABELS.get(kyoku, str(kyoku)))
        values.append(df.loc[df["kyoku"] == kyoku, value_col].to_numpy())

    plt.figure(figsize=(11, 6))
    plt.boxplot(values, tick_labels=labels, showfliers=False)
    plt.title(title)
    plt.xlabel("Round")
    plt.ylabel(ylabel)
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(OUT_DIR / filename, dpi=160)
    plt.close()


def plot_scatter(df: pd.DataFrame, x_col: str, y_col: str, title: str, filename: str) -> None:
    plt.figure(figsize=(10, 6))

    for kyoku in sorted(df["kyoku"].unique()):
        part = df[df["kyoku"] == kyoku]
        if len(part) > 1000:
            part = part.sample(1000, random_state=42)
        plt.scatter(part[x_col], part[y_col], s=8, alpha=0.35, label=KYOKU_LABELS.get(kyoku, str(kyoku)))

    plt.title(title)
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.legend(markerscale=2, fontsize=8)
    plt.tight_layout()
    plt.savefig(OUT_DIR / filename, dpi=160)
    plt.close()


def main() -> None:
    input_path = resolve_input_path()
    df = pd.read_csv(input_path)
    df = add_state_hash_if_needed(df)
    df = add_distribution_metrics(df)

    summary = make_summary(df)
    summary.to_csv(OUT_DIR / "kyoku_variance_summary.csv", index=False)

    plot_bar(
        summary,
        ["p1_std", "p2_std", "p3_std", "p4_std"],
        "Rank Probability Standard Deviation by Round",
        "Standard deviation",
        "rank_probability_std_by_round.png",
    )

    plot_line(
        summary,
        "sharpness_mean",
        "Mean Sharpness by Round",
        "Mean sharpness",
        "mean_sharpness_by_round.png",
    )

    plot_line(
        summary,
        "entropy_mean",
        "Mean Entropy by Round",
        "Mean entropy",
        "mean_entropy_by_round.png",
    )

    plot_box_by_kyoku(
        df,
        "p1",
        "P1 Distribution by Round",
        "P1",
        "p1_distribution_by_round.png",
    )

    plot_box_by_kyoku(
        df,
        "p4",
        "P4 Distribution by Round",
        "P4",
        "p4_distribution_by_round.png",
    )

    plot_box_by_kyoku(
        df,
        "sharpness",
        "Sharpness Distribution by Round",
        "Sharpness",
        "sharpness_distribution_by_round.png",
    )

    plot_box_by_kyoku(
        df,
        "score_range",
        "Score Range Distribution by Round",
        "Score range",
        "score_range_distribution_by_round.png",
    )

    plot_scatter(
        df,
        "score_range",
        "sharpness",
        "Sharpness vs Score Range by Round",
        "sharpness_vs_score_range.png",
    )

    by_rank = (
        df.groupby(["kyoku", "current_rank"])
        .agg(
            rows=("kyoku", "size"),
            p1_std=("p1", "std"),
            p4_std=("p4", "std"),
            sharpness_mean=("sharpness", "mean"),
            entropy_mean=("entropy", "mean"),
        )
        .reset_index()
    )
    by_rank.to_csv(OUT_DIR / "kyoku_current_rank_variance_summary.csv", index=False)

    print(summary.sort_values("sharpness_mean", ascending=False))
    print(f"Saved outputs to: {OUT_DIR}")


if __name__ == "__main__":
    main()
