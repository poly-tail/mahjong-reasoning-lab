from __future__ import annotations

"""ワークスペースを source 配布または明示 runtime backup 用 ZIP にまとめる。"""

import argparse
import os
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "dist"
SOURCE_PROFILE = "source"
RUNTIME_BACKUP_PROFILE = "runtime-backup"
PROFILE_CHOICES = (SOURCE_PROFILE, RUNTIME_BACKUP_PROFILE)
ALWAYS_SKIP_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "out",
}
SOURCE_RUNTIME_DIR_NAMES = {
    "analysis_output",
    "csv_db",
    "logs",
    "reports",
}
SECRET_DIR_NAMES = {
    ".secrets",
}
TRANSIENT_DIR_PREFIXES = (
    "tmp",
)
TRANSIENT_DIR_ALLOWLIST = {
    "tmp_web",
}
SKIP_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
}
PACKAGED_ARTIFACT_SUFFIXES = {
    ".7z",
    ".zip",
}
SOURCE_RUNTIME_FILE_SUFFIXES = {
    ".log",
    ".pcap",
    ".pcapng",
}
SECRET_FILE_NAME_TOKENS = (
    "cookie",
    "keylog",
    "storage_state",
    "storage-state",
    "tls.keys",
    "token",
)


def _default_zip_name() -> str:
    """日時を含む既定の保存名を返す。"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"tenhou_hojo_workspace_{timestamp}.zip"


def _relative_parts(path: Path, root: Path) -> tuple[str, ...]:
    """Return a casefolded relative path tuple for filtering."""

    try:
        relative_path = path.resolve().relative_to(root.resolve())
    except ValueError:
        return ()
    return tuple(part.casefold() for part in relative_path.parts)


def _is_transient_dir_name(dir_name: str) -> bool:
    normalized = dir_name.casefold()
    return (
        any(normalized.startswith(prefix) for prefix in TRANSIENT_DIR_PREFIXES)
        and normalized not in TRANSIENT_DIR_ALLOWLIST
    )


def _is_secret_path(path: Path, root: Path) -> bool:
    parts = _relative_parts(path, root)
    if any(part in SECRET_DIR_NAMES for part in parts):
        return True
    name = path.name.casefold()
    return any(token in name for token in SECRET_FILE_NAME_TOKENS)


def _is_source_runtime_data_path(path: Path, root: Path) -> bool:
    parts = _relative_parts(path, root)
    if any(part in SOURCE_RUNTIME_DIR_NAMES for part in parts):
        return True
    suffix = path.suffix.casefold()
    if suffix in SOURCE_RUNTIME_FILE_SUFFIXES:
        return True
    return False


def _is_packaged_artifact(path: Path) -> bool:
    return path.suffix.casefold() in PACKAGED_ARTIFACT_SUFFIXES


def _is_always_skipped_dir(dir_name: str) -> bool:
    normalized = dir_name.casefold()
    return (
        normalized in ALWAYS_SKIP_DIR_NAMES
        or normalized in SECRET_DIR_NAMES
        or _is_transient_dir_name(normalized)
    )


def _should_include_source_file(file_path: Path, root: Path, output_path: Path) -> bool:
    """Return whether one file belongs in the safe source distribution ZIP."""

    if file_path.resolve() == output_path.resolve():
        return False
    if _is_secret_path(file_path, root):
        return False
    if _is_source_runtime_data_path(file_path, root):
        return False
    if _is_packaged_artifact(file_path):
        return False
    if file_path.suffix.casefold() in SKIP_FILE_SUFFIXES:
        return False
    if file_path.name.endswith("~"):
        return False
    return True


def _iter_source_workspace_files(
    root: Path,
    *,
    output_path: Path,
) -> tuple[list[Path], list[str]]:
    """Enumerate files for the safe source distribution profile."""

    collected: list[Path] = []
    warnings: list[str] = []

    def _on_error(error: OSError) -> None:
        # 一時フォルダなどで読めない経路があっても全体の保存は継続する。
        warnings.append(str(error))

    for current_root, dir_names, file_names in os.walk(root, topdown=True, onerror=_on_error):
        current_path = Path(current_root)
        # Keep source ZIPs free of runtime data, secrets, caches, and nested packages.
        dir_names[:] = [
            dir_name
            for dir_name in dir_names
            if not _is_always_skipped_dir(dir_name)
            and dir_name.casefold() not in SOURCE_RUNTIME_DIR_NAMES
        ]
        for file_name in file_names:
            file_path = current_path / file_name
            if not _should_include_source_file(file_path, root, output_path):
                continue
            try:
                if not file_path.is_file():
                    continue
            except OSError as exc:
                warnings.append(f"{file_path}: {exc}")
                continue
            collected.append(file_path)
    return collected, warnings


def _iter_runtime_backup_files(
    root: Path,
    *,
    include_paths: list[Path],
    output_path: Path,
) -> tuple[list[Path], list[str]]:
    """Enumerate explicitly requested runtime files while still rejecting secrets."""

    collected: list[Path] = []
    warnings: list[str] = []
    resolved_root = root.resolve()
    for include_path in include_paths:
        resolved_include_path = include_path.resolve()
        try:
            resolved_include_path.relative_to(resolved_root)
        except ValueError:
            raise ValueError(f"runtime-backup include path must stay under workspace: {include_path}")
        if not resolved_include_path.exists():
            warnings.append(f"missing runtime include path: {include_path}")
            continue
        candidate_files: list[Path] = []
        if resolved_include_path.is_file():
            candidate_files.append(resolved_include_path)
        else:
            for current_root, dir_names, file_names in os.walk(resolved_include_path, topdown=True):
                dir_names[:] = [
                    dir_name
                    for dir_name in dir_names
                    if dir_name.casefold() not in ALWAYS_SKIP_DIR_NAMES
                ]
                for file_name in file_names:
                    candidate_files.append(Path(current_root) / file_name)
        for file_path in candidate_files:
            if file_path.resolve() == output_path.resolve():
                continue
            if _is_secret_path(file_path, root):
                raise ValueError(f"runtime-backup rejected secret-like path: {file_path.relative_to(root)}")
            if file_path.suffix.casefold() in SKIP_FILE_SUFFIXES:
                continue
            if _is_packaged_artifact(file_path):
                continue
            collected.append(file_path)
    return collected, warnings


def _iter_workspace_files(
    root: Path,
    *,
    profile: str = SOURCE_PROFILE,
    include_runtime_paths: list[Path] | None = None,
    output_path: Path | None = None,
) -> tuple[list[Path], list[str]]:
    """除外規則を適用しながら ZIP 対象ファイルを列挙する。"""

    resolved_output_path = (
        output_path.resolve()
        if output_path is not None
        else (DEFAULT_OUTPUT_DIR / _default_zip_name()).resolve()
    )
    if profile == SOURCE_PROFILE:
        return _iter_source_workspace_files(root, output_path=resolved_output_path)
    if profile == RUNTIME_BACKUP_PROFILE:
        include_paths = list(include_runtime_paths or [])
        if not include_paths:
            raise ValueError("runtime-backup profile requires --include-runtime-data")
        return _iter_runtime_backup_files(
            root,
            include_paths=include_paths,
            output_path=resolved_output_path,
        )
    raise ValueError(f"unknown package profile: {profile}")


def _validate_archive_members(
    files: list[Path],
    root: Path,
    *,
    profile: str,
    output_path: Path,
) -> None:
    """Fail before writing if forbidden files would enter the archive."""

    violations: list[str] = []
    for file_path in files:
        if file_path.resolve() == output_path.resolve():
            violations.append(str(file_path.relative_to(root)))
            continue
        if _is_secret_path(file_path, root):
            violations.append(str(file_path.relative_to(root)))
            continue
        if profile == SOURCE_PROFILE and (
            _is_source_runtime_data_path(file_path, root) or _is_packaged_artifact(file_path)
        ):
            violations.append(str(file_path.relative_to(root)))
    if violations:
        joined = ", ".join(sorted(set(violations))[:20])
        raise RuntimeError(f"ZIP contains forbidden source paths: {joined}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="現在のワークスペースを安全な profile で ZIP 化します。",
    )
    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default=SOURCE_PROFILE,
        help="source は安全なソース配布、runtime-backup は明示指定した runtime data のみ保存します。",
    )
    parser.add_argument(
        "--include-runtime-data",
        action="append",
        default=[],
        help="runtime-backup profile で含める workspace 内 path。複数指定できます。",
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

    include_runtime_paths = [
        (ROOT / path_text).resolve()
        for path_text in args.include_runtime_data
    ]
    files, warnings = _iter_workspace_files(
        ROOT,
        profile=args.profile,
        include_runtime_paths=include_runtime_paths,
        output_path=output_path,
    )
    _validate_archive_members(files, ROOT, profile=args.profile, output_path=output_path)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in files:
            # ほかの環境で展開しやすいよう、ZIP 内はワークスペース相対パスで保存する。
            archive.write(file_path, arcname=file_path.relative_to(ROOT))

    print(f"ZIP 作成完了: {output_path}")
    print(f"profile: {args.profile}")
    print(f"格納ファイル数: {len(files)}")
    for warning in warnings:
        print(f"スキップ: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
