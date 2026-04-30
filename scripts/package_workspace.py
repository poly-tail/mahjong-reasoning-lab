from __future__ import annotations

"""ワークスペース一式を配布・退避向け ZIP にまとめる補助スクリプト。"""

import argparse
import os
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "dist"
SKIP_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "dist",
}
SKIP_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def _default_zip_name() -> str:
    """日時を含む既定の保存名を返す。"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"tenhou_hojo_workspace_{timestamp}.zip"


def _iter_workspace_files(root: Path) -> tuple[list[Path], list[str]]:
    """除外規則を適用しながら ZIP 対象ファイルを列挙する。"""

    collected: list[Path] = []
    warnings: list[str] = []

    def _on_error(error: OSError) -> None:
        # 一時フォルダなどで読めない経路があっても全体の保存は継続する。
        warnings.append(str(error))

    for current_root, dir_names, file_names in os.walk(root, topdown=True, onerror=_on_error):
        current_path = Path(current_root)
        # キャッシュや既存 ZIP を再帰的に抱き込まないよう先に除外する。
        dir_names[:] = [
            dir_name
            for dir_name in dir_names
            if dir_name not in SKIP_DIR_NAMES
        ]
        for file_name in file_names:
            file_path = current_path / file_name
            if file_path.suffix.lower() in SKIP_FILE_SUFFIXES:
                continue
            if file_path.name.endswith("~"):
                continue
            try:
                if not file_path.is_file():
                    continue
            except OSError as exc:
                warnings.append(f"{file_path}: {exc}")
                continue
            collected.append(file_path)
    return collected, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="現在のワークスペースを ZIP 化して配布・退避用に保存します。",
    )
    parser.add_argument(
        "--output",
        default="",
        help="出力先 ZIP パス。未指定時は dist/ 配下へ日時付きで保存します。",
    )
    args = parser.parse_args()

    output_path = (
        Path(args.output).resolve()
        if str(args.output).strip()
        else (DEFAULT_OUTPUT_DIR / _default_zip_name()).resolve()
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files, warnings = _iter_workspace_files(ROOT)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in files:
            # ほかの環境で展開しやすいよう、ZIP 内はワークスペース相対パスで保存する。
            archive.write(file_path, arcname=file_path.relative_to(ROOT))

    print(f"ZIP 作成完了: {output_path}")
    print(f"格納ファイル数: {len(files)}")
    for warning in warnings:
        print(f"スキップ: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
