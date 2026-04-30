from __future__ import annotations

import argparse
from pathlib import Path

from db_graph_tool import (
    SUPPORTED_GRAPH_KINDS,
    SUPPORTED_LINE_AGGREGATIONS,
    DEFAULT_EXCLUDED_PLAYERS,
    RuntimeGraphRequest,
    apply_query_pipeline,
    available_field_names,
    run_runtime_graph_request,
    runtime_dataset_definitions,
)


def _dataset_list_text() -> str:
    """利用可能 dataset 一覧を返す。"""

    lines = ["利用可能なデータセット:"]
    for dataset_name, definition in sorted(runtime_dataset_definitions().items()):
        lines.append(f"- {dataset_name}: {definition.description}")
    return "\n".join(lines)


def main() -> None:
    """任意条件で discard_fact グラフを 1 枚出力する。"""

    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description=(
            "DB の列、where 条件、派生列をその場で指定して、散布図・箱ひげ図・線グラフなどを出力する。"
        ),
        epilog=(
            "例:\n"
            "  py -3 cli/plot_db_graph.py --dataset ryanmen_fixed_discards --kind scatter "
            "--x-field shanten_after_discard --y-field thinking_time_ms --include-regression\n"
            "  py -3 cli/plot_db_graph.py --dataset discard_fact_all --kind boxplot "
            "--x-field shanten_after_discard --y-field thinking_time_ms --where \"thinking_time_ms > 900\"\n"
            "  py -3 cli/plot_db_graph.py --dataset discard_fact_all --kind line "
            "--x-field shanten_after_discard --line-aggregation count\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--list-datasets", action="store_true", help="利用可能なデータセット一覧を表示して終了する。")
    parser.add_argument("--list-fields", action="store_true", help="指定 dataset/derive/where 適用後のフィールド一覧を表示して終了する。")
    parser.add_argument("--dataset", default="discard_fact_all", help="データセット名。既定値は discard_fact_all。")
    parser.add_argument("--kind", default="scatter", choices=SUPPORTED_GRAPH_KINDS, help="グラフ種類。")
    parser.add_argument("--x-field", default="", help="X 軸に使うフィールド名。")
    parser.add_argument("--y-field", default="", help="Y 軸に使うフィールド名。不要なグラフでは省略可。")
    parser.add_argument("--where", action="append", default=[], help="where 条件式。複数回指定すると AND になる。")
    parser.add_argument("--derive", action="append", default=[], help="派生列。name=expr 形式で複数回指定可。")
    parser.add_argument("--title", default="", help="グラフタイトル。未指定時は自動。")
    parser.add_argument("--subtitle", default="", help="サブタイトル。未指定時は自動。")
    parser.add_argument("--x-label", default="", help="X 軸ラベル。未指定時は x-field。")
    parser.add_argument("--y-label", default="", help="Y 軸ラベル。未指定時は y-field または count。")
    parser.add_argument("--output-file", type=Path, default=Path(""), help="出力 SVG ファイル。未指定時は既定名で生成。")
    parser.add_argument("--output-root", type=Path, default=repo_root / "analysis_output" / "custom_graphs", help="既定出力先ルート。")
    parser.add_argument("--db-dir", type=Path, default=repo_root / "csv_db", help="discard_fact_*.csv を置くディレクトリ。")
    parser.add_argument("--include-regression", action="store_true", help="scatter / scatter_ci に回帰直線を重ねる。")
    parser.add_argument("--line-aggregation", default="raw", choices=SUPPORTED_LINE_AGGREGATIONS, help="line 用の集計方法。")
    parser.add_argument("--x-bin-width", type=float, default=None, help="numeric X を区間化するビン幅。")
    parser.add_argument("--ci-confidence", type=float, default=0.95, help="scatter_ci の信頼水準。既定値 0.95")
    parser.add_argument("--exclude-player", action="append", default=[], help="追加で除外する player_name。複数回指定可。")
    parser.add_argument(
        "--include-default-excluded-players",
        action="store_true",
        help="既定除外プレイヤー (`パシフィック`, `s6u`) を除外しない。",
    )
    args = parser.parse_args()

    if args.list_datasets:
        print(_dataset_list_text())
        return

    definitions = runtime_dataset_definitions()
    if args.dataset not in definitions:
        raise SystemExit(f"不明なデータセットです: {args.dataset}\n\n{_dataset_list_text()}")

    excluded_players = [] if args.include_default_excluded_players else list(DEFAULT_EXCLUDED_PLAYERS)
    for player_name in args.exclude_player:
        normalized = str(player_name).strip()
        if normalized and normalized not in excluded_players:
            excluded_players.append(normalized)

    if args.list_fields:
        dataset_records = definitions[args.dataset].build_records(args.db_dir, tuple(excluded_players))
        filtered_records = apply_query_pipeline(
            dataset_records,
            derive_specs=tuple(args.derive),
            where_clauses=tuple(args.where),
        )
        print("\n".join(available_field_names(filtered_records)))
        return

    if not args.x_field:
        raise SystemExit("--x-field は必須です。")

    title = args.title or f"{args.kind} / {args.dataset}"
    subtitle = args.subtitle or "discard_fact 条件指定グラフ"
    x_label = args.x_label or args.x_field
    resolved_y_field = args.y_field.strip() or None
    y_label = args.y_label or (resolved_y_field or "count")

    request = RuntimeGraphRequest(
        dataset_name=args.dataset,
        kind=args.kind,
        x_field=args.x_field.strip(),
        y_field=resolved_y_field,
        title=title,
        subtitle=subtitle,
        x_label=x_label,
        y_label=y_label,
        output_path=args.output_file,
        include_regression=args.include_regression,
        line_aggregation=args.line_aggregation,
        x_bin_width=args.x_bin_width,
        ci_confidence=args.ci_confidence,
        where_clauses=tuple(args.where),
        derive_specs=tuple(args.derive),
        excluded_players=tuple(excluded_players),
    )
    generated_graph = run_runtime_graph_request(
        request,
        db_dir=args.db_dir,
        output_root=args.output_root,
    )
    if generated_graph.output_path is None:
        print(f"[plot-db-graph] 未生成: {generated_graph.message}")
        return
    print(f"[plot-db-graph] 出力先: {generated_graph.output_path}")
    print(f"[plot-db-graph] 件数: {generated_graph.sample_count}")
    print(f"[plot-db-graph] メッセージ: {generated_graph.message}")


if __name__ == "__main__":
    main()
