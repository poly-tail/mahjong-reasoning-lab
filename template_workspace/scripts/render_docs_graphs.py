from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "docs" / "graphs" / "src"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "graphs" / "generated"


def _iter_graph_sources(input_dir: Path) -> list[Path]:
    graph_files = sorted(input_dir.glob("*.mmd"))
    if not graph_files:
        raise FileNotFoundError(f"No Mermaid source files found in: {input_dir}")
    return graph_files


def _find_mermaid_command() -> list[str] | None:
    if shutil.which("mmdc"):
        return ["mmdc"]
    node_runner = shutil.which("npx.cmd") or shutil.which("npx")
    if node_runner:
        return [node_runner, "-y", "@mermaid-js/mermaid-cli"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render Mermaid graphs in a cross-platform way.",
    )
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help="Directory that contains *.mmd files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory that receives rendered *.svg files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned render actions without invoking Mermaid CLI.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    graph_files = _iter_graph_sources(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for graph_file in graph_files:
        output_file = output_dir / f"{graph_file.stem}.svg"
        print(f"{graph_file} -> {output_file}")

    if args.dry_run:
        print(f"Dry-run complete. {len(graph_files)} graph(s) listed.")
        return 0

    command_prefix = _find_mermaid_command()
    if command_prefix is None:
        print(
            "Mermaid CLI not found. Install `mmdc` or Node+npx, or run with `--dry-run`.",
            file=sys.stderr,
        )
        return 1

    for graph_file in graph_files:
        output_file = output_dir / f"{graph_file.stem}.svg"
        command = [*command_prefix, "-i", str(graph_file), "-o", str(output_file)]
        print(f"Rendering {graph_file.name}")
        subprocess.run(command, check=True)

    print(f"Rendered {len(graph_files)} graph(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
