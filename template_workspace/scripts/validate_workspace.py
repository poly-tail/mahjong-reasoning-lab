from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    ".codex/config.toml",
    ".github/workflows/ci.yml",
    "Makefile",
    "scripts/README.md",
    "scripts/validate_workspace.py",
    "scripts/render_docs_graphs.py",
    "scripts/clean_python_cache.py",
    ".agents/skills/update-docs/SKILL.md",
    ".agents/skills/sync-current-files/SKILL.md",
    "docs/README.md",
    "docs/context.md",
    "docs/project_guide.md",
    "docs/source_overview.md",
    "docs/folder_structure.md",
    "docs/src_call_graph.md",
    "docs/changelog.md",
    "docs/graphs/generated/README.md",
    "docs/graphs/src/project_flow.mmd",
    "docs/graphs/src/project_hierarchy.mmd",
    "docs/requirements/current.md",
    "docs/specs/current.md",
    "docs/screen_specs/current.md",
    "language_packs/README.md",
    "language_packs/python/README.md",
)

REQUIRED_DIRS = (
    "src/app",
    "src/domain",
    "src/infrastructure",
    "src/shared",
    "src/ui",
    "tests/unit",
    "tests/integration",
    "tests/fixtures",
    "analysis_output",
    "assets",
    "cli",
    "docs",
    "language_packs",
    "scripts",
)


def _find_cache_artifacts(root: Path) -> list[Path]:
    results: list[Path] = []
    for path in root.rglob("*"):
        if path.name == "__pycache__" or path.suffix == ".pyc":
            results.append(path)
    return sorted(results)


def _find_tracked_generated_svgs(root: Path) -> list[Path]:
    generated_dir = root / "docs" / "graphs" / "generated"
    if not generated_dir.exists():
        return []
    results = [
        path
        for path in generated_dir.glob("*.svg")
        if path.name.lower() != "readme.md"
    ]
    return sorted(results)


def main() -> int:
    errors: list[str] = []

    for relative_path in REQUIRED_FILES:
        if not (ROOT / relative_path).is_file():
            errors.append(f"Missing required file: {relative_path}")

    for relative_path in REQUIRED_DIRS:
        if not (ROOT / relative_path).is_dir():
            errors.append(f"Missing required directory: {relative_path}")

    cache_artifacts = _find_cache_artifacts(ROOT)
    if cache_artifacts:
        for path in cache_artifacts:
            errors.append(f"Cache artifact must not ship in template: {path.relative_to(ROOT)}")

    generated_svgs = _find_tracked_generated_svgs(ROOT)
    if generated_svgs:
        for path in generated_svgs:
            errors.append(f"Generated SVG must be re-created locally, not shipped: {path.relative_to(ROOT)}")

    if errors:
        print("Workspace validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Workspace validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
