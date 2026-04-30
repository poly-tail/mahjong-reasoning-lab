from __future__ import annotations

from pathlib import Path

from capture.csv_db_schema import CSV_DB_DIRNAME


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_DB_DIR = WORKSPACE_ROOT / CSV_DB_DIRNAME
DEFAULT_LOG_DIR = WORKSPACE_ROOT / "logs"
DEFAULT_LIVE_CAPTURE_LOG_PATH = DEFAULT_LOG_DIR / "live_capture.log"
