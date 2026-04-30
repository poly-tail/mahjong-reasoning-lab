from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_CACHE_DIR = ROOT / "tests" / "unit" / "__pycache__"


class WorkspaceStructureTests(unittest.TestCase):
    def test_codex_native_files_exist(self) -> None:
        required_files = (
            ROOT / "AGENTS.md",
            ROOT / ".codex" / "config.toml",
            ROOT / ".agents" / "skills" / "update-docs" / "SKILL.md",
            ROOT / ".agents" / "skills" / "sync-current-files" / "SKILL.md",
            ROOT / "Makefile",
            ROOT / "scripts" / "validate_workspace.py",
            ROOT / ".github" / "workflows" / "ci.yml",
        )
        for path in required_files:
            self.assertTrue(path.is_file(), str(path))

    def test_template_contains_no_python_cache_artifacts(self) -> None:
        cache_paths = [
            path
            for path in ROOT.rglob("*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        ]
        cache_paths = [
            path
            for path in cache_paths
            if not (
                path == RUNTIME_CACHE_DIR
                or RUNTIME_CACHE_DIR in path.parents
            )
        ]
        self.assertEqual(cache_paths, [])

    def test_generated_graph_directory_keeps_readme_only(self) -> None:
        generated_dir = ROOT / "docs" / "graphs" / "generated"
        generated_files = sorted(
            path.name
            for path in generated_dir.iterdir()
            if path.is_file()
        )
        self.assertEqual(generated_files, ["README.md"])


if __name__ == "__main__":
    unittest.main()
