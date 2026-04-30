from __future__ import annotations

"""Mermaid ソースを SVG に再生成する補助スクリプト。"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "docs" / "graphs" / "src"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "graphs" / "generated"


def _iter_graph_sources(input_dir: Path) -> list[Path]:
    """入力ディレクトリから Mermaid ソースを列挙する。"""

    graph_files = sorted(input_dir.glob("*.mmd"))
    if not graph_files:
        raise FileNotFoundError(f"Mermaid ソースが見つかりません: {input_dir}")
    return graph_files


def _find_mermaid_command() -> list[str] | None:
    """ローカルの `mmdc` を優先し、無ければ `npx` 経由へフォールバックする。"""

    if shutil.which("mmdc"):
        return ["mmdc"]
    node_runner = shutil.which("npx.cmd") or shutil.which("npx")
    if node_runner:
        return [node_runner, "-y", "@mermaid-js/mermaid-cli"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="docs/graphs/src 配下の Mermaid 図を SVG に再生成します。",
    )
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help="Mermaid ソース (*.mmd) の配置先。",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="生成した SVG の出力先。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実行計画だけ表示し、Mermaid CLI は呼び出しません。",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"入力ディレクトリが見つかりません: {input_dir}")

    graph_files = _iter_graph_sources(input_dir)
    # 出力先は無ければ作る。既存 SVG は同名で上書き再生成する。
    output_dir.mkdir(parents=True, exist_ok=True)

    for graph_file in graph_files:
        output_file = output_dir / f"{graph_file.stem}.svg"
        print(f"{graph_file} -> {output_file}")

    if args.dry_run:
        print(f"ドライラン完了: {len(graph_files)} 件の図を確認しました。")
        return 0

    command_prefix = _find_mermaid_command()
    if command_prefix is None:
        print(
            "Mermaid CLI が見つかりません。`mmdc` または Node.js + npx を用意してください。",
            file=sys.stderr,
        )
        return 1

    for graph_file in graph_files:
        output_file = output_dir / f"{graph_file.stem}.svg"
        # 1 ファイルずつ独立に生成し、失敗時にどの図で止まったか追いやすくする。
        command = [*command_prefix, "-i", str(graph_file), "-o", str(output_file)]
        print(f"生成中: {graph_file.name}")
        subprocess.run(command, check=True)

    print(f"SVG を {len(graph_files)} 件生成しました: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
