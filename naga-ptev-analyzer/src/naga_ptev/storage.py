from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    import pandas as pd


def _ensure_parent(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def save_raw_json(raw: dict[str, Any], path: str | Path) -> Path:
    target = _ensure_parent(path)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(raw, handle, ensure_ascii=False, indent=2)
    return target


def save_dataframe_csv(df: "pd.DataFrame", path: str | Path) -> Path:
    target = _ensure_parent(path)
    df.to_csv(target, index=False, encoding="utf-8-sig")
    return target


def append_jsonl(record: dict[str, Any], path: str | Path) -> Path:
    target = _ensure_parent(path)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return target


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a mapping, got {type(loaded).__name__}")
    return loaded


def timestamped_artifact_path(directory: str | Path, stem: str, suffix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(directory) / f"{timestamp}_{stem}{suffix}"

