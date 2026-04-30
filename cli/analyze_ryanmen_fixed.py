from __future__ import annotations

import argparse
from pathlib import Path

from db_graph_framework import DEFAULT_EXCLUDED_PLAYERS, run_analysis_definition
from db_graph_presets import ANALYSIS_DEFINITIONS, DATASET_DEFINITIONS, GRAPH_DEFINITIONS


def main() -> None:
    """両面固定分析の既存コマンド互換ラッパー。"""

    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="既定の ryanmen_fixed_analysis を実行して、SVG グラフと summary.md を出力する。",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=repo_root / "csv_db",
        help="discard_fact_*.csv を置くディレクトリ。既定値は ./csv_db",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "analysis_output" / "ryanmen_fixed",
        help="SVG グラフと summary.md の出力先。既定値は ./analysis_output/ryanmen_fixed",
    )
    parser.add_argument(
        "--exclude-player",
        action="append",
        default=[],
        help="追加で除外する player_name。複数回指定可能。",
    )
    args = parser.parse_args()

    excluded_players = list(DEFAULT_EXCLUDED_PLAYERS)
    for player_name in args.exclude_player:
        normalized = str(player_name).strip()
        if normalized and normalized not in excluded_players:
            excluded_players.append(normalized)

    run_analysis_definition(
        ANALYSIS_DEFINITIONS["ryanmen_fixed_analysis"],
        DATASET_DEFINITIONS,
        GRAPH_DEFINITIONS,
        args.db_dir,
        args.output_dir,
        excluded_players=tuple(excluded_players),
    )
    print(f"[ryanmen-fixed-analysis] 出力先: {args.output_dir}")


if __name__ == "__main__":
    main()
