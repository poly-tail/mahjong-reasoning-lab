from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd


DISCARD_FACT_COLUMNS = (
    "discard_id",
    "hanchan_id",
    "room_class_label",
    "player_rel_seat",
    "player_name",
    "tsumogiri_flag",
    "thinking_time_ms",
    "shanten_after_discard",
)
HANCHAN_MASTER_COLUMNS = (
    "hanchan_id",
    "room_class_label",
    "seat0_player_name",
    "seat1_player_name",
    "seat2_player_name",
    "seat3_player_name",
)
HANCHAN_PLAYER_COLUMNS = (
    "seat0_player_name",
    "seat1_player_name",
    "seat2_player_name",
    "seat3_player_name",
)
UNKNOWN_ROOM_CLASS_LABEL = "不明"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_discard_facts(csv_dir: Path) -> pd.DataFrame:
    files = sorted(csv_dir.glob("discard_fact_*.csv"))
    if not files:
        raise FileNotFoundError(f"discard_fact_*.csv not found under {csv_dir}")

    # Read every monthly chunk with the same narrow column set.  The analysis is row-heavy, so
    # avoiding unused JSON hand/context columns keeps memory and parse time predictable.
    frames: list[pd.DataFrame] = []
    for path in files:
        frame = pd.read_csv(
            path,
            usecols=lambda col: col in DISCARD_FACT_COLUMNS,
            low_memory=False,
        )
        frame["source_file"] = path.name
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _read_hanchan_master(csv_dir: Path) -> pd.DataFrame:
    path = csv_dir / "hanchan_master.csv"
    if not path.exists():
        return pd.DataFrame(columns=HANCHAN_MASTER_COLUMNS)
    return pd.read_csv(
        path,
        usecols=lambda col: col in HANCHAN_MASTER_COLUMNS,
        dtype=str,
        low_memory=False,
    )


def _prepare_valid_rows(df: pd.DataFrame, *, min_shanten: int, max_shanten: int) -> pd.DataFrame:
    out = df.copy()
    out["thinking_time_ms"] = pd.to_numeric(out["thinking_time_ms"], errors="coerce")
    out["shanten_after_discard"] = pd.to_numeric(out["shanten_after_discard"], errors="coerce")
    # 0-shanten discards are excluded by the default CLI range. They often represent wait-selection
    # or post-ready decisions and were observed to be a shorter-time exception.
    out = out[
        out["thinking_time_ms"].notna()
        & out["shanten_after_discard"].notna()
        & (out["thinking_time_ms"] >= 0)
        & out["shanten_after_discard"].between(min_shanten, max_shanten)
    ].copy()
    out["shanten_after_discard"] = out["shanten_after_discard"].astype(int)
    out["thinking_s"] = out["thinking_time_ms"] / 1000.0
    out["log1p_thinking_s"] = np.log1p(out["thinking_s"].to_numpy(dtype=float))
    out["player_name"] = out["player_name"].fillna("(unknown)").astype(str)
    out["room_class_label"] = out["room_class_label"].fillna("").astype(str)
    return out


def _player_table_affiliations(hanchan_master: pd.DataFrame) -> pd.DataFrame:
    # hanchan_master is the canonical table-affiliation source because it represents the match, not
    # just the subset of discards that survived the later analysis filters.
    if hanchan_master.empty:
        return pd.DataFrame(
            columns=[
                "player_name",
                "hanchan_count",
                "hanchan_room_class_main",
                "hanchan_room_class_main_n",
                "table_affiliation",
                "hanchan_room_class_counts_json",
            ]
        )
    seat_columns = [column for column in HANCHAN_PLAYER_COLUMNS if column in hanchan_master.columns]
    if not seat_columns:
        return pd.DataFrame(
            columns=[
                "player_name",
                "hanchan_count",
                "hanchan_room_class_main",
                "hanchan_room_class_main_n",
                "table_affiliation",
                "hanchan_room_class_counts_json",
            ]
        )

    base = hanchan_master.copy().reset_index().rename(columns={"index": "_hanchan_row_index"})
    if "hanchan_id" not in base.columns:
        base["hanchan_id"] = ""
    if "room_class_label" not in base.columns:
        base["room_class_label"] = ""
    melted = base.melt(
        id_vars=["_hanchan_row_index", "hanchan_id", "room_class_label"],
        value_vars=seat_columns,
        var_name="seat_column",
        value_name="player_name",
    )
    # One hanchan contributes at most once per player even if legacy data contains duplicate rows or
    # repeated import attempts.
    melted["player_name"] = melted["player_name"].fillna("").astype(str).str.strip()
    melted = melted[melted["player_name"] != ""].copy()
    if melted.empty:
        return pd.DataFrame(
            columns=[
                "player_name",
                "hanchan_count",
                "hanchan_room_class_main",
                "hanchan_room_class_main_n",
                "table_affiliation",
                "hanchan_room_class_counts_json",
            ]
        )
    melted["room_class_label"] = melted["room_class_label"].fillna("").astype(str).str.strip()
    melted.loc[melted["room_class_label"] == "", "room_class_label"] = UNKNOWN_ROOM_CLASS_LABEL
    melted["hanchan_id"] = melted["hanchan_id"].fillna("").astype(str).str.strip()
    melted["_hanchan_instance_key"] = np.where(
        melted["hanchan_id"] != "",
        melted["hanchan_id"],
        "row:" + melted["_hanchan_row_index"].astype(str),
    )
    melted = melted.drop_duplicates(["player_name", "_hanchan_instance_key"])

    rows: list[dict[str, object]] = []
    for player_name, group in melted.groupby("player_name", sort=False):
        # Prefer a known room label; if all rows are missing, keep the explicit unknown bucket so
        # the report still shows where the affiliation came from.
        hanchan_count = int(group["_hanchan_instance_key"].nunique())
        room_counts = group["room_class_label"].value_counts()
        known_room_counts = room_counts.drop(index=UNKNOWN_ROOM_CLASS_LABEL, errors="ignore")
        main_room_counts = known_room_counts if len(known_room_counts) else room_counts
        main_room = str(main_room_counts.index[0]) if len(main_room_counts) else ""
        main_count = int(main_room_counts.iloc[0]) if len(main_room_counts) else 0
        rows.append(
            {
                "player_name": player_name,
                "hanchan_count": hanchan_count,
                "hanchan_room_class_main": main_room,
                "hanchan_room_class_main_n": main_count,
                "table_affiliation": (
                    f"{main_room} ({main_count}/{hanchan_count}半荘)"
                    if main_room and hanchan_count > 0
                    else ""
                ),
                "hanchan_room_class_counts_json": json.dumps(
                    {str(k): int(v) for k, v in room_counts.items()},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    return pd.DataFrame(rows)


def _attach_player_table_affiliations(
    summary: pd.DataFrame,
    hanchan_master: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return summary
    affiliations = _player_table_affiliations(hanchan_master)
    out = summary.merge(affiliations, on="player_name", how="left")
    for column, default_value in (
        ("hanchan_count", 0),
        ("hanchan_room_class_main", ""),
        ("hanchan_room_class_main_n", 0),
        ("table_affiliation", ""),
        ("hanchan_room_class_counts_json", "{}"),
    ):
        if column not in out.columns:
            out[column] = default_value
    out["hanchan_count"] = pd.to_numeric(out["hanchan_count"], errors="coerce").fillna(0).astype(int)
    out["hanchan_room_class_main_n"] = (
        pd.to_numeric(out["hanchan_room_class_main_n"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    for column in ("hanchan_room_class_main", "table_affiliation", "hanchan_room_class_counts_json"):
        out[column] = out[column].fillna("").astype(str)
    missing_affiliation = out["table_affiliation"].str.strip() == ""
    # Fallback to discard-row room labels only for players missing from hanchan_master.  Mixing both
    # sources would over-weight players with more retained discard rows.
    fallback_room = out.get("room_class_main", pd.Series("", index=out.index)).fillna("").astype(str).str.strip()
    out.loc[missing_affiliation & (fallback_room != ""), "table_affiliation"] = (
        fallback_room[missing_affiliation & (fallback_room != "")]
        + " (discard rows)"
    )
    return out


def _safe_corr(series_x: pd.Series, series_y: pd.Series, *, method: str) -> float:
    if len(series_x) < 3 or series_x.nunique(dropna=True) < 2 or series_y.nunique(dropna=True) < 2:
        return float("nan")
    return float(series_x.corr(series_y, method=method))


def _player_summary(valid: pd.DataFrame, *, min_samples: int, min_bins: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for player_name, group in valid.groupby("player_name", sort=False):
        # Median-by-shanten is more robust than mean for thinking time because pauses and UI lag can
        # create long right tails.
        shanten_counts = group["shanten_after_discard"].value_counts().sort_index()
        if len(group) < min_samples or len(shanten_counts) < min_bins:
            continue
        median_by_shanten = group.groupby("shanten_after_discard")["thinking_s"].median().sort_index()
        p90_by_shanten = group.groupby("shanten_after_discard")["thinking_s"].quantile(0.90).sort_index()
        x = median_by_shanten.index.to_numpy(dtype=float)
        y = median_by_shanten.to_numpy(dtype=float)
        slope = float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else float("nan")
        med_range = float(np.nanmax(y) - np.nanmin(y)) if len(y) else float("nan")
        med_mean = float(np.nanmean(y)) if len(y) else float("nan")
        med_cv = float(np.nanstd(y, ddof=0) / med_mean) if med_mean > 0 else float("nan")

        def median_delta(left_shanten: int, right_shanten: int) -> float:
            left = median_by_shanten.get(left_shanten, np.nan)
            right = median_by_shanten.get(right_shanten, np.nan)
            if pd.isna(left) or pd.isna(right):
                return float("nan")
            return float(left - right)

        # In the default 1..3 report, this is the clearest per-player effect size:
        # positive means 1-shanten decisions take longer than 3-shanten decisions.
        shanten_1_minus_3 = median_delta(1, 3)
        room_counts = group["room_class_label"].value_counts()
        rows.append(
            {
                "player_name": player_name,
                "n": int(len(group)),
                "room_class_main": str(room_counts.index[0]) if len(room_counts) else "",
                "room_class_main_n": int(room_counts.iloc[0]) if len(room_counts) else 0,
                "shanten_bins": int(len(shanten_counts)),
                "spearman_shanten_vs_thinking_s": _safe_corr(
                    group["shanten_after_discard"], group["thinking_s"], method="spearman"
                ),
                "spearman_shanten_vs_log1p_thinking_s": _safe_corr(
                    group["shanten_after_discard"], group["log1p_thinking_s"], method="spearman"
                ),
                "pearson_shanten_vs_log1p_thinking_s": _safe_corr(
                    group["shanten_after_discard"], group["log1p_thinking_s"], method="pearson"
                ),
                "thinking_median_s": float(group["thinking_s"].median()),
                "thinking_mean_s": float(group["thinking_s"].mean()),
                "thinking_p90_s": float(group["thinking_s"].quantile(0.90)),
                "median_s_slope_per_shanten": slope,
                "median_s_range_across_shanten": med_range,
                "median_s_cv_across_shanten": med_cv,
                "near_ready_delta_s": shanten_1_minus_3,
                "median_s_1_minus_3_s": shanten_1_minus_3,
                "median_s_1_minus_2_s": median_delta(1, 2),
                "median_s_2_minus_3_s": median_delta(2, 3),
                "n_by_shanten_json": json.dumps(
                    {int(k): int(v) for k, v in shanten_counts.items()},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "median_s_by_shanten_json": json.dumps(
                    {int(k): round(float(v), 3) for k, v in median_by_shanten.items()},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "p90_s_by_shanten_json": json.dumps(
                    {int(k): round(float(v), 3) for k, v in p90_by_shanten.items()},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    return summary.sort_values(
        ["n", "player_name"],
        ascending=[False, True],
    ).reset_index(drop=True)


def _player_shanten_medians(valid: pd.DataFrame, qualified: pd.DataFrame) -> pd.DataFrame:
    names = set(qualified["player_name"])
    data = valid[valid["player_name"].isin(names)]
    return (
        data.groupby(["player_name", "shanten_after_discard"])["thinking_s"]
        .median()
        .unstack("shanten_after_discard")
        .sort_index()
    )


def _set_plot_style() -> None:
    font_candidates: list[str] = ["DejaVu Sans"]
    for font_path in (
        Path(r"C:\Windows\Fonts\NotoSansJP-VF.ttf"),
        Path(r"C:\Windows\Fonts\meiryo.ttc"),
        Path(r"C:\Windows\Fonts\YuGothR.ttc"),
    ):
        if not font_path.exists():
            continue
        try:
            font_manager.fontManager.addfont(str(font_path))
            font_name = font_manager.FontProperties(fname=str(font_path)).get_name()
        except RuntimeError:
            continue
        if font_name:
            font_candidates.insert(0, font_name)

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#fbfdff",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#0f172a",
            "axes.titlecolor": "#0f172a",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "grid.color": "#e2e8f0",
            "font.family": font_candidates,
            "axes.titleweight": "bold",
        }
    )


def _save_correlation_ranking(summary: pd.DataFrame, out_path: Path, *, top_n: int = 36) -> None:
    plot_df = summary.dropna(subset=["spearman_shanten_vs_log1p_thinking_s"]).copy()
    if plot_df.empty:
        return
    plot_df = plot_df.sort_values("spearman_shanten_vs_log1p_thinking_s").head(top_n)
    labels = [
        f"{name} (n={n})"
        for name, n in zip(plot_df["player_name"], plot_df["n"], strict=False)
    ]
    values = plot_df["spearman_shanten_vs_log1p_thinking_s"].to_numpy(dtype=float)
    colors = np.where(values < 0, "#2563eb", "#dc2626")

    fig_h = max(6.0, 0.34 * len(plot_df) + 1.8)
    fig, ax = plt.subplots(figsize=(11, fig_h))
    ax.barh(labels, values, color=colors, alpha=0.88)
    ax.axvline(0, color="#0f172a", linewidth=1)
    ax.grid(axis="x", linestyle="-", linewidth=0.8)
    ax.set_title("Player-wise correlation: shanten 1-3 vs thinking time")
    ax.set_xlabel("Spearman rho, using log1p(thinking seconds)")
    ax.set_ylabel("")
    ax.text(
        0.01,
        0.01,
        "Negative: 1-shanten tends to take longer. Positive: 3-shanten tends to take longer.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        color="#475569",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _save_median_heatmap(medians: pd.DataFrame, summary: pd.DataFrame, out_path: Path, *, top_n: int = 30) -> None:
    if medians.empty:
        return
    order = summary.sort_values("n", ascending=False)["player_name"].head(top_n)
    matrix = medians.reindex(order).dropna(how="all")
    if matrix.empty:
        return

    fig_h = max(6.0, 0.34 * len(matrix) + 1.8)
    fig, ax = plt.subplots(figsize=(10, fig_h))
    values = matrix.to_numpy(dtype=float)
    masked = np.ma.masked_invalid(values)
    image = ax.imshow(masked, aspect="auto", cmap="viridis", vmin=0, vmax=np.nanpercentile(values, 95))
    ax.set_title("Median thinking time by player and shanten 1-3")
    ax.set_xlabel("shanten_after_discard")
    ax.set_ylabel("player")
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels([str(int(c)) for c in matrix.columns])
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for row_idx in range(matrix.shape[0]):
        for col_idx in range(matrix.shape[1]):
            value = matrix.iat[row_idx, col_idx]
            if pd.isna(value):
                continue
            ax.text(col_idx, row_idx, f"{value:.1f}", ha="center", va="center", fontsize=7, color="white")
    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("median seconds")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _save_profile_lines(medians: pd.DataFrame, summary: pd.DataFrame, out_path: Path, *, highlighted_n: int = 12) -> None:
    if medians.empty:
        return
    fig, ax = plt.subplots(figsize=(11, 6.8))
    x = np.array([int(c) for c in medians.columns], dtype=float)
    for _, row in medians.iterrows():
        y = row.to_numpy(dtype=float)
        if np.isnan(y).all():
            continue
        ax.plot(x, y, color="#cbd5e1", alpha=0.42, linewidth=1.0)

    candidates = summary.dropna(subset=["spearman_shanten_vs_log1p_thinking_s"]).copy()
    highlight_names = pd.concat(
        [
            candidates.sort_values("spearman_shanten_vs_log1p_thinking_s").head(highlighted_n // 2),
            candidates.sort_values("spearman_shanten_vs_log1p_thinking_s", ascending=False).head(highlighted_n // 2),
        ]
    )["player_name"].drop_duplicates()
    palette = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2"]
    for idx, name in enumerate(highlight_names):
        if name not in medians.index:
            continue
        row = medians.loc[name]
        ax.plot(
            x,
            row.to_numpy(dtype=float),
            marker="o",
            linewidth=2.0,
            markersize=4,
            color=palette[idx % len(palette)],
            label=str(name),
        )

    overall = medians.median(axis=0, skipna=True)
    ax.plot(
        x,
        overall.to_numpy(dtype=float),
        color="#0f172a",
        linewidth=3.0,
        marker="s",
        label="player median of medians",
    )
    ax.grid(True, axis="y")
    ax.set_title("Per-player median thinking profile, shanten 1-3")
    ax.set_xlabel("shanten_after_discard")
    ax.set_ylabel("median thinking seconds")
    ax.set_xticks(x)
    ax.legend(loc="upper right", fontsize=8, ncol=2, frameon=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _save_player_variability_boxplot(medians: pd.DataFrame, out_path: Path) -> None:
    if medians.empty:
        return
    columns = list(medians.columns)
    values = [medians[col].dropna().to_numpy(dtype=float) for col in columns]
    fig, ax = plt.subplots(figsize=(10, 6.4))
    ax.boxplot(
        values,
        tick_labels=[str(int(col)) for col in columns],
        patch_artist=True,
        medianprops={"color": "#0f172a", "linewidth": 1.6},
        boxprops={"facecolor": "#dbeafe", "edgecolor": "#2563eb"},
        whiskerprops={"color": "#64748b"},
        capprops={"color": "#64748b"},
        flierprops={"marker": "o", "markersize": 3, "markerfacecolor": "#f97316", "markeredgecolor": "#f97316", "alpha": 0.55},
    )
    rng = np.random.default_rng(20260524)
    for idx, arr in enumerate(values, start=1):
        if len(arr) == 0:
            continue
        jitter = rng.normal(loc=idx, scale=0.035, size=len(arr))
        ax.scatter(jitter, arr, s=12, color="#334155", alpha=0.38, linewidth=0)
    ax.grid(True, axis="y")
    ax.set_title("Player-to-player variability of median thinking time, shanten 1-3")
    ax.set_xlabel("shanten_after_discard")
    ax.set_ylabel("per-player median thinking seconds")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _save_sample_balance(summary: pd.DataFrame, out_path: Path, *, top_n: int = 30) -> None:
    if summary.empty:
        return
    plot_df = summary.sort_values("n", ascending=False).head(top_n)
    fig, ax = plt.subplots(figsize=(11, 6.8))
    ax.bar(plot_df["player_name"], plot_df["n"], color="#0f766e", alpha=0.88)
    ax.set_yscale("log")
    ax.grid(True, axis="y")
    ax.set_title("Sample count by player")
    ax.set_xlabel("player")
    ax.set_ylabel("valid discard rows, log scale")
    ax.tick_params(axis="x", rotation=65)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _variability_summary(medians: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for shanten, series in medians.items():
        values = series.dropna()
        if values.empty:
            continue
        rows.append(
            {
                "shanten_after_discard": int(shanten),
                "player_count": int(values.count()),
                "player_median_of_medians_s": float(values.median()),
                "player_mean_of_medians_s": float(values.mean()),
                "player_sd_of_medians_s": float(values.std(ddof=0)),
                "player_iqr_of_medians_s": float(values.quantile(0.75) - values.quantile(0.25)),
                "player_min_median_s": float(values.min()),
                "player_max_median_s": float(values.max()),
            }
        )
    return pd.DataFrame(rows)


def _fmt(value: object, digits: int = 3) -> str:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return ""
    if not np.isfinite(val):
        return ""
    return f"{val:.{digits}f}"


def _report_lightbox_css() -> str:
    return """
    figure img { cursor: zoom-in; }
    .image-lightbox[hidden] { display: none; }
    .image-lightbox {
      position: fixed;
      inset: 0;
      z-index: 1000;
      display: grid;
      place-items: center;
      padding: 28px;
      background: rgba(15, 23, 42, 0.86);
    }
    .image-lightbox img {
      max-width: min(96vw, 1480px);
      max-height: 86vh;
      width: auto;
      height: auto;
      background: white;
      border-radius: 6px;
      box-shadow: 0 20px 80px rgba(0, 0, 0, 0.42);
      cursor: zoom-out;
    }
    .image-lightbox button {
      position: fixed;
      top: 14px;
      right: 18px;
      width: 40px;
      height: 40px;
      border: 1px solid rgba(255, 255, 255, 0.52);
      border-radius: 999px;
      color: white;
      background: rgba(15, 23, 42, 0.72);
      font-size: 24px;
      line-height: 1;
      cursor: pointer;
    }
    .image-lightbox-caption {
      position: fixed;
      left: 24px;
      right: 24px;
      bottom: 16px;
      color: white;
      text-align: center;
      font-size: 13px;
    }"""


def _report_lightbox_html() -> str:
    return """
  <div class="image-lightbox" id="image-lightbox" hidden>
    <button type="button" id="image-lightbox-close" aria-label="Close">&times;</button>
    <img id="image-lightbox-img" alt="">
    <div class="image-lightbox-caption" id="image-lightbox-caption"></div>
  </div>
  <script>
    (() => {
      const lightbox = document.getElementById("image-lightbox");
      const lightboxImage = document.getElementById("image-lightbox-img");
      const caption = document.getElementById("image-lightbox-caption");
      const closeButton = document.getElementById("image-lightbox-close");

      const close = () => {
        lightbox.hidden = true;
        lightboxImage.removeAttribute("src");
        caption.textContent = "";
      };

      const open = (image) => {
        lightboxImage.src = image.currentSrc || image.src;
        lightboxImage.alt = image.alt || "";
        const figureCaption = image.closest("figure")?.querySelector("figcaption");
        caption.textContent = figureCaption?.textContent || image.alt || "";
        lightbox.hidden = false;
        closeButton.focus();
      };

      document.querySelectorAll("figure img").forEach((image) => {
        image.tabIndex = 0;
        image.addEventListener("click", () => open(image));
        image.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") {
            return;
          }
          event.preventDefault();
          open(image);
        });
      });
      closeButton.addEventListener("click", close);
      lightbox.addEventListener("click", (event) => {
        if (event.target === lightbox || event.target === lightboxImage) {
          close();
        }
      });
      document.addEventListener("keydown", (event) => {
        if (!lightbox.hidden && event.key === "Escape") {
          close();
        }
      });
    })();
  </script>"""


def _write_html_report_legacy(
    out_dir: Path,
    *,
    source_files: list[str],
    all_rows: int,
    valid_rows: int,
    min_samples: int,
    max_shanten: int,
    summary: pd.DataFrame,
    variability: pd.DataFrame,
) -> None:
    corr = summary["spearman_shanten_vs_log1p_thinking_s"].dropna() if not summary.empty else pd.Series(dtype=float)
    strongest_negative = summary.sort_values("spearman_shanten_vs_log1p_thinking_s").head(8)
    strongest_positive = summary.sort_values("spearman_shanten_vs_log1p_thinking_s", ascending=False).head(8)
    most_variable = summary.sort_values("median_s_range_across_shanten", ascending=False).head(10)

    def table_html(frame: pd.DataFrame, columns: list[str]) -> str:
        if frame.empty:
            return "<p>No rows.</p>"
        rows = []
        rows.append("<table><thead><tr>" + "".join(f"<th>{html.escape(col)}</th>" for col in columns) + "</tr></thead><tbody>")
        for _, row in frame[columns].iterrows():
            rows.append("<tr>")
            for col in columns:
                value = row[col]
                if isinstance(value, float):
                    text = _fmt(value, 3)
                else:
                    text = str(value)
                rows.append(f"<td>{html.escape(text)}</td>")
            rows.append("</tr>")
        rows.append("</tbody></table>")
        return "".join(rows)

    lightbox_css = _report_lightbox_css()
    lightbox_html = _report_lightbox_html()

    html_text = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>思考時間 x シャンテン数 プレイヤー別分析</title>
  <style>
    body {{ font-family: "Yu Gothic UI", Meiryo, system-ui, sans-serif; margin: 24px; color: #0f172a; background: #f8fafc; }}
    h1 {{ font-size: 24px; margin: 0 0 12px; }}
    h2 {{ font-size: 18px; margin: 28px 0 10px; }}
    p, li {{ line-height: 1.6; }}
    .note {{ color: #475569; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; align-items: start; }}
    figure {{ margin: 0; padding: 12px; background: white; border: 1px solid #dbe3ef; border-radius: 8px; }}
    figcaption {{ color: #475569; font-size: 13px; margin-top: 8px; }}
    img {{ display: block; max-width: 100%; height: auto; }}
    table {{ border-collapse: collapse; background: white; margin: 8px 0 20px; font-size: 13px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 6px 8px; text-align: right; }}
    th {{ background: #e2e8f0; }}
    td:first-child, th:first-child {{ text-align: left; }}
    code {{ font-family: Consolas, monospace; background: #eef2ff; padding: 1px 4px; border-radius: 4px; }}
{lightbox_css}
  </style>
</head>
<body>
  <h1>思考時間 x シャンテン数 プレイヤー別分析</h1>
  <p class="note">source_files={html.escape(', '.join(source_files))} / hanchan_master=csv_db/hanchan_master.csv / all_rows={all_rows} / valid_rows={valid_rows} / qualified_players={len(summary)} / min_samples={min_samples} / shanten=0..{max_shanten}</p>
  <h2>見方</h2>
  <ul>
    <li>相関は <code>shanten_after_discard</code> と <code>log1p(thinking seconds)</code> の Spearman ρ。負なら「シャンテン数が低いほど長考寄り」、正なら「シャンテン数が高いほど長考寄り」。</li>
    <li>思考時間は外れ値が強いので、プレイヤープロファイルは平均ではなく中央値を主に見ています。</li>
    <li>プレイヤー別比較はサンプル数 {min_samples} 件以上、かつシャンテン種類が複数あるプレイヤーだけに絞っています。</li>
  </ul>
  <h2>全体サマリ</h2>
  <ul>
    <li>プレイヤー別 Spearman ρ: mean={_fmt(corr.mean())}, sd={_fmt(corr.std(ddof=0))}, min={_fmt(corr.min())}, median={_fmt(corr.median())}, max={_fmt(corr.max())}</li>
    <li>ρ のIQR: {_fmt(corr.quantile(0.75) - corr.quantile(0.25))}</li>
  </ul>
  <div class="grid">
    <figure><img src="player_correlation_ranking.png" alt="Player correlation ranking"><figcaption>プレイヤー別の相関ランキング。左に長いほど低シャンテンで長考しやすい傾向。</figcaption></figure>
    <figure><img src="player_shanten_median_heatmap.png" alt="Player shanten median heatmap"><figcaption>サンプル上位プレイヤーの、シャンテン別中央値秒。</figcaption></figure>
    <figure><img src="player_shanten_profile_lines.png" alt="Player shanten profile lines"><figcaption>プレイヤーごとの中央値ライン。灰色は全対象、色線は相関の極端なプレイヤー。</figcaption></figure>
    <figure><img src="player_variability_boxplot.png" alt="Player variability boxplot"><figcaption>シャンテン別に見たプレイヤー間の中央値のバラつき。</figcaption></figure>
    <figure><img src="player_sample_balance.png" alt="Player sample balance"><figcaption>サンプル数の偏り。ログスケール。</figcaption></figure>
  </div>
  <h2>負の相関が強いプレイヤー</h2>
  {table_html(strongest_negative, ["player_name", "table_affiliation", "n", "hanchan_count", "spearman_shanten_vs_log1p_thinking_s", "thinking_median_s", "median_s_range_across_shanten", "near_ready_delta_s"])}
  <h2>正の相関が強いプレイヤー</h2>
  {table_html(strongest_positive, ["player_name", "table_affiliation", "n", "hanchan_count", "spearman_shanten_vs_log1p_thinking_s", "thinking_median_s", "median_s_range_across_shanten", "near_ready_delta_s"])}
  <h2>シャンテン別中央値の起伏が大きいプレイヤー</h2>
  {table_html(most_variable, ["player_name", "table_affiliation", "n", "hanchan_count", "median_s_range_across_shanten", "median_s_cv_across_shanten", "spearman_shanten_vs_log1p_thinking_s", "median_s_by_shanten_json"])}
  <h2>プレイヤー間バラつき</h2>
  {table_html(variability, ["shanten_after_discard", "player_count", "player_median_of_medians_s", "player_sd_of_medians_s", "player_iqr_of_medians_s", "player_min_median_s", "player_max_median_s"])}
{lightbox_html}
</body>
</html>
"""
    (out_dir / "index.html").write_text(html_text, encoding="utf-8")


def _write_html_report(
    out_dir: Path,
    *,
    source_files: list[str],
    all_rows: int,
    valid_rows: int,
    min_samples: int,
    min_shanten: int,
    max_shanten: int,
    summary: pd.DataFrame,
    variability: pd.DataFrame,
) -> None:
    corr_column = "spearman_shanten_vs_log1p_thinking_s"
    corr = (
        summary[corr_column].dropna()
        if not summary.empty and corr_column in summary.columns
        else pd.Series(dtype=float)
    )
    strongest_negative = (
        summary.sort_values(corr_column).head(8)
        if not summary.empty and corr_column in summary.columns
        else pd.DataFrame()
    )
    strongest_positive = (
        summary.sort_values(corr_column, ascending=False).head(8)
        if not summary.empty and corr_column in summary.columns
        else pd.DataFrame()
    )
    most_variable = (
        summary.sort_values("median_s_range_across_shanten", ascending=False).head(10)
        if not summary.empty and "median_s_range_across_shanten" in summary.columns
        else pd.DataFrame()
    )

    def table_html(frame: pd.DataFrame, columns: list[str]) -> str:
        if frame.empty:
            return "<p>No rows.</p>"
        rows = [
            "<table><thead><tr>"
            + "".join(f"<th>{html.escape(col)}</th>" for col in columns)
            + "</tr></thead><tbody>"
        ]
        for _, row in frame.iterrows():
            rows.append("<tr>")
            for col in columns:
                value = row[col] if col in row.index else ""
                if isinstance(value, float):
                    text = _fmt(value, 3)
                else:
                    text = str(value)
                rows.append(f"<td>{html.escape(text)}</td>")
            rows.append("</tr>")
        rows.append("</tbody></table>")
        return "".join(rows)

    range_label = f"{min_shanten}..{max_shanten}"
    corr_iqr = corr.quantile(0.75) - corr.quantile(0.25) if not corr.empty else float("nan")
    negative_columns = [
        "player_name",
        "table_affiliation",
        "n",
        "hanchan_count",
        "spearman_shanten_vs_log1p_thinking_s",
        "median_s_1_minus_3_s",
        "median_s_1_minus_2_s",
        "median_s_2_minus_3_s",
        "thinking_median_s",
        "median_s_by_shanten_json",
    ]
    variable_columns = [
        "player_name",
        "table_affiliation",
        "n",
        "hanchan_count",
        "median_s_range_across_shanten",
        "median_s_cv_across_shanten",
        "median_s_1_minus_3_s",
        "spearman_shanten_vs_log1p_thinking_s",
        "median_s_by_shanten_json",
    ]

    lightbox_css = _report_lightbox_css()
    lightbox_html = _report_lightbox_html()

    html_text = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>思考時間 x シャンテン数 プレイヤー別分析</title>
  <style>
    body {{ font-family: "Yu Gothic UI", Meiryo, system-ui, sans-serif; margin: 24px; color: #0f172a; background: #f8fafc; }}
    h1 {{ font-size: 24px; margin: 0 0 12px; }}
    h2 {{ font-size: 18px; margin: 28px 0 10px; }}
    p, li {{ line-height: 1.6; }}
    .note {{ color: #475569; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; align-items: start; }}
    figure {{ margin: 0; padding: 12px; background: white; border: 1px solid #dbe3ef; border-radius: 8px; }}
    figcaption {{ color: #475569; font-size: 13px; margin-top: 8px; }}
    img {{ display: block; max-width: 100%; height: auto; }}
    table {{ border-collapse: collapse; background: white; margin: 8px 0 20px; font-size: 13px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 6px 8px; text-align: right; }}
    th {{ background: #e2e8f0; }}
    td:first-child, th:first-child {{ text-align: left; }}
    code {{ font-family: Consolas, monospace; background: #eef2ff; padding: 1px 4px; border-radius: 4px; }}
{lightbox_css}
  </style>
</head>
<body>
  <h1>思考時間 x シャンテン数 プレイヤー別分析</h1>
  <p class="note">source_files={html.escape(', '.join(source_files))} / hanchan_master=csv_db/hanchan_master.csv / all_rows={all_rows} / analyzed_rows={valid_rows} / qualified_players={len(summary)} / min_samples={min_samples} / shanten={range_label}</p>

  <h2>今回の見方</h2>
  <ul>
    <li>0シャンテンは待ち選択やテンパイ後の処理で少し短くなりやすい例外なので、相関・ランキング・グラフから除外しました。</li>
    <li>分析対象は <code>shanten_after_discard</code> が 1, 2, 3 の行だけです。相関は <code>log1p(thinking seconds)</code> との Spearman ρ で見ています。</li>
    <li>ρ が負なら「1シャンテン側ほど長考」、正なら「3シャンテン側ほど長考」です。<code>median_s_1_minus_3_s</code> は 1シャンテン中央値から3シャンテン中央値を引いた秒数です。</li>
    <li>プレイヤー別比較は、分析範囲内のサンプルが {min_samples} 件以上、かつ 1,2,3 の3種類すべてにデータがあるプレイヤーだけです。</li>
  </ul>

  <h2>全体サマリ</h2>
  <ul>
    <li>プレイヤー別 Spearman ρ: mean={_fmt(corr.mean())}, sd={_fmt(corr.std(ddof=0))}, min={_fmt(corr.min())}, median={_fmt(corr.median())}, max={_fmt(corr.max())}</li>
    <li>ρ のIQR: {_fmt(corr_iqr)}</li>
  </ul>

  <div class="grid">
    <figure><img src="player_correlation_ranking.png" alt="Player correlation ranking"><figcaption>1〜3シャンテンだけで見たプレイヤー別相関。左に長いほど1シャンテン側で長考しやすい。</figcaption></figure>
    <figure><img src="player_shanten_median_heatmap.png" alt="Player shanten median heatmap"><figcaption>サンプル上位プレイヤーの1〜3シャンテン別中央値秒。</figcaption></figure>
    <figure><img src="player_shanten_profile_lines.png" alt="Player shanten profile lines"><figcaption>プレイヤーごとの中央値ライン。太い黒線はプレイヤー中央値の中央値。</figcaption></figure>
    <figure><img src="player_variability_boxplot.png" alt="Player variability boxplot"><figcaption>1〜3シャンテン別に見たプレイヤー間の中央値のバラつき。</figcaption></figure>
    <figure><img src="player_sample_balance.png" alt="Player sample balance"><figcaption>分析対象になったプレイヤーのサンプル数。ログスケール。</figcaption></figure>
  </div>

  <h2>1シャンテン側で長考しやすいプレイヤー</h2>
  {table_html(strongest_negative, negative_columns)}
  <h2>3シャンテン側で長考しやすいプレイヤー</h2>
  {table_html(strongest_positive, negative_columns)}
  <h2>1〜3シャンテン間の起伏が大きいプレイヤー</h2>
  {table_html(most_variable, variable_columns)}
  <h2>プレイヤー間のバラつき</h2>
  {table_html(variability, ["shanten_after_discard", "player_count", "player_median_of_medians_s", "player_sd_of_medians_s", "player_iqr_of_medians_s", "player_min_median_s", "player_max_median_s"])}
{lightbox_html}
</body>
</html>
"""
    (out_dir / "index.html").write_text(html_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze player-wise correlation between thinking time and shanten count."
    )
    parser.add_argument("--csv-dir", type=Path, default=_repo_root() / "csv_db")
    parser.add_argument("--out-dir", type=Path, default=_repo_root() / "reports" / "player_shanten_thinking")
    parser.add_argument("--min-samples", type=int, default=80)
    parser.add_argument("--min-bins", type=int, default=3)
    parser.add_argument("--min-shanten", type=int, default=1)
    parser.add_argument("--max-shanten", type=int, default=3)
    args = parser.parse_args()
    if args.min_shanten > args.max_shanten:
        parser.error("--min-shanten must be <= --max-shanten")

    _set_plot_style()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    raw = _read_discard_facts(args.csv_dir)
    hanchan_master = _read_hanchan_master(args.csv_dir)
    valid = _prepare_valid_rows(raw, min_shanten=args.min_shanten, max_shanten=args.max_shanten)
    summary = _player_summary(valid, min_samples=args.min_samples, min_bins=args.min_bins)
    summary = _attach_player_table_affiliations(summary, hanchan_master)
    medians = _player_shanten_medians(valid, summary) if not summary.empty else pd.DataFrame()
    variability = _variability_summary(medians)

    summary.to_csv(args.out_dir / "player_shanten_thinking_summary.csv", index=False, encoding="utf-8-sig")
    variability.to_csv(args.out_dir / "player_shanten_variability_summary.csv", index=False, encoding="utf-8-sig")
    valid.groupby(["shanten_after_discard"])["thinking_s"].agg(
        n="count",
        mean_s="mean",
        median_s="median",
        p25_s=lambda s: s.quantile(0.25),
        p75_s=lambda s: s.quantile(0.75),
        p90_s=lambda s: s.quantile(0.90),
        p99_s=lambda s: s.quantile(0.99),
    ).reset_index().to_csv(args.out_dir / "overall_shanten_thinking_summary.csv", index=False, encoding="utf-8-sig")

    _save_correlation_ranking(summary, args.out_dir / "player_correlation_ranking.png")
    _save_median_heatmap(medians, summary, args.out_dir / "player_shanten_median_heatmap.png")
    _save_profile_lines(medians, summary, args.out_dir / "player_shanten_profile_lines.png")
    _save_player_variability_boxplot(medians, args.out_dir / "player_variability_boxplot.png")
    _save_sample_balance(summary, args.out_dir / "player_sample_balance.png")

    source_files = sorted({str(name) for name in raw["source_file"].unique()})
    _write_html_report(
        args.out_dir,
        source_files=source_files,
        all_rows=int(len(raw)),
        valid_rows=int(len(valid)),
        min_samples=int(args.min_samples),
        min_shanten=int(args.min_shanten),
        max_shanten=int(args.max_shanten),
        summary=summary,
        variability=variability,
    )
    print(f"wrote {args.out_dir}")
    print(
        f"raw_rows={len(raw)} analyzed_rows={len(valid)} "
        f"qualified_players={len(summary)} shanten={args.min_shanten}..{args.max_shanten}"
    )


if __name__ == "__main__":
    main()
