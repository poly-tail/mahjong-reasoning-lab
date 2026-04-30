from __future__ import annotations

import argparse
from pathlib import Path

from db_graph_framework import DEFAULT_EXCLUDED_PLAYERS, run_analysis_definition
from db_graph_presets import ANALYSIS_DEFINITIONS, DATASET_DEFINITIONS, GRAPH_DEFINITIONS


def _list_presets() -> str:
    """利用できる分析定義の一覧を返す。"""

    lines = ["利用可能な分析定義:"]
    for analysis_name, analysis_definition in sorted(ANALYSIS_DEFINITIONS.items()):
        lines.append(f"- {analysis_name}: {analysis_definition.description}")
    lines.append("")
    lines.append("利用可能なグラフ定義:")
    for graph_name, graph_definition in sorted(GRAPH_DEFINITIONS.items()):
        lines.append(f"- {graph_name}: dataset={graph_definition.dataset_name} / {graph_definition.description}")
    lines.append("")
    lines.append("利用可能なデータセット定義:")
    for dataset_name, dataset_definition in sorted(DATASET_DEFINITIONS.items()):
        lines.append(f"- {dataset_name}: {dataset_definition.description}")
    return "\n".join(lines)


def main() -> None:
    """指定した分析定義を実行して SVG と summary.md を生成する。"""

    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Python で定義したデータセット・軸・グラフ種類の組み合わせから discard_fact グラフを生成する。",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="利用可能なデータセット定義・グラフ定義・分析定義を表示して終了する。",
    )
    parser.add_argument(
        "--analysis",
        default="ryanmen_fixed_analysis",
        help="分析定義名。既定値は ryanmen_fixed_analysis。",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=repo_root / "csv_db",
        help="discard_fact_*.csv を置くディレクトリ。既定値は ./csv_db",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=repo_root / "analysis_output",
        help="出力先ルートディレクトリ。既定値は ./analysis_output",
    )
    parser.add_argument(
        "--exclude-player",
        action="append",
        default=[],
        help="追加で除外する player_name。複数回指定可能。",
    )
    args = parser.parse_args()

    if args.list_presets:
        print(_list_presets())
        return

    if args.analysis not in ANALYSIS_DEFINITIONS:
        raise SystemExit(f"不明な分析定義: {args.analysis}\n\n{_list_presets()}")

    excluded_players = list(DEFAULT_EXCLUDED_PLAYERS)
    for player_name in args.exclude_player:
        normalized = str(player_name).strip()
        if normalized and normalized not in excluded_players:
            excluded_players.append(normalized)

    analysis_definition = ANALYSIS_DEFINITIONS[args.analysis]
    output_dir = args.output_root / analysis_definition.output_subdir
    run_analysis_definition(
        analysis_definition,
        DATASET_DEFINITIONS,
        GRAPH_DEFINITIONS,
        args.db_dir,
        output_dir,
        excluded_players=tuple(excluded_players),
    )
    print(f"[db-graph-analysis] 出力先: {output_dir}")


if __name__ == "__main__":
    main()
