from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


def _load_package_workspace_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "package_workspace.py"
    spec = importlib.util.spec_from_file_location("package_workspace", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


package_workspace = _load_package_workspace_module()


class PackageWorkspaceTest(unittest.TestCase):
    def test_source_profile_excludes_runtime_secrets_and_nested_archives(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "tmp_web").mkdir()
            (root / "tmp_web" / "mock.html").write_text("<html></html>\n", encoding="utf-8")
            (root / "tmp123").mkdir()
            (root / "tmp123" / "scratch.txt").write_text("scratch\n", encoding="utf-8")
            (root / "logs").mkdir()
            (root / "logs" / "live_capture.log").write_text("runtime log\n", encoding="utf-8")
            (root / "csv_db").mkdir()
            (root / "csv_db" / "discard_fact_202606.csv").write_text("runtime csv\n", encoding="utf-8")
            (root / ".secrets").mkdir()
            (root / ".secrets" / "state.json").write_text("secret\n", encoding="utf-8")
            (root / "template_workspace.7z").write_bytes(b"nested 7z")
            (root / "tenhou_hojo.zip").write_bytes(b"nested zip")
            output_path = root / "dist" / "package.zip"

            files, warnings = package_workspace._iter_workspace_files(
                root,
                profile=package_workspace.SOURCE_PROFILE,
                output_path=output_path,
            )

        relative_files = {
            str(file_path.relative_to(root)).replace("\\", "/")
            for file_path in files
        }
        self.assertEqual(warnings, [])
        self.assertIn("src/app.py", relative_files)
        self.assertIn("tmp_web/mock.html", relative_files)
        self.assertNotIn("tmp123/scratch.txt", relative_files)
        self.assertNotIn("logs/live_capture.log", relative_files)
        self.assertNotIn("csv_db/discard_fact_202606.csv", relative_files)
        self.assertNotIn(".secrets/state.json", relative_files)
        self.assertNotIn("template_workspace.7z", relative_files)
        self.assertNotIn("tenhou_hojo.zip", relative_files)

    def test_runtime_backup_requires_explicit_include_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(ValueError):
                package_workspace._iter_workspace_files(
                    root,
                    profile=package_workspace.RUNTIME_BACKUP_PROFILE,
                    output_path=root / "backup.zip",
                )

    def test_runtime_backup_rejects_secret_like_paths_even_when_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime_dir = root / "csv_db"
            runtime_dir.mkdir()
            (runtime_dir / "discard_fact_202606.csv").write_text("ok\n", encoding="utf-8")
            (runtime_dir / "cookie_state.json").write_text("secret\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                package_workspace._iter_workspace_files(
                    root,
                    profile=package_workspace.RUNTIME_BACKUP_PROFILE,
                    include_runtime_paths=[runtime_dir],
                    output_path=root / "backup.zip",
                )


if __name__ == "__main__":
    unittest.main()
