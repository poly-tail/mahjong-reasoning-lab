from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
import random
import re
import sqlite3
import time
from typing import Any

from naga_ptev.client import NagaPtevClient
from naga_ptev.models import KyokuState
from naga_ptev.parser import parse_analyzer_response
from naga_ptev.sampler import read_samples_csv
from naga_ptev.state_hash import state_hash
from naga_ptev.storage import save_raw_json


STOP_HTTP_STATUSES = {403, 429}


class CollectorStop(RuntimeError):
    """Raised when collection must stop immediately due to remote status."""


def utc_now_text() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def extract_http_status(error_message: str) -> int | None:
    match = re.search(r"HTTP\s+(\d{3})", str(error_message))
    if not match:
        return None
    return int(match.group(1))


def extract_json_status(error_message: str) -> int | None:
    match = re.search(r"['\"]status['\"]\s*:\s*(\d{3})", str(error_message))
    if not match:
        match = re.search(r"JSON status is not 200:\s*(\d{3})", str(error_message))
    if not match:
        return None
    return int(match.group(1))


def should_stop_for_http_status(status: int | None) -> bool:
    if status is None:
        return False
    return status in STOP_HTTP_STATUSES or 500 <= int(status) <= 599


def should_stop_for_status(http_status: int | None, json_status: int | None) -> bool:
    return should_stop_for_http_status(http_status) or should_stop_for_http_status(json_status)


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS states (
            state_hash TEXT PRIMARY KEY,
            kyoku INTEGER NOT NULL,
            honba INTEGER NOT NULL,
            kyotaku INTEGER NOT NULL,
            score0 INTEGER NOT NULL,
            score1 INTEGER NOT NULL,
            score2 INTEGER NOT NULL,
            score3 INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            raw_path TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state_hash TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL DEFAULT '',
            http_status INTEGER,
            json_status INTEGER,
            elapsed_ms INTEGER
        )
        """
    )
    conn.commit()


def enqueue_states(conn: sqlite3.Connection, states: list[KyokuState]) -> int:
    inserted = 0
    now = utc_now_text()
    for state in states:
        digest = state_hash(state)
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO states
            (state_hash, kyoku, honba, kyotaku, score0, score1, score2, score3, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                digest,
                int(state.kyoku),
                int(state.honba),
                int(state.kyotaku),
                int(state.scores[0]),
                int(state.scores[1]),
                int(state.scores[2]),
                int(state.scores[3]),
                now,
                now,
            ),
        )
        inserted += int(cursor.rowcount > 0)
    conn.commit()
    return inserted


def load_pending_states(conn: sqlite3.Connection, *, limit: int | None, resume: bool) -> list[tuple[str, KyokuState]]:
    statuses = ("pending", "failed") if resume else ("pending",)
    placeholders = ",".join("?" for _ in statuses)
    sql = f"""
        SELECT state_hash, kyoku, honba, kyotaku, score0, score1, score2, score3
        FROM states
        WHERE status IN ({placeholders})
        ORDER BY created_at, state_hash
    """
    params: list[Any] = list(statuses)
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    return [
        (
            str(row["state_hash"]),
            KyokuState(
                kyoku=int(row["kyoku"]),
                honba=int(row["honba"]),
                kyotaku=int(row["kyotaku"]),
                scores=[int(row[f"score{index}"]) for index in range(4)],
            ),
        )
        for row in rows
    ]


def _insert_request_start(conn: sqlite3.Connection, digest: str) -> int:
    cursor = conn.execute(
        "INSERT INTO requests (state_hash, started_at) VALUES (?, ?)",
        (digest, utc_now_text()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def _finish_request(
    conn: sqlite3.Connection,
    request_id: int,
    *,
    http_status: int | None,
    json_status: int | None,
    elapsed_ms: int,
) -> None:
    conn.execute(
        """
        UPDATE requests
        SET finished_at = ?, http_status = ?, json_status = ?, elapsed_ms = ?
        WHERE id = ?
        """,
        (utc_now_text(), http_status, json_status, int(elapsed_ms), int(request_id)),
    )
    conn.commit()


def _update_state(
    conn: sqlite3.Connection,
    digest: str,
    *,
    status: str,
    raw_path: str = "",
    error_message: str = "",
) -> None:
    conn.execute(
        """
        UPDATE states
        SET status = ?, raw_path = ?, error_message = ?, updated_at = ?
        WHERE state_hash = ?
        """,
        (status, raw_path, error_message[:1000], utc_now_text(), digest),
    )
    conn.commit()


async def collect_dataset_async(
    *,
    samples: str | Path,
    storage: str | Path,
    db: str | Path = "out/collector.sqlite",
    raw_dir: str | Path = "out/raw",
    sleep_sec: float = 1.0,
    limit: int | None = None,
    resume: bool = False,
) -> dict[str, int]:
    sleep_seconds = max(1.0, float(sleep_sec))
    states = read_samples_csv(samples)
    conn = connect(db)
    enqueue_states(conn, states)
    pending = load_pending_states(conn, limit=limit, resume=resume)
    counts = {"success": 0, "failed": 0, "skipped": 0}
    client = NagaPtevClient(sleep_seconds=0.0, raw_output_dir=raw_dir)
    await client.open_with_state(str(storage))
    try:
        for digest, state in pending:
            raw_path = Path(raw_dir) / f"{digest}.json"
            if raw_path.exists():
                _update_state(conn, digest, status="success", raw_path=str(raw_path), error_message="")
                counts["skipped"] += 1
                continue

            jittered_sleep = random.uniform(sleep_seconds * 0.8, sleep_seconds * 1.2)
            await asyncio.sleep(jittered_sleep)
            request_id = _insert_request_start(conn, digest)
            started = time.perf_counter()
            http_status: int | None = None
            json_status: int | None = None
            try:
                raw = await client.query(state)
                json_status = int(raw.get("status", 0)) if isinstance(raw, dict) else None
                parse_analyzer_response(raw, state)
                artifact = {
                    "saved_at": utc_now_text(),
                    "state_hash": digest,
                    "state": state.model_dump(),
                    "response": raw,
                }
                save_raw_json(artifact, raw_path)
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                http_status = extract_http_status(error_message)
                json_status = json_status or extract_json_status(error_message)
                error_path = Path(raw_dir) / f"{digest}.error.json"
                save_raw_json(
                    {
                        "saved_at": utc_now_text(),
                        "state_hash": digest,
                        "state": state.model_dump(),
                        "http_status": http_status,
                        "json_status": json_status,
                        "error_message": error_message,
                    },
                    error_path,
                )
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                _finish_request(
                    conn,
                    request_id,
                    http_status=http_status,
                    json_status=json_status,
                    elapsed_ms=elapsed_ms,
                )
                _update_state(conn, digest, status="failed", raw_path=str(error_path), error_message=error_message)
                counts["failed"] += 1
                if should_stop_for_status(http_status, json_status):
                    raise CollectorStop(
                        f"Stopping collection after status http={http_status or '-'} json={json_status or '-'}"
                    ) from exc
                continue

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            _finish_request(conn, request_id, http_status=200, json_status=json_status, elapsed_ms=elapsed_ms)
            _update_state(conn, digest, status="success", raw_path=str(raw_path), error_message="")
            counts["success"] += 1
    finally:
        await client.close()
        conn.close()
    return counts


def collect_dataset(**kwargs: Any) -> dict[str, int]:
    return asyncio.run(collect_dataset_async(**kwargs))
