import argparse
from pathlib import Path


# DOCS_ROOT の型定義。
DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs" / "requirements"
# CURRENT_FILE の型定義。
CURRENT_FILE = DOCS_ROOT / "current.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="要件定義 (current.md) に機能要件の項目を追記します。"
    )
    parser.add_argument("--req-id", required=True, help="要件 ID (例: REQ-GUI-99)")
    parser.add_argument("--summary", required=True, help="要件の概要")
    parser.add_argument(
        "--details",
        nargs="*",
        default=[],
        help="詳細説明（複数行可、スペース区切り指定）",
    )
    return parser.parse_args()


def inject_requirement(req_id: str, summary: str, details: list[str]) -> None:
    if not CURRENT_FILE.exists():
        raise FileNotFoundError(f"{CURRENT_FILE} が見つかりません。")

    content = CURRENT_FILE.read_text(encoding="utf-8").splitlines()

    try:
        start_idx = content.index("## 6. 機能要件")
        end_idx = content.index("## 7. 非機能要件")
    except ValueError as exc:
        raise RuntimeError("機能要件のセクション境界が見つかりません。") from exc

    entry_lines = [f"- **{req_id}**: {summary}"]
    for detail in details:
        entry_lines.append(f"  - {detail}")

    insertion_point = end_idx
    content = (
        content[:insertion_point]
        + entry_lines
        + [""]  # 空行で区切る
        + content[insertion_point:]
    )

    CURRENT_FILE.write_text("\n".join(content) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    inject_requirement(args.req_id, args.summary, args.details)
    print(f"Added requirement {args.req_id} to {CURRENT_FILE.name}")


if __name__ == "__main__":
    main()
