from __future__ import annotations

import sys
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from runtime_paths import DEFAULT_CSV_DB_DIR, DEFAULT_LIVE_CAPTURE_LOG_PATH


class RuntimePathsTest(unittest.TestCase):
    def test_default_csv_db_dir_is_workspace_root_relative(self) -> None:
        self.assertEqual(DEFAULT_CSV_DB_DIR, WORKSPACE_ROOT / "csv_db")

    def test_live_capture_log_path_is_workspace_root_relative(self) -> None:
        self.assertEqual(DEFAULT_LIVE_CAPTURE_LOG_PATH, WORKSPACE_ROOT / "logs" / "live_capture.log")


if __name__ == "__main__":
    unittest.main()
