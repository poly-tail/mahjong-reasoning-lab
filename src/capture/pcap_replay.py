from __future__ import annotations

import subprocess
import time
from pathlib import Path

from capture.state import CaptureState
from capture.storage import initialize_db
from capture.tshark_capture import (
    TLS_KEYLOG_FILE,
    TSHARK_DISPLAY_FILTER,
    TSHARK_FIELDS,
    TSHARK_PATH,
    _record_capture_warning,
    parse_tshark_output_line,
)

# DEFAULT_TEST_PACKET_INTERVAL_MS の定義。
DEFAULT_TEST_PACKET_INTERVAL_MS = 500


def build_pcap_tshark_command(
    input_path: str | Path,
    tls_keylog_path: str | Path | None = None,
) -> list[str]:
    """Build the offline tshark command for a replayable `.pcapng` capture."""

    pcap_path = Path(input_path)
    if pcap_path.suffix.lower() != ".pcapng":
        raise ValueError(f"Test input must be a .pcapng file: {pcap_path}")
    if not pcap_path.exists():
        raise FileNotFoundError(f"Test input file not found: {pcap_path}")

    keylog_path = Path(tls_keylog_path) if tls_keylog_path is not None else Path(TLS_KEYLOG_FILE)
    if not keylog_path.exists():
        raise FileNotFoundError(f"TLS keylog file not found: {keylog_path}")

    command = [
        str(TSHARK_PATH),
        "-l",
        "-r",
        str(pcap_path),
        "-o",
        f"tls.keylog_file:{keylog_path}",
        "-Y",
        TSHARK_DISPLAY_FILTER,
        "-T",
        "fields",
        "-E",
        # Keep replay output identical to live capture so both paths share the same line parser.
        "separator=/t",
    ]
    for field_name in TSHARK_FIELDS:
        command.extend(["-e", field_name])
    return command


def run_test_capture(
    input_path: str | Path,
    state: CaptureState | None = None,
    tls_keylog_path: str | Path | None = None,
    interval_ms: int = DEFAULT_TEST_PACKET_INTERVAL_MS,
    *,
    debug_tags: bool = False,
) -> CaptureState:
    """Replay a `.pcapng` capture through tshark using the provided TLS keylog."""

    if interval_ms < 0:
        raise ValueError(f"interval_ms must be >= 0: {interval_ms}")

    state = state or CaptureState()
    try:
        db = initialize_db()
    except Exception as exc:
        print(f"DB initialization skipped: {exc}")
        db = None
    command = build_pcap_tshark_command(input_path, tls_keylog_path=tls_keylog_path)
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    ) as proc:
        if proc.stdout is None:
            if db is not None:
                db.close()
            raise RuntimeError("Failed to open tshark stdout for pcap replay.")
        try:
            for line in proc.stdout:
                try:
                    parsed_packet = parse_tshark_output_line(
                        state,
                        db,
                        line,
                        debug_tags=debug_tags,
                    )
                except Exception as exc:  # noqa: BLE001 - one bad replay line must not abort replay.
                    _record_capture_warning(
                        state,
                        code="pcap_replay_line_processing_failed",
                        message=f"Pcap replay line processing skipped: {exc}",
                        raw_line=line.rstrip(),
                    )
                    parsed_packet = False
                if parsed_packet and interval_ms > 0:
                    time.sleep(interval_ms / 1000)
        finally:
            if db is not None:
                db.close()
            if proc.poll() is None:
                proc.terminate()
        return_code = proc.wait()
        if return_code != 0:
            raise RuntimeError(f"tshark pcap replay exited with code {return_code}.")
    return state
