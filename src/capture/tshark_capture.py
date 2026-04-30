from __future__ import annotations

import subprocess
import sys
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from capture.fragment_parser import extract_html_xml_fragments, parse_fragment, split_tshark_line
from capture.state import CaptureState, mark_runtime_thread_progress
from capture.storage import CsvDatabase, initialize_db, persist_event
from runtime_paths import DEFAULT_LIVE_CAPTURE_LOG_PATH

# TSHARK_PATH の定義。
TSHARK_PATH = Path("C:/Program Files/Wireshark/tshark")
# TSHARK_INTERFACE の定義。
TSHARK_INTERFACE = "5"
# PREFERRED_TSHARK_INTERFACE_HINTS は自動選択時に優先したい実ネットワーク adapter 名の断片。
PREFERRED_TSHARK_INTERFACE_HINTS = (
    "wi-fi",
    "wifi",
    "wireless",
    "wlan",
    "ethernet",
    "イーサネット",
)
# BLOCKED_TSHARK_INTERFACE_HINTS は Tenhou live capture の既定選択から除外したい adapter 名の断片。
BLOCKED_TSHARK_INTERFACE_HINTS = (
    "loopback",
    "adapter for loopback traffic capture",
    "npcap loopback",
    "event tracing for windows",
    "etw reader",
)
# DEPRIORITIZED_TSHARK_INTERFACE_HINTS は存在しても既定自動選択では避けたい adapter 名の断片。
DEPRIORITIZED_TSHARK_INTERFACE_HINTS = (
    "bluetooth",
    "vmware",
    "virtual",
    "vpn",
    "ローカル エリア接続*",
    "local area connection*",
)
# TLS_KEYLOG_FILE の定義。
TLS_KEYLOG_FILE = Path("C:/tmp/tls.keys")
# TSHARK_TARGET_NET の定義。
TSHARK_TARGET_NET: str | None = None
# CAPTURE_FILTER の定義。
CAPTURE_FILTER = "tcp port 443"
# TSHARK_DISPLAY_FILTER の定義。
TSHARK_DISPLAY_FILTER = "websocket"
# TSHARK_FIELDS の一覧。
TSHARK_FIELDS = [
    "frame.time_epoch",
    "websocket.payload.text",
    "text",
]
# LIVE_CAPTURE_LOG_PATH の定義。
LIVE_CAPTURE_LOG_PATH = DEFAULT_LIVE_CAPTURE_LOG_PATH


def _append_live_capture_log(message: str) -> None:
    """Append a timestamped live-capture diagnostic line to a local log file."""

    try:
        LIVE_CAPTURE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LIVE_CAPTURE_LOG_PATH.open("a", encoding="utf-8") as handle:
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            handle.write(f"[{now_text}] {message}\n")
    except OSError:
        return


def _list_tshark_interfaces() -> list[tuple[str, str]]:
    """Return `tshark -D` entries as `(index, description)` tuples."""

    try:
        completed = subprocess.run(
            [str(TSHARK_PATH), "-D"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return []
    entries: list[tuple[str, str]] = []
    for raw_line in str(completed.stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        interface_index, dot, description = line.partition(".")
        if dot != "." or not interface_index.strip().isdigit():
            continue
        entries.append((interface_index.strip(), description.strip()))
    return entries


def _score_tshark_interface_description(description: str) -> int:
    """Return a coarse preference score for one `tshark -D` description."""

    normalized = str(description or "").casefold()
    if any(token in normalized for token in BLOCKED_TSHARK_INTERFACE_HINTS):
        return -1000
    score = 0
    if any(token in normalized for token in PREFERRED_TSHARK_INTERFACE_HINTS):
        score += 100
    if any(token.casefold() in normalized for token in DEPRIORITIZED_TSHARK_INTERFACE_HINTS):
        score -= 10
    return score


def resolve_tshark_interface(interface_override: str | None = None) -> str:
    """Return the live-capture interface index/name that should be passed to tshark."""

    requested_interface = str(interface_override or "").strip()
    if requested_interface:
        return requested_interface

    default_interface = str(TSHARK_INTERFACE).strip()
    best_candidate: tuple[str, str] | None = None
    best_score = -1001
    first_neutral_candidate: tuple[str, str] | None = None
    default_interface_blocked = False
    for interface_index, description in _list_tshark_interfaces():
        score = _score_tshark_interface_description(description)
        if interface_index == default_interface and score <= -100:
            default_interface_blocked = True
        if score >= 0 and first_neutral_candidate is None:
            first_neutral_candidate = (interface_index, description)
        if score > best_score:
            best_score = score
            best_candidate = (interface_index, description)
    if best_candidate is not None and best_score > 0:
        return best_candidate[0]
    if default_interface_blocked and first_neutral_candidate is not None:
        return first_neutral_candidate[0]
    return default_interface


def _emit_live_capture_error(message: str, *, code: str | None = None, detail: str | None = None) -> None:
    """Emit live-capture failures to stdout/stderr and the rolling log file."""

    # Standard output is the first place the user asked to inspect while debugging live capture.
    print(message)
    print(message, file=sys.stderr)
    if code or detail:
        detail_text = f" code={code}" if code else ""
        if detail:
            detail_text = f"{detail_text} detail={detail}"
        _append_live_capture_log(f"live_error:{detail_text.strip()} message={message}")
    else:
        _append_live_capture_log(f"live_error: message={message}")


def _emit_tag_debug_message(message: str) -> None:
    """Emit one tag-level debug line to stdout and the rolling capture log."""

    print(message)
    _append_live_capture_log(message)


def _debug_tag_fragment(timestamp: float | None, fragment: str) -> None:
    """Print one extracted raw tag fragment before parser mutation."""

    # Show the exact fragment that will be mapped so capture/decryption issues are visible.
    _emit_tag_debug_message(f"[debug-tag] ts={timestamp} raw={fragment}")


def _debug_tag_event(timestamp: float | None, fragment: str, event: object) -> None:
    """Print the parsed event summary that came out of one raw fragment."""

    # Keep the event summary flat and explicit so tag-to-event mapping is easy to compare.
    if event is None:
        _emit_tag_debug_message(f"[debug-event] ts={timestamp} raw={fragment} event=None")
        return
    event_type = getattr(event, "event_type", "")
    seat = getattr(event, "seat", None)
    tile_136 = getattr(event, "tile_136", None)
    attrs = getattr(event, "attrs", {})
    _emit_tag_debug_message(
        f"[debug-event] ts={timestamp} type={event_type} seat={seat} tile_136={tile_136} attrs={attrs}"
    )


def _record_capture_warning(state: CaptureState, *, code: str, message: str, raw_line: str = "") -> None:
    """Keep capture-line failures in diagnostics without stopping the live thread."""

    # Keep a structured in-memory warning so the UI and diagnostics export can inspect it later.
    with state.state_lock:
        state.diagnostics.append(
            {
                "level": "warning",
                "code": code,
                "message": message,
                "raw_line": raw_line,
            }
        )
        state.prune_live_history()
    _emit_live_capture_error(message, code=code)
    if raw_line:
        _append_live_capture_log(f"{code}: {message} | raw={raw_line[:1000]}")
    else:
        _append_live_capture_log(f"{code}: {message}")


def _mark_capture_progress(
    state: CaptureState,
    stage: str,
    *,
    detail: str = "",
    blocked_hint: str = "",
    stale_after_s: float = 10.0,
    repeat_after_s: float = 15.0,
) -> None:
    """Record one capture-thread progress point for the runtime watchdog."""

    mark_runtime_thread_progress(
        state,
        "capture",
        stage,
        detail=detail,
        blocked_hint=blocked_hint,
        stale_after_s=stale_after_s,
        repeat_after_s=repeat_after_s,
    )


def build_tshark_command(
    tls_keylog_path: str | Path | None = None,
    tshark_interface: str | None = None,
) -> list[str]:
    """Build the live tshark command used for websocket capture."""

    # Build the capture filter from the optional target-net override first.
    capture_filter = CAPTURE_FILTER
    if TSHARK_TARGET_NET:
        capture_filter = f"net {TSHARK_TARGET_NET} and tcp port 443"

    # Resolve the TLS keylog path early so startup errors fail before spawning tshark.
    keylog_path = Path(tls_keylog_path) if tls_keylog_path is not None else Path(TLS_KEYLOG_FILE)
    if not keylog_path.exists():
        raise FileNotFoundError(f"TLS keylog file not found: {keylog_path}")

    selected_interface = resolve_tshark_interface(tshark_interface)
    command = [
        str(TSHARK_PATH),
        "-l",
        "-i",
        selected_interface,
        "-o",
        f"tls.keylog_file:{keylog_path}",
        "-f",
        capture_filter,
        "-Y",
        TSHARK_DISPLAY_FILTER,
        "-T",
        "fields",
        "-E",
        # TShark field output expects the symbolic `/t` form, not a literal tab character.
        "separator=/t",
    ]
    for field_name in TSHARK_FIELDS:
        command.extend(["-e", field_name])
    return command


def parse_tshark_output_line(
    state: CaptureState,
    db: CsvDatabase | None,
    line: str,
    *,
    debug_tags: bool = False,
) -> None:
    """Parse one tshark text line and persist the normalized events."""

    # Step 1: split the tshark TSV line into timestamp and websocket payload.
    _mark_capture_progress(
        state,
        "split_tshark_line",
        detail=f"line_len={len(line)}",
        blocked_hint="splitting one tshark stdout line",
        stale_after_s=2.0,
        repeat_after_s=6.0,
    )
    try:
        timestamp, payload = split_tshark_line(line)
    except Exception as exc:  # noqa: BLE001 - malformed tshark rows must not stop capture.
        _record_capture_warning(
            state,
            code="tshark_line_split_failed",
            message=f"Capture line split skipped: {exc}",
            raw_line=line.rstrip(),
        )
        return
    # TShark writes startup and failure diagnostics to the same combined stdout stream.
    # If the line is non-empty but not a timestamped packet row, surface it instead of silently
    # dropping it so interface/keylog/filter failures are visible to the user.
    if timestamp is None:
        raw_line = line.rstrip()
        if raw_line:
            _record_capture_warning(
                state,
                code="tshark_runtime_message",
                message=f"TShark runtime message: {raw_line}",
                raw_line=raw_line,
            )
        return
    if timestamp is None or not payload:
        return
    # Step 2: extract one or more mjlog fragments from the websocket payload.
    _mark_capture_progress(
        state,
        "extract_fragments",
        detail=f"payload_len={len(payload)}",
        blocked_hint="extracting XML fragments from one websocket payload",
        stale_after_s=2.0,
        repeat_after_s=6.0,
    )
    try:
        fragments = extract_html_xml_fragments(payload)
    except Exception as exc:  # noqa: BLE001 - malformed payloads must not stop capture.
        _record_capture_warning(
            state,
            code="payload_fragment_extract_failed",
            message=f"Payload fragment extraction skipped: {exc}",
            raw_line=payload,
        )
        return
    for fragment in fragments:
        if debug_tags:
            _debug_tag_fragment(timestamp, fragment)
        # Step 3: parse one fragment into the mutable live state.
        _mark_capture_progress(
            state,
            "parse_fragment",
            detail=fragment[:96],
            blocked_hint="inside capture.fragment_parser.parse_fragment",
            stale_after_s=2.0,
            repeat_after_s=6.0,
        )
        try:
            with state.state_lock:
                event = parse_fragment(state, timestamp, fragment)
        except Exception as exc:  # noqa: BLE001 - one bad fragment must not stop capture.
            _record_capture_warning(
                state,
                code="fragment_parse_failed",
                message=f"Fragment parse skipped: {exc}",
                raw_line=fragment,
            )
            continue
        _mark_capture_progress(
            state,
            "event_parsed",
            detail=(
                f"type={getattr(event, 'event_type', '')} "
                f"seat={getattr(event, 'seat', None)}"
            ),
            blocked_hint="post-parse capture event handling",
            stale_after_s=2.0,
            repeat_after_s=6.0,
        )
        if debug_tags:
            _debug_tag_event(timestamp, fragment, event)
        if event is not None and event.event_type in {"init", "reinit", "initbylog", "wgc"}:
            _append_live_capture_log(
                f"snapshot_event: type={event.event_type} raw={fragment[:1000]}"
            )
        if event is not None and db is not None:
            # DB persistence is intentionally isolated so parser/rendering can continue on write failure.
            _mark_capture_progress(
                state,
                "persist_event",
                detail=f"event={event.event_type}",
                blocked_hint="inside capture.storage.persist_event",
                stale_after_s=2.5,
                repeat_after_s=6.0,
            )
            try:
                persist_event(db, state, event)
            except Exception as exc:
                _emit_live_capture_error(
                    f"DB persist skipped: {exc}",
                    code="db_persist_skipped",
                    detail=traceback.format_exc(limit=5).strip(),
                )


def run_and_capture(
    state: CaptureState | None = None,
    tls_keylog_path: str | Path | None = None,
    tshark_interface: str | None = None,
    *,
    debug_tags: bool = False,
) -> CaptureState:
    """Run live tshark capture and stream parsed websocket events into state."""

    state = state or CaptureState()
    _mark_capture_progress(
        state,
        "run_and_capture_start",
        detail="capture startup",
        blocked_hint="initializing capture runtime",
        stale_after_s=4.0,
        repeat_after_s=10.0,
    )
    # Write a startup marker first so we can distinguish "capture never started" from "started but idle".
    _append_live_capture_log("capture_start_requested")
    # DB setup is best-effort. Live parsing/rendering must continue even if CSV writing is unavailable.
    try:
        _mark_capture_progress(
            state,
            "db_initialize",
            detail="initialize_db",
            blocked_hint="initializing CSV persistence",
            stale_after_s=4.0,
            repeat_after_s=10.0,
        )
        db = initialize_db()
    except Exception as exc:
        _emit_live_capture_error(
            f"DB initialization skipped: {exc}",
            code="db_initialization_skipped",
            detail=traceback.format_exc(limit=5).strip(),
        )
        db = None
    try:
        # Startup failures around tshark path, TLS keylog, or process spawn must be surfaced immediately.
        _mark_capture_progress(
            state,
            "build_tshark_command",
            detail="build_tshark_command",
            blocked_hint="building tshark capture command",
            stale_after_s=4.0,
            repeat_after_s=10.0,
        )
        command = build_tshark_command(
            tls_keylog_path=tls_keylog_path,
            tshark_interface=tshark_interface,
        )
        _append_live_capture_log(f"tshark_interface_selected: {command[3]}")
        _append_live_capture_log(f"tshark_command_ready: {' '.join(command)}")
        _mark_capture_progress(
            state,
            "spawn_tshark",
            detail=f"interface={command[3]}",
            blocked_hint="starting tshark subprocess",
            stale_after_s=4.0,
            repeat_after_s=10.0,
        )
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
                raise RuntimeError("Failed to open tshark stdout.")
            try:
                # Process each tshark line independently so one malformed payload cannot stop capture.
                _mark_capture_progress(
                    state,
                    "tshark_stdout_wait",
                    detail="waiting next line",
                    blocked_hint="waiting on tshark stdout for the next websocket packet",
                    stale_after_s=12.0,
                    repeat_after_s=20.0,
                )
                for line in proc.stdout:
                    try:
                        parse_tshark_output_line(state, db, line, debug_tags=debug_tags)
                    except Exception as exc:  # noqa: BLE001 - live capture must stay running.
                        _record_capture_warning(
                            state,
                            code="capture_line_processing_failed",
                            message=f"Capture line processing skipped: {exc}",
                            raw_line=line.rstrip(),
                        )
                    _mark_capture_progress(
                        state,
                        "tshark_stdout_wait",
                        detail="waiting next line",
                        blocked_hint="waiting on tshark stdout for the next websocket packet",
                        stale_after_s=12.0,
                        repeat_after_s=20.0,
                    )
            finally:
                if proc.poll() is None:
                    proc.terminate()
    except Exception as exc:
        _mark_capture_progress(
            state,
            "capture_failed",
            detail=str(exc),
            blocked_hint="capture thread raised an exception",
            stale_after_s=60.0,
            repeat_after_s=60.0,
        )
        _emit_live_capture_error(
            f"Live tshark capture failed: {exc}",
            code="tshark_capture_failed",
            detail=traceback.format_exc(limit=8).strip(),
        )
        raise
    finally:
        if db is not None:
            try:
                db.close()
            except Exception as exc:  # noqa: BLE001 - close failures must still be visible.
                _emit_live_capture_error(
                    f"DB close skipped: {exc}",
                    code="db_close_skipped",
                    detail=traceback.format_exc(limit=5).strip(),
                )
    _append_live_capture_log("capture_process_exited")
    _mark_capture_progress(
        state,
        "capture_process_exited",
        detail="tshark process exited",
        blocked_hint="capture thread reached process exit",
        stale_after_s=60.0,
        repeat_after_s=60.0,
    )
    return state


def main() -> None:
    """Small debug entrypoint for direct tshark-capture execution."""

    print("Starting packet capture via tshark...")
    try:
        state = run_and_capture()
    except KeyboardInterrupt:
        print("Capture interrupted by user.")
        return

    print("=== players ===")
    for seat, player in state.players.items():
        print(seat, asdict(player))

    print("\n=== rounds ===")
    print(f"round count: {len(state.rounds)}")
    if state.current_round is not None:
        print("scores:", state.current_round.scores)
        print("dora indicators:", state.current_round.dora_indicators_136)
        for seat in range(4):
            print(f"seat {seat} discards:", [asdict(item) for item in state.current_round.discards[seat]])

    print("\n=== events ===")
    print(f"event count: {len(state.events)}")
    for event in state.events[:20]:
        print(asdict(event))

    print("\n=== chats ===")
    for chat in state.chats[:10]:
        print(chat)

    print("\n=== unknown tags ===")
    for item in state.unknown_tags[:20]:
        print(item)


if __name__ == "__main__":
    main()
