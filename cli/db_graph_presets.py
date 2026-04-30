from __future__ import annotations

from pathlib import Path
from typing import Sequence

from db_graph_framework import (
    AnalysisDefinition,
    DatasetDefinition,
    GraphDefinition,
    NumericFieldFilter,
    THINKING_TIME_MAX_MS,
    THINKING_TIME_MIN_MS,
    iter_discard_fact_rows,
    is_truthy_flag,
    parse_optional_float,
    parse_optional_int,
)


def build_ryanmen_fixed_dataset(
    db_dir: Path,
    excluded_players: Sequence[str],
) -> list[dict[str, object]]:
    """両面固定打牌だけを `discard_fact` から抽出する。"""

    excluded_name_set = {str(name).strip() for name in excluded_players if str(name).strip()}
    records: list[dict[str, object]] = []
    for row in iter_discard_fact_rows(db_dir):
        if not is_truthy_flag(row.get("ryanmen_fixed_flag")):
            continue
        player_name = str(row.get("player_name", "")).strip()
        if not player_name or player_name in excluded_name_set:
            continue
        records.append(
            {
                "discard_id": str(row.get("discard_id", "")).strip(),
                "player_name": player_name,
                "thinking_time_ms": parse_optional_float(row.get("thinking_time_ms")),
                "shanten_after_discard": parse_optional_int(row.get("shanten_after_discard")),
                "ryanmen_fixed_flag": True,
            }
        )
    return records


# DATASET_DEFINITIONS の対応表。
DATASET_DEFINITIONS: dict[str, DatasetDefinition] = {
    "ryanmen_fixed_discards": DatasetDefinition(
        name="ryanmen_fixed_discards",
        description="両面固定打牌だけを集めた分析用データセット。",
        build_records=build_ryanmen_fixed_dataset,
    ),
}


# THINKING_TIME_WINDOW の並びを定義する。
THINKING_TIME_WINDOW = (
    NumericFieldFilter(
        field_name="thinking_time_ms",
        min_exclusive=THINKING_TIME_MIN_MS,
        max_exclusive=THINKING_TIME_MAX_MS,
    ),
)


# GRAPH_DEFINITIONS の対応表。
GRAPH_DEFINITIONS: dict[str, GraphDefinition] = {
    "ryanmen_fixed_thinking_time_vs_shanten": GraphDefinition(
        name="ryanmen_fixed_thinking_time_vs_shanten",
        description="両面固定打牌の思考時間とシャンテン数の散布図。",
        dataset_name="ryanmen_fixed_discards",
        kind="scatter",
        x_field="shanten_after_discard",
        y_field="thinking_time_ms",
        output_filename="thinking_time_vs_shanten_scatter.svg",
        title="両面固定打牌のシャンテン数と思考時間",
        subtitle="discard_fact / ryanmen_fixed_flag=1 / 思考時間は共通外れ値ルールで抽出",
        x_label="shanten_after_discard",
        y_label="thinking_time_ms",
        numeric_filters=THINKING_TIME_WINDOW,
        include_regression=True,
    ),
    "ryanmen_fixed_thinking_time_distribution": GraphDefinition(
        name="ryanmen_fixed_thinking_time_distribution",
        description="両面固定打牌の思考時間分布。",
        dataset_name="ryanmen_fixed_discards",
        kind="histogram",
        x_field="thinking_time_ms",
        output_filename="thinking_time_distribution.svg",
        title="両面固定打牌の思考時間分布",
        subtitle="discard_fact / ryanmen_fixed_flag=1 / 900 < thinking_time_ms < 8000",
        x_label="thinking_time_ms",
        y_label="count",
        numeric_filters=THINKING_TIME_WINDOW,
        histogram_bin_width=500.0,
    ),
    "ryanmen_fixed_shanten_distribution": GraphDefinition(
        name="ryanmen_fixed_shanten_distribution",
        description="両面固定打牌のシャンテン数分布。",
        dataset_name="ryanmen_fixed_discards",
        kind="discrete_bar",
        x_field="shanten_after_discard",
        output_filename="shanten_distribution.svg",
        title="両面固定打牌のシャンテン数分布",
        subtitle="discard_fact / ryanmen_fixed_flag=1 / シャンテン値の件数集計",
        x_label="shanten_after_discard",
        y_label="count",
    ),
}


# ANALYSIS_DEFINITIONS の対応表。
ANALYSIS_DEFINITIONS: dict[str, AnalysisDefinition] = {
    "ryanmen_fixed_analysis": AnalysisDefinition(
        name="ryanmen_fixed_analysis",
        description="両面固定打牌の思考時間とシャンテン数をまとめて見る分析束。",
        graph_names=(
            "ryanmen_fixed_thinking_time_vs_shanten",
            "ryanmen_fixed_thinking_time_distribution",
            "ryanmen_fixed_shanten_distribution",
        ),
        output_subdir="ryanmen_fixed",
    ),
}
