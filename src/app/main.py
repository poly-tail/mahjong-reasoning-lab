from __future__ import annotations

import argparse
import copy
import itertools
import math
import os
import sys
import threading
import time
import traceback
import tkinter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from app import naga_analyzer
from app.hand_recommendation_service import HandRecommendationService
from app.pystyle_simulator_protocol import (
    PystyleDisplayContext,
    PystyleRequestMeld,
    build_remaining_wall_from_visible_tiles37,
    tile37_to_simulator_tile,
)
from app.tenhou_ui_bridge_client import TenhouUiBridgeClient
from app.tenhou_ui_bridge_protocol import (
    DEFAULT_TENHOU_UI_BRIDGE_HOST,
    DEFAULT_TENHOU_UI_BRIDGE_PORT,
    VisibleHandState,
    build_tenhou_ui_bridge_ws_url,
    build_visible_hand_state,
)
from app.tenhou_ui_bridge_server import TenhouUiBridgeServer
from app.mock_data import (
    AVAILABLE_MOCK_PATTERNS,
    DEFAULT_MOCK_PATTERN,
    build_mock_meld_map,
    build_mock_tracker,
    get_mock_inputs,
    tiles136_to_tiles37,
)
from app.window import configure_window
from capture.pcap_replay import DEFAULT_TEST_PACKET_INTERVAL_MS, run_test_capture
from capture.state import (
    CaptureState,
    Discard as CaptureDiscard,
    Event as CaptureEvent,
    LOCAL_RELATIVE_SEAT,
    Meld,
    RED_TILE_IDS_136,
    RoundState,
    SEAT_COUNT,
    build_round_id,
    build_round_key,
    mark_runtime_thread_progress,
    snapshot_runtime_thread_progress,
    tile136_to_tile37,
)
from capture.storage import import_xml_discard_hands, remember_pystyle_self_history
from capture.tshark_capture import (
    TLS_KEYLOG_FILE,
    LIVE_CAPTURE_LOG_PATH,
    TSHARK_INTERFACE,
    run_and_capture,
)
from capture.xml_url_loader import extract_log_id, fetch_xml_text_from_url
from logic.danger_suji import (
    DEFAULT_TENPAI_PROBABILITY_PERCENT,
    build_all_opponent_suji_danger_profiles,
    build_all_opponent_suji_panel_summaries,
    build_discard_red_tint_indices_by_seat,
    build_hand_tile_suji_danger_metrics,
    build_latest_discard_push_alert_percentages,
)
from sutehai import Player, SutehaiTracker
import ui.table_renderer as table_view
from visible_tiles import VisibleTileSummary, collect_visible_tile_summary
from capture.fragment_parser import (
    _rebuild_tracker_from_round,
    _reindex_round_discards,
    _restore_reach_state_from_snapshot_discards,
    _sync_live_state,
    load_from_xml_text,
)

LIVE_DISCARD_RED_TINT_ENABLED = True
LIVE_ASYNC_BUNDLE_REFRESH_ENABLED = True
LIVE_RUNTIME_WATCHDOG_POLL_INTERVAL_S = 1.0
LIVE_SNAPSHOT_REQUEST_MIN_INTERVAL_S = 0.08
NAGA_BUTTON_X = 82
NAGA_BUTTON_Y = 64
NAGA_WINDOW_WIDTH = 860
NAGA_WINDOW_HEIGHT = 700
NAGA_AUTO_START_KYOKU = 5
NAGA_AUTO_REFRESH_MS = 1000
NAGA_AUTO_ERROR_TEXT_MAX = 72
NAGA_POPUP_TITLE = "NAGA 段位ポイント分析"
NAGA_POPUP_SECTION_ALL = "all"
NAGA_POPUP_SECTION_3900 = "3900"
NAGA_POPUP_SECTION_MANGAN = "mangan"
NAGA_POPUP_SECTION_LABELS = (
    (NAGA_POPUP_SECTION_ALL, "全体"),
    (NAGA_POPUP_SECTION_3900, "3900直撃平均"),
    (NAGA_POPUP_SECTION_MANGAN, "満貫ツモ候補"),
)
NAGA_GRAPH_METRICS = (
    ("ptev", "段位ptEV"),
    ("p1", "1着率"),
    ("p2", "2着率"),
    ("p4", "4着率"),
)

# DEFAULT_PLAYER_NAMES_BY_SEAT の対応表。
DEFAULT_PLAYER_NAMES_BY_SEAT = {
    int(Player.JICHA): "YOU",
    int(Player.SHIMOCHA): "SHIMO",
    int(Player.TOIMEN): "TOIMEN",
    int(Player.KAMICHA): "KAMI",
}
# ROUND_WIND_LABELS の並びを定義する。
ROUND_WIND_LABELS = ("東", "南", "西", "北")


def _build_stale_runtime_thread_reports(
    progress_snapshot: dict[str, dict[str, Any]],
    *,
    now_monotonic: float,
) -> list[dict[str, Any]]:
    """Return watchdog report candidates for threads whose progress has gone stale."""

    reports: list[dict[str, Any]] = []
    for thread_name in sorted(progress_snapshot):
        progress = dict(progress_snapshot.get(thread_name, {}))
        updated_monotonic = float(progress.get("updated_monotonic", 0.0) or 0.0)
        stale_after_s = max(0.5, float(progress.get("stale_after_s", 10.0) or 10.0))
        repeat_after_s = max(1.0, float(progress.get("repeat_after_s", 15.0) or 15.0))
        if updated_monotonic <= 0.0:
            continue
        age_s = max(0.0, float(now_monotonic - updated_monotonic))
        if age_s < stale_after_s:
            continue
        reports.append(
            {
                "thread_name": thread_name,
                "stage": str(progress.get("stage", "") or "unknown"),
                "detail": str(progress.get("detail", "") or ""),
                "blocked_hint": str(progress.get("blocked_hint", "") or ""),
                "age_s": age_s,
                "sequence": int(progress.get("sequence", 0) or 0),
                "repeat_after_s": repeat_after_s,
            }
        )
    return reports


def _format_stale_runtime_thread_report(report: dict[str, Any]) -> str:
    """Format one watchdog report as a compact stdout line."""

    thread_name = str(report.get("thread_name", "") or "unknown")
    stage = str(report.get("stage", "") or "unknown")
    age_s = max(0.0, float(report.get("age_s", 0.0) or 0.0))
    blocked_hint = str(report.get("blocked_hint", "") or "").strip()
    detail = str(report.get("detail", "") or "").strip()
    parts = [
        "[watchdog]",
        f"thread={thread_name}",
        f"stalled_for={age_s:.1f}s",
        f"stage={stage}",
    ]
    if blocked_hint:
        parts.append(f"reason={blocked_hint}")
    if detail:
        parts.append(f"detail={detail}")
    return " ".join(parts)


def _append_live_runtime_log(message: str) -> None:
    """Append one live-runtime diagnostic line to the capture log."""

    try:
        LIVE_CAPTURE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LIVE_CAPTURE_LOG_PATH.open("a", encoding="utf-8") as handle:
            now_text = time.strftime("%Y-%m-%d %H:%M:%S")
            handle.write(f"[{now_text}] {message}\n")
    except OSError:
        return


def _start_live_runtime_watchdog(capture_state: CaptureState) -> None:
    """Start one stdout watchdog that reports stale capture/UI progress markers."""

    if bool(getattr(capture_state, "_live_runtime_watchdog_started", False)):
        return
    capture_state._live_runtime_watchdog_started = True

    def _watchdog_worker() -> None:
        last_report_by_thread: dict[str, tuple[tuple[Any, ...], float]] = {}
        while True:
            time.sleep(LIVE_RUNTIME_WATCHDOG_POLL_INTERVAL_S)
            progress_snapshot = snapshot_runtime_thread_progress(capture_state)
            now_monotonic = time.monotonic()
            for report in _build_stale_runtime_thread_reports(
                progress_snapshot,
                now_monotonic=now_monotonic,
            ):
                thread_name = str(report["thread_name"])
                signature = (
                    report.get("stage"),
                    report.get("detail"),
                    report.get("blocked_hint"),
                    int(report.get("sequence", 0) or 0),
                )
                last_report = last_report_by_thread.get(thread_name)
                repeat_after_s = float(report.get("repeat_after_s", 15.0) or 15.0)
                if (
                    last_report is not None
                    and last_report[0] == signature
                    and (now_monotonic - last_report[1]) < repeat_after_s
                ):
                    continue
                formatted_report = _format_stale_runtime_thread_report(report)
                print(formatted_report)
                _append_live_runtime_log(formatted_report)
                last_report_by_thread[thread_name] = (signature, now_monotonic)

    threading.Thread(
        target=_watchdog_worker,
        name="live-runtime-watchdog",
        daemon=True,
    ).start()


def _schedule_live_runtime_ui_heartbeat(
    root: tkinter.Misc,
    capture_state: CaptureState,
) -> None:
    """Emit one periodic UI-thread heartbeat so the watchdog can detect mainloop stalls."""

    mark_runtime_thread_progress(
        capture_state,
        "ui",
        "before_mainloop",
        detail="waiting for tkinter mainloop",
        blocked_hint="Tk mainloop has not started ticking yet",
        stale_after_s=6.0,
        repeat_after_s=12.0,
    )

    def _heartbeat() -> None:
        if not bool(getattr(root, "winfo_exists", lambda: False)()):
            return
        mark_runtime_thread_progress(
            capture_state,
            "ui",
            "mainloop_heartbeat",
            detail="tk after heartbeat",
            blocked_hint="Tk mainloop heartbeat stopped",
            stale_after_s=4.0,
            repeat_after_s=10.0,
        )
        root.after(1000, _heartbeat)

    root.after(1000, _heartbeat)


@dataclass
class NagaAnalyzerUiState:
    storage_state_path: Path
    raw_output_dir: Path
    query_state_provider: Callable[[], naga_analyzer.NagaQueryState | None] | None = None
    capture_state: CaptureState | None = None
    window: tkinter.Toplevel | None = None
    text_widget: tkinter.Text | None = None
    graph_canvas: tkinter.Canvas | None = None
    button_widget: tkinter.Button | None = None
    section_button_widgets: dict[str, tkinter.Button] = field(default_factory=dict)
    graph_metric_button_widgets: dict[str, tkinter.Button] = field(default_factory=dict)
    active_graph_metric: str = "ptev"
    active_section: str = NAGA_POPUP_SECTION_ALL
    in_flight: bool = False
    last_error_text: str = ""
    last_result: naga_analyzer.NagaAnalysisText | None = None
    auto_in_flight: bool = False
    auto_last_query_key: tuple[object, ...] | None = None
    auto_last_result_key: tuple[object, ...] | None = None
    auto_failed_query_key: tuple[object, ...] | None = None
    auto_error_text: str = ""
    auto_result: naga_analyzer.NagaAnalysisText | None = None
    auto_update_sequence: int = 0


def _build_naga_query_state_from_capture_state(
    capture_state: CaptureState | None,
) -> naga_analyzer.NagaQueryState | None:
    if capture_state is None:
        return None
    with capture_state.state_lock:
        return naga_analyzer.build_query_state_from_round_state(capture_state.current_round)


def _naga_query_key(
    query_state: naga_analyzer.NagaQueryState | None,
) -> tuple[object, ...] | None:
    if query_state is None:
        return None
    return (
        int(query_state.kyoku),
        int(query_state.honba),
        int(query_state.kyotaku),
        tuple(int(score) for score in query_state.scores),
        (
            int(query_state.oya_seat)
            if query_state.oya_seat is not None
            else None
        ),
    )


def _naga_auto_enabled_for_query_state(
    query_state: naga_analyzer.NagaQueryState | None,
) -> bool:
    return query_state is not None and int(query_state.kyoku) >= NAGA_AUTO_START_KYOKU


def _format_naga_pt_delta(value: float) -> str:
    return f"{float(value):+.1f}pt"


def _format_naga_auto_point(point: naga_analyzer.NagaGraphPoint | None) -> str:
    if point is None:
        return "-"
    return f"{point.label} {_format_naga_pt_delta(point.delta_ptev)}"


def _top_naga_points(
    points: Sequence[naga_analyzer.NagaGraphPoint],
    categories: set[str],
    *,
    limit: int,
    descending: bool,
) -> tuple[naga_analyzer.NagaGraphPoint, ...]:
    candidates = [point for point in points if point.category in categories]
    candidates.sort(key=lambda point: float(point.delta_ptev), reverse=descending)
    return tuple(candidates[: max(0, int(limit))])


def _build_naga_auto_result_line(
    result: naga_analyzer.NagaAnalysisText,
) -> str:
    # The table-bottom strip is a decision hint, not a full report. Keep only the branches that
    # change late-round dan-point tradeoffs: wins, deal-ins, and exhaustive draws.
    points = tuple(result.graph_points)
    base_point = next((point for point in points if point.category == "BASE"), None)
    base_text = (
        f"現状 {float(base_point.ptev):+.1f}pt"
        if base_point is not None
        else "現状 -"
    )
    win_points = _top_naga_points(points, {"RON+", "TSM+"}, limit=2, descending=True)
    houjuu_points = _top_naga_points(points, {"RON-"}, limit=1, descending=False)
    ryukyoku_best = _top_naga_points(points, {"RYK"}, limit=1, descending=True)
    ryukyoku_worst = _top_naga_points(points, {"RYK"}, limit=1, descending=False)
    win_text = "和了 " + " / ".join(_format_naga_auto_point(point) for point in win_points)
    if not win_points:
        win_text = "和了 -"
    houjuu_text = f"放銃 {_format_naga_auto_point(houjuu_points[0] if houjuu_points else None)}"
    if ryukyoku_best and ryukyoku_worst and ryukyoku_best[0] != ryukyoku_worst[0]:
        ryukyoku_text = (
            f"流局 {_format_naga_auto_point(ryukyoku_best[0])}"
            f"/{_format_naga_pt_delta(ryukyoku_worst[0].delta_ptev)}"
        )
    elif ryukyoku_best:
        ryukyoku_text = f"流局 {_format_naga_auto_point(ryukyoku_best[0])}"
    else:
        ryukyoku_text = "流局 -"
    return f"{base_text}  {win_text}  {houjuu_text}  {ryukyoku_text}"


def _build_naga_auto_panel_data(
    ui_state: NagaAnalyzerUiState | None,
) -> table_view.NagaAutoPanelData:
    # Auto data is polled by the renderer on every redraw. Return a small immutable DTO so the draw
    # layer never needs to know about Playwright, storage_state, or raw NAGA artifacts.
    if ui_state is None or ui_state.query_state_provider is None:
        return table_view.NagaAutoPanelData()
    query_state = ui_state.query_state_provider()
    if not _naga_auto_enabled_for_query_state(query_state):
        return table_view.NagaAutoPanelData()
    query_key = _naga_query_key(query_state)
    title_text = f"NAGA pt {query_state.round_text}" if query_state is not None else "NAGA pt"
    if ui_state.auto_in_flight and ui_state.auto_last_query_key == query_key:
        return table_view.NagaAutoPanelData(
            visible=True,
            title_text=title_text,
            lines=("照会中...",),
            status_kind="loading",
        )
    if ui_state.auto_result is not None and ui_state.auto_last_result_key == query_key:
        return table_view.NagaAutoPanelData(
            visible=True,
            title_text=title_text,
            lines=(_build_naga_auto_result_line(ui_state.auto_result),),
            status_kind="ready",
        )
    if ui_state.auto_error_text and ui_state.auto_failed_query_key == query_key:
        error_text = str(ui_state.auto_error_text).strip()
        if len(error_text) > NAGA_AUTO_ERROR_TEXT_MAX:
            error_text = f"{error_text[:NAGA_AUTO_ERROR_TEXT_MAX]}..."
        return table_view.NagaAutoPanelData(
            visible=True,
            title_text=title_text,
            lines=(f"NAGA取得失敗: {error_text}",),
            status_kind="error",
        )
    return table_view.NagaAutoPanelData(
        visible=True,
        title_text=title_text,
        lines=("照会待ち",),
        status_kind="waiting",
    )


def _format_naga_popup_text(
    storage_state_path: Path,
    *,
    title: str,
    body: str,
    query_state: naga_analyzer.NagaQueryState | None = None,
) -> str:
    lines = [title]
    if query_state is not None:
        score_text = " / ".join(f"{score * 100}点" for score in query_state.scores)
        lines.append(f"局面: {query_state.round_text}")
        lines.append(f"持ち点: {score_text}")
    lines.append(f"ログイン状態: {storage_state_path}")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def _naga_login_command_text(storage_state_path: Path) -> str:
    return f"python -m naga_ptev.cli login --storage {storage_state_path}"


def _format_naga_error_body(
    storage_state_path: Path,
    raw_error_text: str,
) -> str:
    normalized_error_text = str(raw_error_text or "").strip()
    if "Saved NAGA session is not authenticated anymore" in normalized_error_text:
        return (
            "保存済みのNAGAログイン状態が期限切れです。\n\n"
            "この機能は、普段使っているChromeではなく、下のPlaywright用ログイン状態ファイルを使います。\n\n"
            "別ターミナルで一度実行してください:\n"
            f"{_naga_login_command_text(storage_state_path)}\n\n"
            "必要ならOSの資格情報ストアへログイン情報を保存できます:\n"
            "python -m naga_ptev.cli store-login\n\n"
            "開いたPlaywrightブラウザでログインし、そのターミナルでEnterを押してください。"
        )
    if "Storage state not found" in normalized_error_text:
        return (
            "保存済みのNAGAログイン状態が見つかりません。\n\n"
            "資格情報が保存済みなら自動作成を試します。失敗する場合は別ターミナルで実行してください:\n"
            f"{_naga_login_command_text(storage_state_path)}\n\n"
            "先に資格情報だけ保存する場合:\n"
            "python -m naga_ptev.cli store-login"
        )
    if "Saved NAGA login state does not exist yet" in normalized_error_text:
        return (
            "NAGAログイン状態がまだ作成されておらず、自動ログインでも作成できませんでした。\n\n"
            "ニコニコ側で追加確認が必要な場合があります。別ターミナルで実行してください:\n"
            f"{_naga_login_command_text(storage_state_path)}\n\n"
            "開いたPlaywrightブラウザで一度ログインを完了してください。"
        )
    return normalized_error_text


def _format_naga_result_popup_text(
    storage_state_path: Path,
    result: naga_analyzer.NagaAnalysisText,
    *,
    section: str = NAGA_POPUP_SECTION_ALL,
) -> str:
    if section == NAGA_POPUP_SECTION_3900:
        title = f"{NAGA_POPUP_TITLE} / 3900直撃"
        body_lines = [result.ron_3900_text or "この項目のデータはありません。"]
    elif section == NAGA_POPUP_SECTION_MANGAN:
        title = f"{NAGA_POPUP_TITLE} / 満貫ツモ"
        body_lines = [result.mangan_tsumo_text or "この項目のデータはありません。"]
    else:
        title = NAGA_POPUP_TITLE
        body_lines = list(result.summary_lines)
        if result.raw_artifact_path is not None:
            body_lines.append(f"生レスポンス: {result.raw_artifact_path}")
        body_lines.append("")
        body_lines.append(result.detail_text)
    if result.raw_artifact_path is not None and section != NAGA_POPUP_SECTION_ALL:
        body_lines.append("")
        body_lines.append(f"生レスポンス: {result.raw_artifact_path}")
    return _format_naga_popup_text(
        storage_state_path,
        title=title,
        body="\n".join(body_lines),
        query_state=result.query_state,
    )


def _refresh_naga_popup_section_buttons(ui_state: NagaAnalyzerUiState) -> None:
    has_result = ui_state.last_result is not None and not ui_state.in_flight and not ui_state.last_error_text
    for section, _label in NAGA_POPUP_SECTION_LABELS:
        button_widget = ui_state.section_button_widgets.get(section)
        if button_widget is None or not button_widget.winfo_exists():
            continue
        is_active = ui_state.active_section == section
        background = (
            table_view.HAND_AUTO_BUTTON_ON_FILL
            if is_active and has_result
            else "#16202c"
        )
        foreground = table_view.HAND_AUTO_BUTTON_TEXT if has_result or is_active else "#9aa4b5"
        button_widget.configure(
            state=(tkinter.NORMAL if has_result else tkinter.DISABLED),
            bg=background,
            activebackground=background,
            fg=foreground,
            activeforeground=foreground,
        )


def _show_naga_result_for_active_section(ui_state: NagaAnalyzerUiState) -> None:
    result = ui_state.last_result
    if result is None:
        return
    _draw_naga_graph(ui_state)
    _set_naga_popup_text(
        ui_state,
        _format_naga_result_popup_text(
            ui_state.storage_state_path,
            result,
            section=ui_state.active_section,
        ),
    )


def _naga_graph_metric_value(point: naga_analyzer.NagaGraphPoint, metric: str) -> float:
    if metric == "p1":
        return float(point.p1) * 100.0
    if metric == "p2":
        return float(point.p2) * 100.0
    if metric == "p4":
        return float(point.p4) * 100.0
    return float(point.ptev)


def _format_naga_graph_axis_value(value: float, metric: str) -> str:
    if metric in {"p1", "p2", "p4"}:
        return f"{value:.1f}%"
    return f"{value:+.1f}"


def _refresh_naga_graph_metric_buttons(ui_state: NagaAnalyzerUiState) -> None:
    has_result = ui_state.last_result is not None and not ui_state.in_flight and not ui_state.last_error_text
    for metric, _label in NAGA_GRAPH_METRICS:
        button_widget = ui_state.graph_metric_button_widgets.get(metric)
        if button_widget is None or not button_widget.winfo_exists():
            continue
        is_active = ui_state.active_graph_metric == metric
        background = table_view.HAND_AUTO_BUTTON_ON_FILL if is_active and has_result else "#16202c"
        foreground = table_view.HAND_AUTO_BUTTON_TEXT if has_result or is_active else "#9aa4b5"
        button_widget.configure(
            state=(tkinter.NORMAL if has_result else tkinter.DISABLED),
            bg=background,
            activebackground=background,
            fg=foreground,
            activeforeground=foreground,
        )


def _handle_naga_graph_metric_click(ui_state: NagaAnalyzerUiState, metric: str) -> None:
    ui_state.active_graph_metric = str(metric or "ptev")
    _refresh_naga_graph_metric_buttons(ui_state)
    _draw_naga_graph(ui_state)


def _draw_naga_graph(ui_state: NagaAnalyzerUiState) -> None:
    canvas = ui_state.graph_canvas
    if canvas is None or not canvas.winfo_exists():
        return
    canvas.delete("all")
    width = max(1, int(canvas.winfo_width() or canvas.winfo_reqwidth()))
    height = max(1, int(canvas.winfo_height() or canvas.winfo_reqheight()))
    canvas.create_rectangle(0, 0, width, height, fill="#0f1722", outline="")

    result = ui_state.last_result
    points = tuple(result.graph_points) if result is not None else ()
    if not points:
        canvas.create_text(width // 2, height // 2, text="グラフデータなし", fill="#9aa4b5", font=("Yu Gothic UI", 9))
        return

    metric = ui_state.active_graph_metric
    metric_label = dict(NAGA_GRAPH_METRICS).get(metric, "ptEV")
    values = [_naga_graph_metric_value(point, metric) for point in points]
    min_value = min(values)
    max_value = max(values)
    if math.isclose(min_value, max_value):
        min_value -= 1.0
        max_value += 1.0
    padding = max(0.5, (max_value - min_value) * 0.08)
    min_value -= padding
    max_value += padding

    left = 54
    right = max(left + 20, width - 14)
    top = 20
    bottom = max(top + 20, height - 34)
    plot_width = max(1, right - left)
    plot_height = max(1, bottom - top)

    def _x(index: int) -> float:
        if len(points) <= 1:
            return left + plot_width / 2
        return left + plot_width * index / (len(points) - 1)

    def _y(value: float) -> float:
        return bottom - ((value - min_value) / (max_value - min_value)) * plot_height

    grid_color = "#263241"
    axis_color = "#526074"
    for tick_index in range(5):
        ratio = tick_index / 4
        value = min_value + (max_value - min_value) * ratio
        y = _y(value)
        canvas.create_line(left, y, right, y, fill=grid_color)
        canvas.create_text(left - 8, y, text=_format_naga_graph_axis_value(value, metric), fill="#aeb8c8", anchor="e", font=("Consolas", 8))
    canvas.create_line(left, top, left, bottom, fill=axis_color)
    canvas.create_line(left, bottom, right, bottom, fill=axis_color)

    base_value = _naga_graph_metric_value(points[0], metric)
    base_y = _y(base_value)
    canvas.create_line(left, base_y, right, base_y, fill="#627086", dash=(3, 3))
    canvas.create_text(left, 8, text=f"自家 {metric_label}", fill="#d7deea", anchor="w", font=("Yu Gothic UI", 9, "bold"))

    colors = {
        "BASE": "#f8fafc",
        "RON+": "#60a5fa",
        "TSM+": "#34d399",
        "RON-": "#fb7185",
        "RYK": "#fbbf24",
    }
    legend_labels = {
        "RON+": "ロン和了",
        "TSM+": "ツモ和了",
        "RON-": "放銃",
        "RYK": "流局",
    }
    for index, point in enumerate(points):
        x = _x(index)
        value = _naga_graph_metric_value(point, metric)
        y = _y(value)
        color = colors.get(point.category, "#d7deea")
        if index > 0:
            canvas.create_line(_x(0), base_y, x, y, fill=color, width=1)
        canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="")
        if index == 0 or index == len(points) - 1 or index % 3 == 1:
            canvas.create_text(x, bottom + 12, text=point.label, fill="#aeb8c8", font=("Consolas", 8))
    legend_x = right
    for category in ("RON+", "TSM+", "RON-", "RYK"):
        legend_x -= 64
        canvas.create_text(
            legend_x,
            8,
            text=legend_labels[category],
            fill=colors[category],
            anchor="w",
            font=("Yu Gothic UI", 8),
        )


def _handle_naga_popup_section_click(
    ui_state: NagaAnalyzerUiState,
    section: str,
) -> None:
    ui_state.active_section = str(section or NAGA_POPUP_SECTION_ALL)
    _refresh_naga_popup_section_buttons(ui_state)
    _refresh_naga_graph_metric_buttons(ui_state)
    _show_naga_result_for_active_section(ui_state)


def _set_naga_popup_text(
    ui_state: NagaAnalyzerUiState,
    text: str,
) -> None:
    text_widget = ui_state.text_widget
    if text_widget is None or not text_widget.winfo_exists():
        return
    text_widget.configure(state=tkinter.NORMAL)
    text_widget.delete("1.0", tkinter.END)
    text_widget.insert("1.0", text)
    text_widget.configure(state=tkinter.DISABLED)


def _clear_naga_graph(ui_state: NagaAnalyzerUiState, message: str = "") -> None:
    canvas = ui_state.graph_canvas
    if canvas is None or not canvas.winfo_exists():
        return
    canvas.delete("all")
    width = max(1, int(canvas.winfo_width() or canvas.winfo_reqwidth()))
    height = max(1, int(canvas.winfo_height() or canvas.winfo_reqheight()))
    canvas.create_rectangle(0, 0, width, height, fill="#0f1722", outline="")
    if message:
        canvas.create_text(width // 2, height // 2, text=message, fill="#9aa4b5", font=("Yu Gothic UI", 9))


def _ensure_naga_popup(
    root: tkinter.Tk,
    ui_state: NagaAnalyzerUiState,
) -> None:
    window = ui_state.window
    if window is not None and window.winfo_exists():
        window.deiconify()
        window.lift()
        window.focus_force()
        _refresh_naga_popup_section_buttons(ui_state)
        _refresh_naga_graph_metric_buttons(ui_state)
        _draw_naga_graph(ui_state)
        return

    window = tkinter.Toplevel(root)
    window.title(NAGA_POPUP_TITLE)
    window.geometry(f"{NAGA_WINDOW_WIDTH}x{NAGA_WINDOW_HEIGHT}")
    window.configure(bg="#101820")
    container = tkinter.Frame(window, bg="#101820")
    container.pack(fill=tkinter.BOTH, expand=True, padx=8, pady=8)
    toolbar = tkinter.Frame(container, bg="#101820")
    toolbar.grid(row=0, column=0, sticky="w", pady=(0, 6))
    for column_index, (section, label) in enumerate(NAGA_POPUP_SECTION_LABELS):
        section_button = tkinter.Button(
            toolbar,
            text=label,
            command=lambda selected_section=section: _handle_naga_popup_section_click(ui_state, selected_section),
            relief=tkinter.FLAT,
            bd=1,
            bg="#16202c",
            fg="#d7deea",
            activebackground="#29415d",
            activeforeground="#f8fafc",
            font=("Yu Gothic UI", 8, "bold"),
            padx=8,
            pady=2,
            highlightthickness=0,
        )
        section_button.grid(row=0, column=column_index, sticky="w", padx=(0, 6))
        ui_state.section_button_widgets[section] = section_button
    metric_toolbar = tkinter.Frame(container, bg="#101820")
    metric_toolbar.grid(row=1, column=0, sticky="w", pady=(0, 6))
    for column_index, (metric, label) in enumerate(NAGA_GRAPH_METRICS):
        metric_button = tkinter.Button(
            metric_toolbar,
            text=label,
            command=lambda selected_metric=metric: _handle_naga_graph_metric_click(ui_state, selected_metric),
            relief=tkinter.FLAT,
            bd=1,
            bg="#16202c",
            fg="#d7deea",
            activebackground="#29415d",
            activeforeground="#f8fafc",
            font=("Yu Gothic UI", 8, "bold"),
            padx=8,
            pady=2,
            highlightthickness=0,
        )
        metric_button.grid(row=0, column=column_index, sticky="w", padx=(0, 6))
        ui_state.graph_metric_button_widgets[metric] = metric_button
    graph_canvas = tkinter.Canvas(
        container,
        bg="#0f1722",
        height=190,
        relief=tkinter.FLAT,
        bd=0,
        highlightthickness=0,
    )
    graph_canvas.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    graph_canvas.bind("<Configure>", lambda _event: _draw_naga_graph(ui_state))
    ui_state.graph_canvas = graph_canvas
    text_widget = tkinter.Text(
        container,
        wrap=tkinter.NONE,
        bg="#11161f",
        fg="#d7deea",
        insertbackground="#f8fafc",
        relief=tkinter.FLAT,
        bd=0,
        font=("Yu Gothic UI", 10),
        padx=10,
        pady=10,
    )
    y_scrollbar = tkinter.Scrollbar(container, orient=tkinter.VERTICAL, command=text_widget.yview)
    x_scrollbar = tkinter.Scrollbar(container, orient=tkinter.HORIZONTAL, command=text_widget.xview)
    text_widget.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(3, weight=1)
    text_widget.grid(row=3, column=0, sticky="nsew")
    y_scrollbar.grid(row=3, column=1, sticky="ns")
    x_scrollbar.grid(row=4, column=0, sticky="ew")
    text_widget.configure(state=tkinter.DISABLED)

    def _handle_close() -> None:
        ui_state.window = None
        ui_state.text_widget = None
        ui_state.graph_canvas = None
        ui_state.section_button_widgets = {}
        ui_state.graph_metric_button_widgets = {}
        try:
            window.destroy()
        except tkinter.TclError:
            pass

    window.protocol("WM_DELETE_WINDOW", _handle_close)
    ui_state.window = window
    ui_state.text_widget = text_widget
    _refresh_naga_popup_section_buttons(ui_state)
    _refresh_naga_graph_metric_buttons(ui_state)
    _clear_naga_graph(ui_state, "NAGA段位分析を実行")


def _refresh_naga_button_widget(ui_state: NagaAnalyzerUiState) -> None:
    button_widget = ui_state.button_widget
    if button_widget is None or not button_widget.winfo_exists():
        return
    if ui_state.in_flight or ui_state.auto_in_flight:
        button_widget.configure(
            text="NAGA中",
            bg=table_view.HAND_AUTO_BUTTON_RUN_FILL,
            activebackground=table_view.HAND_AUTO_BUTTON_RUN_FILL,
            fg=table_view.HAND_AUTO_BUTTON_TEXT,
            activeforeground=table_view.HAND_AUTO_BUTTON_TEXT,
        )
        return
    if ui_state.last_error_text:
        button_widget.configure(
            text="NAGA失敗",
            bg=table_view.HAND_AUTO_BUTTON_ERROR_FILL,
            activebackground=table_view.HAND_AUTO_BUTTON_ERROR_FILL,
            fg=table_view.HAND_AUTO_BUTTON_TEXT,
            activeforeground=table_view.HAND_AUTO_BUTTON_TEXT,
        )
        return
    if ui_state.last_result is not None:
        button_widget.configure(
            text="NAGA完了",
            bg=table_view.HAND_AUTO_BUTTON_ON_FILL,
            activebackground=table_view.HAND_AUTO_BUTTON_ON_FILL,
            fg=table_view.HAND_AUTO_BUTTON_TEXT,
            activeforeground=table_view.HAND_AUTO_BUTTON_TEXT,
        )
        return
    button_widget.configure(
        text="NAGA段位",
        bg="#16202c",
        activebackground="#29415d",
        fg="#d7deea",
        activeforeground="#f8fafc",
    )


def _handle_naga_button_click(
    root: tkinter.Tk,
    ui_state: NagaAnalyzerUiState,
) -> None:
    _ensure_naga_popup(root, ui_state)
    query_state = (
        ui_state.query_state_provider()
        if ui_state.query_state_provider is not None
        else None
    )
    if query_state is None:
        ui_state.last_error_text = "局面情報なし"
        _refresh_naga_button_widget(ui_state)
        _clear_naga_graph(ui_state, "局面情報なし")
        _set_naga_popup_text(
            ui_state,
            _format_naga_popup_text(
                ui_state.storage_state_path,
                title=NAGA_POPUP_TITLE,
                body="現在局面の情報がまだ取得できていません。",
            ),
        )
        _refresh_naga_popup_section_buttons(ui_state)
        _refresh_naga_graph_metric_buttons(ui_state)
        return
    if not ui_state.storage_state_path.exists():
        ui_state.last_error_text = "ログイン状態なし"
        _refresh_naga_button_widget(ui_state)
        _clear_naga_graph(ui_state, "ログイン状態なし")
        _set_naga_popup_text(
            ui_state,
            _format_naga_popup_text(
                ui_state.storage_state_path,
                title=NAGA_POPUP_TITLE,
                body=(
                    "保存済みのNAGAログイン状態が見つかりません。\n\n"
                    "別ターミナルで一度実行してください:\n"
                    f"{_naga_login_command_text(ui_state.storage_state_path)}"
                ),
                query_state=query_state,
            ),
        )
        _refresh_naga_popup_section_buttons(ui_state)
        _refresh_naga_graph_metric_buttons(ui_state)
        return
    if ui_state.in_flight or ui_state.auto_in_flight:
        _clear_naga_graph(ui_state, "NAGA照会中")
        _set_naga_popup_text(
            ui_state,
            _format_naga_popup_text(
                ui_state.storage_state_path,
                title=NAGA_POPUP_TITLE,
                body="NAGAの段位ポイント分析を取得しています。",
                query_state=query_state,
            ),
        )
        return

    ui_state.in_flight = True
    ui_state.last_error_text = ""
    ui_state.active_section = NAGA_POPUP_SECTION_ALL
    _refresh_naga_button_widget(ui_state)
    _refresh_naga_popup_section_buttons(ui_state)
    _refresh_naga_graph_metric_buttons(ui_state)
    _clear_naga_graph(ui_state, "NAGA照会中")
    _set_naga_popup_text(
        ui_state,
        _format_naga_popup_text(
            ui_state.storage_state_path,
            title=NAGA_POPUP_TITLE,
            body="NAGAの段位ポイント分析を取得しています。",
            query_state=query_state,
        ),
    )
    table_view.begin_thread_activity_notice("NAGA段位")

    def _schedule_on_ui_thread(callback: Callable[[], None]) -> None:
        try:
            root.after(0, callback)
        except tkinter.TclError:
            pass

    def _worker() -> None:
        capture_state = ui_state.capture_state
        if capture_state is not None:
            mark_runtime_thread_progress(
                capture_state,
                "naga",
                "query_start",
                detail=query_state.round_text,
                blocked_hint="NAGA段位ポイント分析を照会中",
                stale_after_s=10.0,
                repeat_after_s=20.0,
            )
        try:
            result = naga_analyzer.analyze_naga_text(
                query_state,
                storage_state_path=ui_state.storage_state_path,
                raw_output_dir=ui_state.raw_output_dir,
            )
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"

            def _apply_error() -> None:
                ui_state.in_flight = False
                ui_state.last_error_text = error_text
                if _naga_auto_enabled_for_query_state(query_state):
                    ui_state.auto_failed_query_key = _naga_query_key(query_state)
                    ui_state.auto_error_text = error_text
                    ui_state.auto_result = None
                    ui_state.auto_last_result_key = None
                    ui_state.auto_update_sequence += 1
                _refresh_naga_button_widget(ui_state)
                _refresh_naga_popup_section_buttons(ui_state)
                _refresh_naga_graph_metric_buttons(ui_state)
                _clear_naga_graph(ui_state, "NAGA照会失敗")
                _set_naga_popup_text(
                    ui_state,
                    _format_naga_popup_text(
                        ui_state.storage_state_path,
                        title=NAGA_POPUP_TITLE,
                        body=_format_naga_error_body(ui_state.storage_state_path, error_text),
                        query_state=query_state,
                    ),
                )

            _schedule_on_ui_thread(_apply_error)
            if capture_state is not None:
                mark_runtime_thread_progress(
                    capture_state,
                    "naga",
                    "query_error",
                    detail=error_text,
                    blocked_hint="NAGA段位ポイント分析の照会に失敗",
                    stale_after_s=10.0,
                    repeat_after_s=20.0,
                )
        else:
            def _apply_result() -> None:
                ui_state.in_flight = False
                ui_state.last_error_text = ""
                ui_state.last_result = result
                if _naga_auto_enabled_for_query_state(query_state):
                    ui_state.auto_result = result
                    ui_state.auto_last_result_key = _naga_query_key(query_state)
                    ui_state.auto_failed_query_key = None
                    ui_state.auto_error_text = ""
                    ui_state.auto_update_sequence += 1
                _refresh_naga_button_widget(ui_state)
                _refresh_naga_popup_section_buttons(ui_state)
                _refresh_naga_graph_metric_buttons(ui_state)
                _show_naga_result_for_active_section(ui_state)

            _schedule_on_ui_thread(_apply_result)
            if capture_state is not None:
                mark_runtime_thread_progress(
                    capture_state,
                    "naga",
                    "query_ready",
                    detail=query_state.round_text,
                    blocked_hint="NAGA段位ポイント分析の表示待ち",
                    stale_after_s=10.0,
                    repeat_after_s=20.0,
                )
        finally:
            table_view.finish_thread_activity_notice("NAGA段位")

    threading.Thread(
        target=_worker,
        name="naga-analyzer-query",
        daemon=True,
    ).start()


def _start_naga_auto_query(
    root: tkinter.Tk,
    ui_state: NagaAnalyzerUiState,
    query_state: naga_analyzer.NagaQueryState,
) -> None:
    # Query keys prevent the 1-second scheduler from stacking multiple Playwright calls for the
    # same round while a previous NAGA auto query is still in flight.
    query_key = _naga_query_key(query_state)
    if query_key is None or ui_state.in_flight or ui_state.auto_in_flight:
        return
    if not ui_state.storage_state_path.exists():
        ui_state.auto_last_query_key = query_key
        ui_state.auto_failed_query_key = query_key
        ui_state.auto_error_text = "ログイン状態なし"
        ui_state.auto_result = None
        ui_state.auto_last_result_key = None
        ui_state.auto_update_sequence += 1
        return

    ui_state.auto_in_flight = True
    ui_state.auto_last_query_key = query_key
    ui_state.auto_failed_query_key = None
    ui_state.auto_error_text = ""
    ui_state.auto_update_sequence += 1
    table_view.begin_thread_activity_notice("NAGA auto")

    def _schedule_on_ui_thread(callback: Callable[[], None]) -> None:
        try:
            root.after(0, callback)
        except tkinter.TclError:
            pass

    def _current_query_key() -> tuple[object, ...] | None:
        provider = ui_state.query_state_provider
        if provider is None:
            return None
        return _naga_query_key(provider())

    def _worker() -> None:
        capture_state = ui_state.capture_state
        if capture_state is not None:
            mark_runtime_thread_progress(
                capture_state,
                "naga-auto",
                "query_start",
                detail=query_state.round_text,
                blocked_hint="NAGA auto query running",
                stale_after_s=10.0,
                repeat_after_s=20.0,
            )
        try:
            result = naga_analyzer.analyze_naga_text(
                query_state,
                storage_state_path=ui_state.storage_state_path,
                raw_output_dir=ui_state.raw_output_dir,
            )
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"

            def _apply_error() -> None:
                ui_state.auto_in_flight = False
                if _current_query_key() != query_key:
                    ui_state.auto_update_sequence += 1
                    return
                ui_state.auto_failed_query_key = query_key
                ui_state.auto_error_text = error_text
                ui_state.auto_result = None
                ui_state.auto_last_result_key = None
                ui_state.auto_update_sequence += 1

            _schedule_on_ui_thread(_apply_error)
            if capture_state is not None:
                mark_runtime_thread_progress(
                    capture_state,
                    "naga-auto",
                    "query_error",
                    detail=error_text,
                    blocked_hint="NAGA auto query failed",
                    stale_after_s=10.0,
                    repeat_after_s=20.0,
                )
        else:

            def _apply_result() -> None:
                ui_state.auto_in_flight = False
                if _current_query_key() != query_key:
                    ui_state.auto_update_sequence += 1
                    return
                ui_state.auto_result = result
                ui_state.auto_last_result_key = query_key
                ui_state.auto_failed_query_key = None
                ui_state.auto_error_text = ""
                ui_state.last_result = result
                ui_state.last_error_text = ""
                ui_state.auto_update_sequence += 1
                _refresh_naga_button_widget(ui_state)
                if ui_state.window is not None and ui_state.window.winfo_exists() and not ui_state.in_flight:
                    _refresh_naga_popup_section_buttons(ui_state)
                    _refresh_naga_graph_metric_buttons(ui_state)
                    _show_naga_result_for_active_section(ui_state)

            _schedule_on_ui_thread(_apply_result)
            if capture_state is not None:
                mark_runtime_thread_progress(
                    capture_state,
                    "naga-auto",
                    "query_ready",
                    detail=query_state.round_text,
                    blocked_hint="NAGA auto query displayed",
                    stale_after_s=10.0,
                    repeat_after_s=20.0,
                )
        finally:
            table_view.finish_thread_activity_notice("NAGA auto")

    threading.Thread(
        target=_worker,
        name="naga-analyzer-auto-query",
        daemon=True,
    ).start()


def _schedule_naga_auto_refresh(
    root: tkinter.Tk,
    ui_state: NagaAnalyzerUiState | None,
) -> None:
    if ui_state is None:
        return

    def _tick() -> None:
        # Capture updates, manual redraws, and NAGA popup actions all mutate the same UI state.  A
        # simple polling tick plus query-key de-duplication keeps this path deterministic.
        try:
            if not bool(getattr(root, "winfo_exists", lambda: False)()):
                return
        except tkinter.TclError:
            return
        query_state = (
            ui_state.query_state_provider()
            if ui_state.query_state_provider is not None
            else None
        )
        if not _naga_auto_enabled_for_query_state(query_state):
            if (
                ui_state.auto_result is not None
                or ui_state.auto_error_text
                or ui_state.auto_last_query_key is not None
            ):
                ui_state.auto_result = None
                ui_state.auto_last_result_key = None
                ui_state.auto_failed_query_key = None
                ui_state.auto_error_text = ""
                ui_state.auto_last_query_key = None
                ui_state.auto_update_sequence += 1
            root.after(NAGA_AUTO_REFRESH_MS, _tick)
            return

        query_key = _naga_query_key(query_state)
        if (
            query_state is not None
            and query_key is not None
            and not ui_state.auto_in_flight
            and ui_state.auto_last_result_key != query_key
            and ui_state.auto_failed_query_key != query_key
        ):
            _start_naga_auto_query(root, ui_state, query_state)
        root.after(NAGA_AUTO_REFRESH_MS, _tick)

    root.after(NAGA_AUTO_REFRESH_MS, _tick)


def _install_naga_button(
    root: tkinter.Tk,
    *,
    capture_state: CaptureState | None,
    query_state_provider: Callable[[], naga_analyzer.NagaQueryState | None] | None,
    ui_state: NagaAnalyzerUiState | None = None,
) -> NagaAnalyzerUiState | None:
    if not bool(getattr(root, "winfo_exists", lambda: False)()):
        return None
    if ui_state is None:
        ui_state = NagaAnalyzerUiState(
            storage_state_path=naga_analyzer.resolve_storage_state_path(),
            raw_output_dir=naga_analyzer.resolve_raw_output_dir(),
            query_state_provider=query_state_provider,
            capture_state=capture_state,
        )
    else:
        ui_state.query_state_provider = query_state_provider
        ui_state.capture_state = capture_state
    button_widget = tkinter.Button(
        root,
        text="NAGA段位",
        command=lambda: _handle_naga_button_click(root, ui_state),
        relief=tkinter.FLAT,
        bd=1,
        bg="#16202c",
        fg="#d7deea",
        activebackground="#29415d",
        activeforeground="#f8fafc",
        font=("Consolas", 8, "bold"),
        padx=8,
        pady=2,
        highlightthickness=0,
        width=10,
    )
    button_widget.place(x=NAGA_BUTTON_X, y=NAGA_BUTTON_Y)
    ui_state.button_widget = button_widget
    _refresh_naga_button_widget(ui_state)
    return ui_state


@dataclass(frozen=True)
class LiveTableSnapshot:
    """Immutable live-table snapshot consumed by one UI redraw pass."""

    discard_map: dict[Player, list[object]]
    discard_red_tint_indices_by_seat: dict[int, tuple[int, ...]]
    hand_tiles: list[int]
    hand_draw_tile: int | None
    hand_danger_percentages: list[dict[int, object]]
    opponent_suji_panel_summaries: dict[int, object]
    player_push_alert_percentages: dict[int, object]
    player_alert_indicators_by_seat: dict[int, tuple[table_view.PlayerAlertIndicator, ...]]
    player_score_diffs_by_seat: dict[int, int]
    player_names_by_seat: dict[int, str]
    meld_tiles: list[int]
    dora_indicator_tiles: list[int]
    round_events: list[object]
    round_info_panel: table_view.RoundInfoPanelData
    melds_by_player: dict[Player, list[Meld]]
    visible_summary: VisibleTileSummary
    round_identity: object | None
    refresh_token: object | None
    hand_recommendation_request_context: PystyleDisplayContext
    table_situation_auto_scores_by_seat: dict[int, tuple[float, ...]] = field(default_factory=dict)
    same_jun_marker_indices_by_seat: dict[int, frozenset[int]] = field(default_factory=dict)


@dataclass(frozen=True)
class LiveSujiComputationBundle:
    """Heavy suji-derived payload computed off the Tk redraw path."""

    source_refresh_token: int
    round_identity: object | None
    input_signature: tuple[object, ...]
    hand_danger_percentages: list[dict[int, object]]
    opponent_suji_panel_summaries: dict[int, object]
    player_push_alert_percentages: dict[int, object]
    player_alert_indicators_by_seat: dict[int, tuple[table_view.PlayerAlertIndicator, ...]]


@dataclass(frozen=True)
class LiveSujiComputationJob:
    """One pending background suji computation request for a copied live snapshot."""

    snapshot_state: CaptureState
    visible_summary: VisibleTileSummary
    source_refresh_token: int
    round_identity: object | None
    input_signature: tuple[object, ...]


@dataclass(frozen=True)
class LiveRedTintComputationBundle:
    """Red-tint payload computed outside the Tk redraw path."""

    source_refresh_token: int
    round_identity: object | None
    discard_red_tint_indices_by_seat: dict[int, tuple[int, ...]]


@dataclass(frozen=True)
class LiveRedTintComputationJob:
    """One pending background red-tint computation request for a copied live snapshot."""

    snapshot_state: CaptureState
    source_refresh_token: int
    round_identity: object | None


@dataclass
class LiveSujiAsyncState:
    """Mutable async bookkeeping for the current live suji bundle worker."""

    pending_job: LiveSujiComputationJob | None = None
    worker_running: bool = False
    wake_event: threading.Event = field(default_factory=threading.Event)
    in_flight_source_refresh_token: int | None = None
    completed_bundle: LiveSujiComputationBundle | None = None
    completed_source_refresh_token: int | None = None
    completed_round_identity: object | None = None
    update_sequence: int = 0
    last_error: str = ""


@dataclass
class LiveRedTintAsyncState:
    """Mutable async bookkeeping for the current live red-tint worker."""

    pending_job: LiveRedTintComputationJob | None = None
    worker_running: bool = False
    wake_event: threading.Event = field(default_factory=threading.Event)
    in_flight_source_refresh_token: int | None = None
    completed_bundle: LiveRedTintComputationBundle | None = None
    completed_source_refresh_token: int | None = None
    completed_round_identity: object | None = None
    update_sequence: int = 0
    last_error: str = ""


_LIVE_DISCARD_RED_TINT_CACHE_SIGNATURE: tuple[object, ...] | None = None
_LIVE_DISCARD_RED_TINT_CACHE_VALUE: dict[int, tuple[int, ...]] = {}


def _iter_xml_url_list(url_list_path: Path) -> Iterator[str]:
    """Yield newline-delimited XML/viewer URLs from a text file."""

    with url_list_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            normalized = raw_line.strip()
            if not normalized or normalized.startswith("#"):
                continue
            yield normalized


def _build_hand_recommendation_panel_data(
    recommendation_service: HandRecommendationService,
) -> table_view.HandRecommendationPanelData:
    """Convert the service snapshot into the table renderer's compact panel payload."""

    snapshot = recommendation_service.snapshot()
    return table_view.HandRecommendationPanelData(
        items=tuple(
            table_view.HandRecommendationItem(
                rank=item.rank,
                tile_37=item.tile_37,
                tile_text=item.tile_text,
                expected_value=item.expected_value,
                expected_value_text=item.expected_value_text,
                win_probability=item.win_probability,
            )
            for item in snapshot.items
        ),
        hand_key=tuple(snapshot.hand_key),
        shanten=snapshot.shanten,
        round_token=str(snapshot.round_token),
        request_context_key=tuple(snapshot.request_context_key),
        top_expected_value=(
            float(snapshot.items[0].expected_value)
            if snapshot.items
            else None
        ),
        subtitle_text=snapshot.subtitle_text,
        status_text=snapshot.status_text,
        is_loading=bool(snapshot.is_loading),
    )


def _build_combined_refresh_token_provider(
    base_refresh_token: object | None,
    base_refresh_token_provider: Callable[[], object | None] | None,
    recommendation_service: HandRecommendationService,
    *,
    extra_update_sequence_provider: Callable[[], object | None] | None = None,
) -> tuple[Callable[[], tuple[object | None, int] | tuple[object | None, int, object | None]], tuple[object | None, int] | tuple[object | None, int, object | None]]:
    """Combine live redraw tokens with recommendation-service updates."""

    def _combined_refresh_token() -> tuple[object | None, int] | tuple[object | None, int, object | None]:
        base_token = (
            base_refresh_token_provider()
            if base_refresh_token_provider is not None
            else base_refresh_token
        )
        if extra_update_sequence_provider is not None:
            return (
                base_token,
                recommendation_service.update_sequence,
                extra_update_sequence_provider(),
            )
        return (base_token, recommendation_service.update_sequence)

    return _combined_refresh_token, _combined_refresh_token()


def _remember_visible_pystyle_history(
    capture_state: CaptureState,
    hand_tiles_37: Sequence[int],
    hand_recommendation_panel: table_view.HandRecommendationPanelData,
    display_context: PystyleDisplayContext,
) -> None:
    """Cache the currently visible AI TOP3 result so the next self discard row can persist it."""

    if not display_context.allow_history_persist:
        return
    ranked_entries = tuple(
        (
            str(item.tile_text).strip(),
            str(item.expected_value_text).strip(),
        )
        for item in hand_recommendation_panel.items[:3]
        if str(item.tile_text).strip() and str(item.expected_value_text).strip()
    )
    if not ranked_entries:
        return
    remember_pystyle_self_history(
        capture_state,
        list(hand_tiles_37),
        ranked_entries,
        blocking=False,
    )


def _load_capture_state_from_xml_url(
    input_url: str,
    *,
    self_abs_seat: int | None = None,
    self_player_name: str | None = None,
) -> CaptureState:
    """Fetch one XML URL, build capture state, and backfill the CSV DB."""

    fetched_xml = fetch_xml_text_from_url(input_url)
    effective_self_abs_seat = (
        self_abs_seat if self_abs_seat is not None else fetched_xml.resolved.viewer_tw
    )
    capture_state = load_from_xml_text(
        fetched_xml.xml_text,
        self_abs_seat=effective_self_abs_seat,
        self_player_name=self_player_name,
    )
    try:
        log_id = extract_log_id(fetched_xml.resolved.xml_url) or extract_log_id(input_url)
        hanchan_date_override = log_id[:8] if log_id and len(log_id) >= 8 else None
        import_result = import_xml_discard_hands(
            fetched_xml.xml_text,
            self_abs_seat=effective_self_abs_seat,
            self_player_name=self_player_name,
            hanchan_date_override=hanchan_date_override,
            source_url=input_url,
        )
        capture_state.diagnostics.append(
            {
                "level": "info",
                "code": "xml_db_imported",
                "input_url": input_url,
                "xml_url": fetched_xml.resolved.xml_url,
                "log_id": log_id,
                **import_result,
            }
        )
    except Exception as exc:
        capture_state.diagnostics.append(
            {
                "level": "warning",
                "code": "xml_db_import_failed",
                "input_url": input_url,
                "xml_url": fetched_xml.resolved.xml_url,
                "message": str(exc),
            }
        )
        print(f"XML DB import skipped: {exc}", file=sys.stderr)
    return capture_state


def start_capture_thread(
    state: CaptureState,
    test_input_path: str | Path | None = None,
    tls_keylog_path: str | Path | None = None,
    tshark_interface: str | None = None,
    test_interval_ms: int = DEFAULT_TEST_PACKET_INTERVAL_MS,
    debug_tags: bool = False,
) -> threading.Thread:
    """Start live capture or pcap replay in a background thread."""

    mark_runtime_thread_progress(
        state,
        "capture",
        "thread_spawn_pending",
        detail="before capture worker start",
        blocked_hint="capture worker thread has not started yet",
        stale_after_s=6.0,
        repeat_after_s=12.0,
    )

    def _capture_worker() -> None:
        try:
            mark_runtime_thread_progress(
                state,
                "capture",
                "capture_worker_started",
                detail="capture worker thread entered",
                blocked_hint="capture worker thread startup is stalled",
                stale_after_s=4.0,
                repeat_after_s=10.0,
            )
            # Emit a startup marker before entering replay/live code so "thread never started" is visible.
            LIVE_CAPTURE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with LIVE_CAPTURE_LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write("[thread] capture_worker_started\n")
            # Replay and live capture share the same background thread so UI startup stays responsive.
            if test_input_path is not None:
                run_test_capture(
                    input_path=test_input_path,
                    state=state,
                    tls_keylog_path=tls_keylog_path,
                    interval_ms=test_interval_ms,
                    debug_tags=debug_tags,
                )
            else:
                run_and_capture(
                    state,
                    tls_keylog_path=tls_keylog_path,
                    tshark_interface=tshark_interface,
                    debug_tags=debug_tags,
                )
        except Exception as exc:
            # Surface thread-level failures to stdout/stderr and keep the traceback in diagnostics.
            message = f"Packet capture stopped: {exc}"
            print(message)
            print(message, file=sys.stderr)
            mark_runtime_thread_progress(
                state,
                "capture",
                "capture_thread_failed",
                detail=str(exc),
                blocked_hint="capture worker thread raised an exception",
                stale_after_s=60.0,
                repeat_after_s=60.0,
            )
            with state.state_lock:
                state.diagnostics.append(
                    {
                        "level": "error",
                        "code": "capture_thread_failed",
                        "message": str(exc),
                        "traceback": traceback.format_exc(limit=8),
                    }
                )
                state.prune_live_history()

    capture_thread = threading.Thread(
        target=_capture_worker,
        name="pcap-test-replay" if test_input_path is not None else "tshark-capture",
        daemon=True,
    )
    table_view.show_thread_activity_notice(
        "pcap replay" if test_input_path is not None else "tshark capture"
    )
    capture_thread.start()
    return capture_thread


def build_live_meld_map(capture_state: CaptureState) -> dict[Player, list[Meld]]:
    """Return the current round meld list keyed by Player."""

    round_state = capture_state.current_round
    if round_state is None:
        return {player: [] for player in Player}
    return {
        player: list(round_state.melds.get(int(player), []))
        for player in Player
    }


def flatten_visible_meld_tiles(meld_map: dict[Player, list[Meld]]) -> list[int]:
    """Flatten full meld tiles for visible-tile counting."""

    return [
        tile_id
        for melds in meld_map.values()
        for meld in melds
        for tile_id in meld.tiles_37
    ]


def build_live_visible_tile_summary(capture_state: CaptureState) -> VisibleTileSummary:
    """Build the current actual visible-tile summary from live state.

    Live visible counts stay independent from awaseuchi/public-event checks and from inferred
    visible adjustments. They are derived only from the current hand, rivers, exposed melds, and
    dora indicators.
    """

    if capture_state.current_round is None:
        return VisibleTileSummary(three_visible_tiles=[], four_visible_tiles=[])

    meld_map = build_live_meld_map(capture_state)
    return collect_visible_tile_summary(
        discard_map=capture_state.tracker.discards,
        hand_tiles=tiles136_to_tiles37(capture_state.live_hand_tiles_136),
        meld_tiles=flatten_visible_meld_tiles(meld_map),
        dora_indicator_tiles=tiles136_to_tiles37(capture_state.live_dora_indicator_tiles_136),
    )


def _collect_uncalled_discard_tiles37(capture_state: CaptureState) -> list[int]:
    """Return visible discards only, excluding tiles already represented inside melds."""

    return [
        int(discard.tile_id)
        for discards in capture_state.tracker.discards.values()
        for discard in discards
        if not discard.called
    ]


def _pystyle_round_wind_tile(kyoku_index: int | None) -> int:
    """Convert the current kyoku index into the simulator's wind tile id."""

    if kyoku_index is None or kyoku_index < 0:
        return 27
    return 27 + min(3, kyoku_index // 4)


def _pystyle_self_seat_wind_tile(oya_rel: int | None) -> int:
    """Convert the current dealer seat into the simulator's self seat-wind tile id."""

    if oya_rel is None:
        return 27
    return 27 + ((0 - int(oya_rel)) % 4)


def _pystyle_round_token(round_state: object | None) -> str:
    """Return a stable round token so old AI snapshots do not bleed into the next hand."""

    if round_state is None:
        return ""
    round_id = getattr(round_state, "round_id", None)
    if round_id:
        return str(round_id)
    return str(
        (
            getattr(round_state, "kyoku_index", None),
            getattr(round_state, "honba", None),
            getattr(round_state, "kyotaku", None),
            getattr(round_state, "oya", None),
        )
    )


def _pystyle_request_meld_type_code(meld: Meld) -> int:
    """Map the local canonical meld labels onto the integer-only pystyle request schema."""

    # The remote validator currently accepts integer enum values, but the backend behavior is not
    # fully documented. Keep a stable local mapping instead of sending strings.
    return {
        "pon": 0,
        "chi": 1,
        "daiminkan": 2,
        "ankan": 3,
        "kakan": 4,
    }.get(meld.meld_type, 0)


def _build_pystyle_self_meld_requests(
    melds: Sequence[Meld],
) -> tuple[PystyleRequestMeld, ...]:
    """Convert the current self melds into pystyle request entries."""

    request_melds: list[PystyleRequestMeld] = []
    for meld in melds:
        simulator_tiles: list[int] = []
        for tile_37 in meld.tiles_37:
            simulator_tile = tile37_to_simulator_tile(int(tile_37))
            if simulator_tile is None:
                simulator_tiles = []
                break
            simulator_tiles.append(simulator_tile)
        if not simulator_tiles:
            continue
        discarded_tile = None
        if meld.target_tile_37 is not None:
            discarded_tile = tile37_to_simulator_tile(int(meld.target_tile_37))
        request_melds.append(
            PystyleRequestMeld(
                type=_pystyle_request_meld_type_code(meld),
                tiles=tuple(simulator_tiles),
                discarded_tile=discarded_tile,
                from_seat=(
                    int(meld.from_seat)
                    if meld.is_open and meld.from_seat is not None
                    else None
                ),
            )
        )
    return tuple(request_melds)


def _build_pystyle_remaining_wall(
    discard_tiles_37: Sequence[int],
    hand_tiles_37: Sequence[int],
    meld_tiles_37: Sequence[int],
    dora_indicator_tiles_37: Sequence[int],
) -> tuple[int, ...] | None:
    """Build one exact wall vector, or fall back to simulator-side defaults when inconsistent."""

    try:
        return build_remaining_wall_from_visible_tiles37(
            [
                *discard_tiles_37,
                *hand_tiles_37,
                *meld_tiles_37,
                *dora_indicator_tiles_37,
            ]
        )
    except ValueError:
        return None


def build_live_hand_draw_tile(capture_state: CaptureState) -> int | None:
    """Return the current self draw tile in UI tile ids when one exists."""

    tile_136 = capture_state.live_last_draw_tile_136
    if tile_136 is None:
        return None
    return tile136_to_tile37(tile_136)


def build_live_visible_hand_state(capture_state: CaptureState) -> VisibleHandState:
    """Return the currently displayed self-hand order for Tenhou UI Bridge commands."""

    with capture_state.state_lock:
        hand_tiles_136 = list(capture_state.live_hand_tiles_136)
        draw_tile_136 = capture_state.live_last_draw_tile_136
    # The bridge must click the hand in the exact order the local UI is currently displaying it.
    # Build that order here from capture state once, instead of making the extension rediscover it.
    hand_tiles_37 = [
        int(tile_37)
        for tile_136 in hand_tiles_136
        if (tile_37 := tile136_to_tile37(tile_136)) is not None
    ]
    draw_tile_37 = tile136_to_tile37(draw_tile_136)
    return build_visible_hand_state(
        hand_tiles_37,
        draw_tile_37,
        hand_tiles_136=hand_tiles_136,
        hand_draw_tile_136=draw_tile_136,
    )


def _build_tenhou_ui_bridge_auto_discard_action(
    tenhou_ui_bridge_client: TenhouUiBridgeClient | None,
) -> Callable[[int], dict[str, object]] | None:
    """Return the app-side callback used by the Auto mode button."""

    if tenhou_ui_bridge_client is None:
        return None

    def _auto_discard(tile_37: int) -> dict[str, object]:
        # Keep tile-to-index resolution in the local app so the extension remains UI-only.
        return tenhou_ui_bridge_client.send_discard_by_tile37(int(tile_37))

    return _auto_discard


def _build_tenhou_ui_bridge_manual_discard_action(
    tenhou_ui_bridge_client: TenhouUiBridgeClient | None,
) -> Callable[[int], dict[str, object]] | None:
    """Return the app-side callback used when the user clicks one self-hand tile on the canvas."""

    if tenhou_ui_bridge_client is None:
        return None

    def _manual_discard(hand_index: int) -> dict[str, object]:
        # Manual clicks should still reach the page even when packet capture is one draw behind and
        # the local visible-hand snapshot is temporarily non-actionable.
        return tenhou_ui_bridge_client.send_discard_by_index(
            int(hand_index),
            require_actionable_visible_hand=False,
        )

    return _manual_discard


def _build_tenhou_ui_bridge_control_click_action(
    tenhou_ui_bridge_client: TenhouUiBridgeClient | None,
) -> Callable[[int], dict[str, object]] | None:
    """Return the app-side callback used by the local visible-control buttons."""

    if tenhou_ui_bridge_client is None:
        return None

    def _click_control(control_id: int) -> dict[str, object]:
        return tenhou_ui_bridge_client.send_click_control(int(control_id))

    return _click_control


def _build_tenhou_ui_bridge_snapshot_action(
    tenhou_ui_bridge_client: TenhouUiBridgeClient | None,
) -> Callable[[], dict[str, object]] | None:
    """Return the app-side callback used to refresh the visible Tenhou UI snapshot."""

    if tenhou_ui_bridge_client is None:
        return None

    def _request_snapshot() -> dict[str, object]:
        return tenhou_ui_bridge_client.request_ui_snapshot()

    return _request_snapshot


def _coerce_bridge_snapshot_int(
    value: object,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    """Convert one browser-snapshot field into a bounded integer when possible."""

    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None and normalized < minimum:
        return None
    if maximum is not None and normalized > maximum:
        return None
    return normalized


def _normalize_bridge_snapshot_tile_ids(value: object) -> list[int]:
    """Return valid 0..135 tile ids from one browser snapshot field."""

    if not isinstance(value, (list, tuple)):
        return []
    normalized: list[int] = []
    for item in value:
        tile_136 = _coerce_bridge_snapshot_int(item, minimum=0, maximum=135)
        if tile_136 is None:
            continue
        normalized.append(tile_136)
    return normalized


def _normalize_bridge_snapshot_player_names(value: object) -> dict[int, str]:
    """Return seat-indexed player names from one browser snapshot field."""

    names = dict(DEFAULT_PLAYER_NAMES_BY_SEAT)
    if not isinstance(value, (list, tuple)):
        return names
    for seat, raw_name in enumerate(value[:SEAT_COUNT]):
        name_text = str(raw_name or "").strip()
        if name_text:
            names[seat] = name_text
    return names


def _normalize_bridge_snapshot_scores(value: object) -> list[int]:
    """Return one 4-seat score list from the browser snapshot, defaulting conservatively."""

    if not isinstance(value, (list, tuple)):
        return [25000, 25000, 25000, 25000]
    scores: list[int] = []
    for raw_score in value[:SEAT_COUNT]:
        score = _coerce_bridge_snapshot_int(raw_score)
        if score is None:
            continue
        scores.append(score)
    if len(scores) < SEAT_COUNT:
        return [25000, 25000, 25000, 25000]
    if max(abs(score) for score in scores) <= 1000:
        return [score * 100 for score in scores]
    return scores


def _normalize_bridge_snapshot_river_entries(
    value: object,
) -> dict[int, list[dict[str, object]]]:
    """Return seat-indexed visible river entries from one browser snapshot field."""

    rivers = {seat: [] for seat in range(SEAT_COUNT)}
    if not isinstance(value, (list, tuple)):
        return rivers
    for seat, raw_entries in enumerate(value[:SEAT_COUNT]):
        if not isinstance(raw_entries, (list, tuple)):
            continue
        seat_entries: list[dict[str, object]] = []
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict):
                continue
            tile34_index = _coerce_bridge_snapshot_int(
                raw_entry.get("tile34Index"),
                minimum=0,
                maximum=33,
            )
            if tile34_index is None:
                continue
            seat_entries.append(
                {
                    "tile34Index": tile34_index,
                    "tsumogiri": bool(raw_entry.get("tsumogiri", False)),
                    "riichiMarkerBefore": bool(raw_entry.get("riichiMarkerBefore", False)),
                }
            )
        rivers[seat] = seat_entries
    return rivers


def _build_bridge_snapshot_tile_pools(
    reserved_tile_ids_136: Sequence[int],
) -> dict[int, list[int]]:
    """Build per-tile allocation pools for unknown browser-side discard identities."""

    reserved_ids = {
        tile_136
        for tile_136 in reserved_tile_ids_136
        if isinstance(tile_136, int) and 0 <= tile_136 <= 135
    }
    pools: dict[int, list[int]] = {}
    for tile34_index in range(34):
        tile_ids = [tile34_index * 4 + offset for offset in range(4)]
        normal_ids = [
            tile_136
            for tile_136 in tile_ids
            if tile_136 not in reserved_ids and tile_136 not in RED_TILE_IDS_136
        ]
        red_ids = [
            tile_136
            for tile_136 in tile_ids
            if tile_136 not in reserved_ids and tile_136 in RED_TILE_IDS_136
        ]
        pools[tile34_index] = [*normal_ids, *red_ids]
    return pools


def _allocate_bridge_snapshot_river_tiles(
    *,
    hand_tiles_136: Sequence[int],
    dora_indicators_136: Sequence[int],
    river_entries_by_seat: dict[int, list[dict[str, object]]],
) -> dict[int, list[int]]:
    """Assign stable 136-ids to browser-reported visible river tiles."""

    tile_pools = _build_bridge_snapshot_tile_pools(
        [*hand_tiles_136, *dora_indicators_136]
    )
    allocated_by_seat = {seat: [] for seat in range(SEAT_COUNT)}
    for seat in range(SEAT_COUNT):
        for entry in river_entries_by_seat.get(seat, ()):
            tile34_index = int(entry["tile34Index"])
            available_tile_ids = tile_pools.get(tile34_index, [])
            if not available_tile_ids:
                raise RuntimeError(f"BROWSER_SNAPSHOT_TILE_OVERFLOW: tile34={tile34_index}")
            allocated_by_seat[seat].append(available_tile_ids.pop(0))
    return allocated_by_seat


def _build_bridge_snapshot_kawa_raw_tokens(
    allocated_tiles_136: Sequence[int],
    river_entries: Sequence[dict[str, object]],
) -> list[int]:
    """Encode browser river metadata into REINIT-like raw kawa tokens for diagnostics."""

    raw_tokens: list[int] = []
    for tile_136, entry in zip(allocated_tiles_136, river_entries):
        if bool(entry.get("riichiMarkerBefore", False)):
            raw_tokens.append(255)
        if bool(entry.get("tsumogiri", False)):
            raw_tokens.append(254)
        raw_tokens.append(int(tile_136))
    return raw_tokens


def _import_tenhou_ui_bridge_table_snapshot(
    capture_state: CaptureState,
    snapshot_result: dict[str, object],
) -> dict[str, object]:
    """Bootstrap the local live state from the current browser-side table snapshot."""

    hand_tiles_136 = _normalize_bridge_snapshot_tile_ids(snapshot_result.get("handTiles136"))
    dora_indicators_136 = _normalize_bridge_snapshot_tile_ids(snapshot_result.get("doraIndicators136"))
    river_entries_by_seat = _normalize_bridge_snapshot_river_entries(
        snapshot_result.get("riverEntriesBySeat")
    )
    if not hand_tiles_136 and not dora_indicators_136 and not any(river_entries_by_seat.values()):
        raise RuntimeError("BROWSER_TABLE_SNAPSHOT_EMPTY")

    player_names_by_seat = _normalize_bridge_snapshot_player_names(snapshot_result.get("playerNames"))
    scores = _normalize_bridge_snapshot_scores(snapshot_result.get("scores"))
    kyoku_index = _coerce_bridge_snapshot_int(snapshot_result.get("kyokuIndex"), minimum=0)
    honba = _coerce_bridge_snapshot_int(snapshot_result.get("honba"), minimum=0)
    kyotaku = _coerce_bridge_snapshot_int(snapshot_result.get("kyotaku"), minimum=0)
    oya = _coerce_bridge_snapshot_int(
        snapshot_result.get("oya"),
        minimum=0,
        maximum=SEAT_COUNT - 1,
    )
    allocated_river_tiles_by_seat = _allocate_bridge_snapshot_river_tiles(
        hand_tiles_136=hand_tiles_136,
        dora_indicators_136=dora_indicators_136,
        river_entries_by_seat=river_entries_by_seat,
    )

    with capture_state.state_lock:
        preserved_game_id = capture_state.game_id
        preserved_go_type = capture_state.go_type
        preserved_room_class_code = capture_state.room_class_code
        preserved_room_class_label = capture_state.room_class_label

        capture_state.reset_live_session(preserve_player_metadata=True)
        capture_state.game_id = preserved_game_id
        capture_state.go_type = preserved_go_type
        capture_state.room_class_code = preserved_room_class_code
        capture_state.room_class_label = preserved_room_class_label

        for seat in range(SEAT_COUNT):
            name_text = str(player_names_by_seat.get(seat, "") or "").strip()
            if not name_text:
                continue
            capture_state.players_rel[seat].seat = seat
            capture_state.players_rel[seat].name = name_text
            capture_state.players_abs[seat].seat = seat
            capture_state.players_abs[seat].name = name_text
        capture_state.refresh_player_views()

        round_state = capture_state.begin_round(started_from_init_like=True)
        capture_state.live_snapshot_bootstrap_sequence += 1
        round_state.snapshot_bootstrap_sequence = capture_state.live_snapshot_bootstrap_sequence
        round_state.snapshot_is_partial = True
        round_state.kyoku_index = kyoku_index
        round_state.honba = honba
        round_state.kyotaku = kyotaku
        round_state.oya = oya
        round_state.oya_rel = oya
        round_state.scores = list(scores)
        round_state.dora_indicators_136 = list(dora_indicators_136)
        round_state.current_hands_136[LOCAL_RELATIVE_SEAT] = list(hand_tiles_136)
        if len(hand_tiles_136) % 3 == 2:
            round_state.last_draw_tiles_136[LOCAL_RELATIVE_SEAT] = hand_tiles_136[-1]
        round_state.round_key = build_round_key(
            capture_state.game_id,
            round_state.kyoku_index,
            round_state.honba,
            round_state.kyotaku,
            round_state.oya,
        )
        round_state.round_id = build_round_id(
            capture_state.game_id,
            round_state.kyoku_index,
            round_state.honba,
            round_state.kyotaku,
            round_state.oya,
        )
        round_state.raw_attrs = {"source": "bridge_table_snapshot"}
        round_state.raw_reinit_attrs = {"source": "bridge_table_snapshot"}

        for seat in range(SEAT_COUNT):
            allocated_tiles_136 = allocated_river_tiles_by_seat.get(seat, [])
            river_entries = river_entries_by_seat.get(seat, [])
            round_state.discards[seat] = [
                CaptureDiscard(
                    tile_136=int(tile_136),
                    tsumogiri=bool(entry.get("tsumogiri", False)),
                    is_tsumogiri_estimated=False,
                    raw_tag=f"BROWSER_TABLE_SNAPSHOT:{seat}",
                    riichi_marker_before=bool(entry.get("riichiMarkerBefore", False)),
                )
                for tile_136, entry in zip(allocated_tiles_136, river_entries)
            ]
            round_state.reinit_kawa_raw[seat] = _build_bridge_snapshot_kawa_raw_tokens(
                allocated_tiles_136,
                river_entries,
            )

        _reindex_round_discards(round_state)
        _restore_reach_state_from_snapshot_discards(round_state)
        _rebuild_tracker_from_round(capture_state)
        _sync_live_state(capture_state)
        capture_state.sync_current_round_context()

        mapped_discard_count_by_seat = [
            len(round_state.discards.get(seat, ()))
            for seat in range(SEAT_COUNT)
        ]
        mapped_riichi_seat_count = sum(
            1
            for seat in range(SEAT_COUNT)
            if str(round_state.reach_state.get(seat, "none")) == "accepted"
        )

    return {
        "mappedHandTileCount": len(hand_tiles_136),
        "mappedDiscardCountTotal": sum(mapped_discard_count_by_seat),
        "mappedDiscardCountBySeat": mapped_discard_count_by_seat,
        "mappedDoraIndicatorCount": len(dora_indicators_136),
        "mappedRiichiSeatCount": mapped_riichi_seat_count,
        "mappedSnapshotBootstrapSequence": int(
            getattr(capture_state, "live_snapshot_bootstrap_sequence", 0)
        ),
    }


def _build_tenhou_ui_bridge_table_snapshot_action(
    tenhou_ui_bridge_client: TenhouUiBridgeClient | None,
    capture_state: CaptureState,
) -> Callable[[], dict[str, object]] | None:
    """Return the app-side callback used to import the current browser table state."""

    if tenhou_ui_bridge_client is None:
        return None

    def _request_table_snapshot() -> dict[str, object]:
        payload = tenhou_ui_bridge_client.request_table_snapshot()
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("BRIDGE_TABLE_SNAPSHOT_RESULT_MISSING")
        if not bool(result.get("ok", False)):
            return payload
        imported_summary = _import_tenhou_ui_bridge_table_snapshot(capture_state, result)
        merged_payload = dict(payload)
        merged_result = dict(result)
        merged_result.update(imported_summary)
        merged_payload["result"] = merged_result
        return merged_payload

    return _request_table_snapshot


def _build_tenhou_ui_bridge_status_provider(
    tenhou_ui_bridge_client: TenhouUiBridgeClient | None,
) -> Callable[[], object] | None:
    """Return the diagnostics status provider consumed by the local bridge widget."""

    if tenhou_ui_bridge_client is None:
        return None

    return tenhou_ui_bridge_client.snapshot_status


def build_live_hand_danger_metrics(capture_state: CaptureState) -> list[dict[int, object]]:
    """Return per-tile suji danger metrics for the current self hand."""

    # Visible counts must match the player-panel SUMMARY side. Build once here and feed the
    # self-hand danger bars from the same 34-kind snapshot semantics used elsewhere.
    visible_summary = build_live_visible_tile_summary(capture_state)
    return build_hand_tile_suji_danger_metrics(
        capture_state,
        capture_state.live_hand_tiles_136,
        visible_counts_34=visible_summary.visible_counts_34_index,
        self_hand_counts_34=visible_summary.self_hand_counts_34_index,
    )


def build_live_opponent_suji_panel_summaries(capture_state: CaptureState) -> dict[int, object]:
    """Return per-opponent denominator/top-line summaries for player panels."""

    round_state = capture_state.current_round
    if round_state is None:
        return {}
    # Keep panel-side ranking labels on the same visible-count basis as the self-hand bars so
    # `Remain`, line ranking, and tile ranking do not drift from the bar percentages.
    visible_summary = build_live_visible_tile_summary(capture_state)
    summaries = build_all_opponent_suji_panel_summaries(
        round_state,
        visible_counts_34=visible_summary.visible_counts_34_index,
        self_hand_counts_34=visible_summary.self_hand_counts_34_index,
    )
    return {
        seat: {
            **vars(summary),
            "is_riichi": seat in round_state.reach_accepted,
        }
        for seat, summary in summaries.items()
    }


def _build_live_opponent_suji_panel_summaries_from_profiles(
    round_state: object | None,
    *,
    visible_counts_34: Sequence[int] | None,
    self_hand_counts_34: Sequence[int] | None,
    profiles: dict[int, object],
) -> dict[int, object]:
    """Build player-panel summaries from a shared precomputed suji profile map."""

    if round_state is None:
        return {}
    summaries = build_all_opponent_suji_panel_summaries(
        round_state,
        visible_counts_34=visible_counts_34,
        self_hand_counts_34=self_hand_counts_34,
        profiles=profiles,
    )
    return {
        seat: {
            **vars(summary),
            "is_riichi": seat in getattr(round_state, "reach_accepted", set()),
        }
        for seat, summary in summaries.items()
    }


def build_live_player_push_alert_percentages(capture_state: CaptureState) -> dict[int, object]:
    """Return per-opponent latest-discard push alert percentages for player panels."""

    round_state = capture_state.current_round
    if round_state is None:
        return {}
    visible_summary = build_live_visible_tile_summary(capture_state)
    return build_latest_discard_push_alert_percentages(
        round_state,
        visible_counts_34=visible_summary.visible_counts_34_index,
    )


def build_player_score_diffs_by_seat(round_state: object | None) -> dict[int, int]:
    """Return opponent score gaps relative to self seat `0`."""

    diffs_by_seat = {
        int(Player.KAMICHA): 0,
        int(Player.TOIMEN): 0,
        int(Player.SHIMOCHA): 0,
    }
    if round_state is None:
        return diffs_by_seat
    raw_scores = getattr(round_state, "scores", None)
    if not isinstance(raw_scores, (list, tuple)) or len(raw_scores) < 4:
        return diffs_by_seat
    try:
        self_score = int(raw_scores[int(Player.JICHA)])
    except (TypeError, ValueError, IndexError):
        return diffs_by_seat
    for seat in diffs_by_seat:
        try:
            diffs_by_seat[seat] = int(raw_scores[seat]) - self_score
        except (TypeError, ValueError, IndexError):
            diffs_by_seat[seat] = 0
    return diffs_by_seat


def build_live_player_score_diffs_by_seat(capture_state: CaptureState) -> dict[int, int]:
    """Return current per-opponent score gaps relative to self seat `0`."""

    return build_player_score_diffs_by_seat(capture_state.current_round)


def build_live_discard_red_tint_indices_by_seat(
    capture_state: CaptureState,
) -> dict[int, tuple[int, ...]]:
    """Return per-opponent river discard indexes that should be shown with a red tint."""

    if not LIVE_DISCARD_RED_TINT_ENABLED:
        return {}

    round_state = capture_state.current_round
    if round_state is None:
        return {}

    signature = _build_live_discard_red_tint_signature(round_state)
    global _LIVE_DISCARD_RED_TINT_CACHE_SIGNATURE, _LIVE_DISCARD_RED_TINT_CACHE_VALUE
    if (
        signature is not None
        and _LIVE_DISCARD_RED_TINT_CACHE_SIGNATURE == signature
    ):
        return _LIVE_DISCARD_RED_TINT_CACHE_VALUE

    highlighted = build_discard_red_tint_indices_by_seat(round_state)
    if signature is not None:
        _LIVE_DISCARD_RED_TINT_CACHE_SIGNATURE = signature
        _LIVE_DISCARD_RED_TINT_CACHE_VALUE = highlighted
    return highlighted


def _get_live_suji_async_state(capture_state: CaptureState) -> LiveSujiAsyncState:
    """Return the mutable async-state bucket attached to one live capture state."""

    async_state = getattr(capture_state, "live_suji_async_state", None)
    if isinstance(async_state, LiveSujiAsyncState):
        return async_state
    async_state = LiveSujiAsyncState()
    capture_state.live_suji_async_state = async_state
    return async_state


def _get_live_red_tint_async_state(capture_state: CaptureState) -> LiveRedTintAsyncState:
    """Return the mutable async-state bucket attached to one live red-tint worker."""

    async_state = getattr(capture_state, "live_red_tint_async_state", None)
    if isinstance(async_state, LiveRedTintAsyncState):
        return async_state
    async_state = LiveRedTintAsyncState()
    capture_state.live_red_tint_async_state = async_state
    return async_state


def _build_loading_opponent_suji_panel_summaries(round_state: object | None) -> dict[int, object]:
    """Return lightweight placeholder summaries while the heavy remain bundle is computing."""

    riichi_seats = set(getattr(round_state, "reach_accepted", set())) if round_state is not None else set()
    return {
        seat: {
            "denominator_count": 0.0,
            "denominator_count_without_temporary_safe": None,
            "menzen_alert_score": 0,
            "hand_pattern_alert_level": 0,
            "suit_bias_alert": False,
            "ryanmen_chi_central_tedashi_alert": False,
            "tedashi_thinking_rise_alert": False,
            "tenpai_probability": (
                100.0 if seat in riichi_seats else DEFAULT_TENPAI_PROBABILITY_PERCENT
            ),
            "is_riichi": seat in riichi_seats,
            "is_loading": True,
            "top_line_labels": (),
            "top_line_summaries": (),
            "top_safe_hand_labels": (),
            "top_tile_rank_labels": (),
        }
        for seat in (int(Player.KAMICHA), int(Player.TOIMEN), int(Player.SHIMOCHA))
    }


def _build_live_suji_computation_bundle(
    snapshot_state: CaptureState,
    visible_summary: VisibleTileSummary,
    *,
    source_refresh_token: int,
    round_identity: object | None,
    input_signature: tuple[object, ...],
) -> LiveSujiComputationBundle:
    """Compute the heavy suji-derived bundle outside the Tk redraw path."""

    precomputed_profiles = (
        build_all_opponent_suji_danger_profiles(
            snapshot_state.current_round,
            visible_counts_34=visible_summary.visible_counts_34_index,
            self_hand_counts_34=visible_summary.self_hand_counts_34_index,
        )
        if snapshot_state.current_round is not None
        else {}
    )
    opponent_suji_panel_summaries = _build_live_opponent_suji_panel_summaries_from_profiles(
        snapshot_state.current_round,
        visible_counts_34=visible_summary.visible_counts_34_index,
        self_hand_counts_34=visible_summary.self_hand_counts_34_index,
        profiles=precomputed_profiles,
    )
    player_push_alert_percentages = (
        build_latest_discard_push_alert_percentages(
            snapshot_state.current_round,
            visible_counts_34=visible_summary.visible_counts_34_index,
        )
        if snapshot_state.current_round is not None
        else {}
    )
    return LiveSujiComputationBundle(
        source_refresh_token=source_refresh_token,
        round_identity=round_identity,
        input_signature=input_signature,
        hand_danger_percentages=build_hand_tile_suji_danger_metrics(
            snapshot_state,
            snapshot_state.live_hand_tiles_136,
            visible_counts_34=visible_summary.visible_counts_34_index,
            self_hand_counts_34=visible_summary.self_hand_counts_34_index,
            profiles=precomputed_profiles,
        ),
        opponent_suji_panel_summaries=opponent_suji_panel_summaries,
        player_push_alert_percentages=player_push_alert_percentages,
        player_alert_indicators_by_seat=table_view.build_player_panel_alert_indicators_by_seat(
            opponent_suji_panel_summaries,
            player_push_alert_percentages,
        ),
    )


def _live_suji_worker(capture_state: CaptureState) -> None:
    """Keep one live suji worker alive and drain the latest pending job on demand."""

    while True:
        wake_event: threading.Event | None = None
        with capture_state.state_lock:
            async_state = _get_live_suji_async_state(capture_state)
            job = async_state.pending_job
            if job is None:
                async_state.in_flight_source_refresh_token = None
                wake_event = async_state.wake_event
            else:
                async_state.pending_job = None
                async_state.in_flight_source_refresh_token = job.source_refresh_token
        if job is None:
            assert wake_event is not None
            wake_event.wait()
            wake_event.clear()
            continue
        table_view.begin_thread_activity_notice("live suji")
        try:
            bundle = _build_live_suji_computation_bundle(
                job.snapshot_state,
                job.visible_summary,
                source_refresh_token=job.source_refresh_token,
                round_identity=job.round_identity,
                input_signature=job.input_signature,
            )
        except Exception as exc:
            with capture_state.state_lock:
                async_state = _get_live_suji_async_state(capture_state)
                async_state.in_flight_source_refresh_token = None
                async_state.last_error = f"{type(exc).__name__}: {exc}"
                async_state.update_sequence += 1
            print(f"Live suji bundle skipped: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        finally:
            table_view.finish_thread_activity_notice("live suji")
        with capture_state.state_lock:
            async_state = _get_live_suji_async_state(capture_state)
            async_state.in_flight_source_refresh_token = None
            async_state.completed_bundle = bundle
            async_state.completed_source_refresh_token = job.source_refresh_token
            async_state.completed_round_identity = job.round_identity
            async_state.last_error = ""
            async_state.update_sequence += 1


def _live_red_tint_worker(capture_state: CaptureState) -> None:
    """Keep one live red-tint worker alive and drain the latest pending job on demand."""

    while True:
        wake_event: threading.Event | None = None
        with capture_state.state_lock:
            async_state = _get_live_red_tint_async_state(capture_state)
            job = async_state.pending_job
            if job is None:
                async_state.in_flight_source_refresh_token = None
                wake_event = async_state.wake_event
            else:
                async_state.pending_job = None
                async_state.in_flight_source_refresh_token = job.source_refresh_token
        if job is None:
            assert wake_event is not None
            wake_event.wait()
            wake_event.clear()
            continue
        table_view.begin_thread_activity_notice("live red tint")
        try:
            bundle = LiveRedTintComputationBundle(
                source_refresh_token=job.source_refresh_token,
                round_identity=job.round_identity,
                discard_red_tint_indices_by_seat=build_live_discard_red_tint_indices_by_seat(
                    job.snapshot_state
                ),
            )
        except Exception as exc:
            with capture_state.state_lock:
                async_state = _get_live_red_tint_async_state(capture_state)
                async_state.in_flight_source_refresh_token = None
                async_state.last_error = f"{type(exc).__name__}: {exc}"
                async_state.update_sequence += 1
            print(f"Live red tint bundle skipped: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        finally:
            table_view.finish_thread_activity_notice("live red tint")
        with capture_state.state_lock:
            async_state = _get_live_red_tint_async_state(capture_state)
            async_state.in_flight_source_refresh_token = None
            async_state.completed_bundle = bundle
            async_state.completed_source_refresh_token = job.source_refresh_token
            async_state.completed_round_identity = job.round_identity
            async_state.last_error = ""
            async_state.update_sequence += 1


def _request_live_suji_bundle(
    capture_state: CaptureState,
    snapshot_state: CaptureState,
    visible_summary: VisibleTileSummary,
    *,
    source_refresh_token: int,
    round_identity: object | None,
    input_signature: tuple[object, ...],
) -> tuple[LiveSujiComputationBundle | None, LiveSujiComputationBundle | None]:
    """Return the current/fallback suji bundle and enqueue work for the newest refresh token."""

    worker_thread: threading.Thread | None = None
    with capture_state.state_lock:
        async_state = _get_live_suji_async_state(capture_state)
        current_bundle = None
        fallback_bundle = None
        completed_bundle = async_state.completed_bundle
        if (
            isinstance(completed_bundle, LiveSujiComputationBundle)
            and async_state.completed_round_identity == round_identity
            and completed_bundle.input_signature == input_signature
        ):
            if async_state.completed_source_refresh_token == source_refresh_token:
                current_bundle = completed_bundle
            else:
                fallback_bundle = completed_bundle
        already_targeted = (
            async_state.in_flight_source_refresh_token == source_refresh_token
            or (
                async_state.pending_job is not None
                and async_state.pending_job.source_refresh_token == source_refresh_token
                and async_state.pending_job.round_identity == round_identity
                and async_state.pending_job.input_signature == input_signature
            )
        )
        if current_bundle is None and not already_targeted:
            async_state.pending_job = LiveSujiComputationJob(
                snapshot_state=snapshot_state,
                visible_summary=visible_summary,
                source_refresh_token=source_refresh_token,
                round_identity=round_identity,
                input_signature=input_signature,
            )
            if not async_state.worker_running:
                async_state.worker_running = True
                worker_thread = threading.Thread(
                    target=_live_suji_worker,
                    args=(capture_state,),
                    name="live-suji-bundle",
                    daemon=True,
                )
            else:
                async_state.wake_event.set()
    if worker_thread is not None:
        if threading.current_thread() is threading.main_thread():
            table_view.show_thread_activity_notice("live suji")
        worker_thread.start()
    return current_bundle, fallback_bundle


def _request_live_red_tint_bundle(
    capture_state: CaptureState,
    snapshot_state: CaptureState,
    *,
    source_refresh_token: int,
    round_identity: object | None,
) -> tuple[dict[int, tuple[int, ...]] | None, dict[int, tuple[int, ...]] | None]:
    """Return the current/fallback red-tint bundle and enqueue work for the newest refresh."""

    worker_thread: threading.Thread | None = None
    with capture_state.state_lock:
        async_state = _get_live_red_tint_async_state(capture_state)
        current_indices = None
        fallback_indices = None
        completed_bundle = async_state.completed_bundle
        if (
            isinstance(completed_bundle, LiveRedTintComputationBundle)
            and async_state.completed_round_identity == round_identity
        ):
            normalized_indices = dict(completed_bundle.discard_red_tint_indices_by_seat)
            if async_state.completed_source_refresh_token == source_refresh_token:
                current_indices = normalized_indices
            else:
                fallback_indices = normalized_indices
        already_targeted = (
            async_state.in_flight_source_refresh_token == source_refresh_token
            or (
                async_state.pending_job is not None
                and async_state.pending_job.source_refresh_token == source_refresh_token
                and async_state.pending_job.round_identity == round_identity
            )
        )
        if current_indices is None and not already_targeted:
            async_state.pending_job = LiveRedTintComputationJob(
                snapshot_state=snapshot_state,
                source_refresh_token=source_refresh_token,
                round_identity=round_identity,
            )
            if not async_state.worker_running:
                async_state.worker_running = True
                worker_thread = threading.Thread(
                    target=_live_red_tint_worker,
                    args=(capture_state,),
                    name="live-red-tint-bundle",
                    daemon=True,
                )
            else:
                async_state.wake_event.set()
    if worker_thread is not None:
        if threading.current_thread() is threading.main_thread():
            table_view.show_thread_activity_notice("live red tint")
        worker_thread.start()
    return current_indices, fallback_indices


def _cache_signature_int(value: object) -> int | None:
    """Normalize one optional integer for lightweight live-state cache signatures."""

    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _cache_signature_float(value: object) -> float | None:
    """Normalize one optional float for lightweight live-state cache signatures."""

    try:
        return round(float(value), 3) if value is not None else None
    except (TypeError, ValueError):
        return None


def _combined_live_async_update_sequence(capture_state: CaptureState) -> int:
    """Return one scalar that changes when any live background bundle completes."""

    suji_update_sequence = int(_get_live_suji_async_state(capture_state).update_sequence)
    red_tint_update_sequence = int(_get_live_red_tint_async_state(capture_state).update_sequence)
    return (suji_update_sequence << 32) | red_tint_update_sequence


def _build_live_discard_red_tint_signature(
    round_state: object | None,
) -> tuple[object, ...] | None:
    """Return the public discard/meld signature used to reuse red-tint candidate results."""

    if round_state is None:
        return None

    round_identity = getattr(round_state, "round_id", None) or (
        _cache_signature_int(getattr(round_state, "kyoku_index", None)),
        _cache_signature_int(getattr(round_state, "honba", None)),
        _cache_signature_int(getattr(round_state, "kyotaku", None)),
        _cache_signature_int(getattr(round_state, "oya", None)),
    )
    discard_signature = tuple(
        (
            seat,
            tuple(
                (
                    _cache_signature_int(getattr(discard, "event_index", None)),
                    _cache_signature_int(getattr(discard, "round_discard_index", None)),
                    _cache_signature_int(getattr(discard, "tile_34", None)),
                    bool(getattr(discard, "called", False)),
                    bool(getattr(discard, "tsumogiri", False)),
                    str(getattr(discard, "thinking_time_source", "") or ""),
                    _cache_signature_float(getattr(discard, "thinking_time_ms", None)),
                    _cache_signature_int(getattr(discard, "lagged", None)),
                    _cache_signature_float(getattr(discard, "lag_delay_ms", None)),
                )
                for discard in getattr(round_state, "discards", {}).get(seat, ())
            ),
        )
        for seat in range(4)
    )
    meld_signature = tuple(
        (
            seat,
            tuple(
                (
                    _cache_signature_int(getattr(meld, "event_index", None)),
                    str(getattr(meld, "meld_type", "") or ""),
                    tuple(
                        _cache_signature_int(tile_34)
                        for tile_34 in getattr(meld, "tiles_34", ()) or ()
                    ),
                    tuple(
                        _cache_signature_int(tile_id)
                        for tile_id in getattr(meld, "consumed_tile_ids", ()) or ()
                    ),
                    _cache_signature_int(getattr(meld, "called_tile_id", None)),
                    _cache_signature_int(getattr(meld, "from_seat", None)),
                )
                for meld in getattr(round_state, "melds", {}).get(seat, ())
            ),
        )
        for seat in range(4)
    )
    return (round_identity, discard_signature, meld_signature)


def _build_live_suji_input_signature(
    snapshot_state: CaptureState,
    visible_summary: VisibleTileSummary,
) -> tuple[object, ...]:
    """Return one signature for the async suji bundle inputs.

    Reusing the previous bundle is only safe while both the public round state and visible-count
    inputs still match. Lag metadata can arrive one event later; if we blindly reuse the fallback
    bundle, player-panel values such as `menzen` can contradict the newly drawn lag marker.
    """

    round_state = snapshot_state.current_round
    round_identity = getattr(round_state, "round_id", None) or (
        _cache_signature_int(getattr(round_state, "kyoku_index", None)) if round_state is not None else None,
        _cache_signature_int(getattr(round_state, "honba", None)) if round_state is not None else None,
        _cache_signature_int(getattr(round_state, "kyotaku", None)) if round_state is not None else None,
        _cache_signature_int(getattr(round_state, "oya", None)) if round_state is not None else None,
    )
    discard_signature = tuple(
        (
            seat,
            tuple(
                (
                    _cache_signature_int(getattr(discard, "event_index", None)),
                    _cache_signature_int(getattr(discard, "round_discard_index", None)),
                    _cache_signature_int(getattr(discard, "tile_34", None)),
                    _cache_signature_int(getattr(discard, "tile_37", None)),
                    bool(getattr(discard, "called", False)),
                    bool(getattr(discard, "tsumogiri", False)),
                    bool(getattr(discard, "is_tsumogiri_estimated", False)),
                    str(getattr(discard, "thinking_time_source", "") or ""),
                    _cache_signature_float(getattr(discard, "thinking_time_ms", None)),
                    _cache_signature_int(getattr(discard, "lagged", None)),
                    _cache_signature_float(getattr(discard, "lag_delay_ms", None)),
                )
                for discard in getattr(round_state, "discards", {}).get(seat, ())
            ),
        )
        for seat in range(4)
    )
    meld_signature = tuple(
        (
            seat,
            tuple(
                (
                    _cache_signature_int(getattr(meld, "event_index", None)),
                    str(getattr(meld, "meld_type", "") or ""),
                    bool(getattr(meld, "is_open", False)),
                    tuple(
                        _cache_signature_int(tile_34)
                        for tile_34 in getattr(meld, "tiles_34", ()) or ()
                    ),
                    _cache_signature_int(getattr(meld, "from_seat", None)),
                )
                for meld in getattr(round_state, "melds", {}).get(seat, ())
            ),
        )
        for seat in range(4)
    )
    visible_counts_signature = tuple(
        _cache_signature_int(count)
        for count in getattr(visible_summary, "visible_counts_34_index", ()) or ()
    )
    self_hand_counts_signature = tuple(
        _cache_signature_int(count)
        for count in getattr(visible_summary, "self_hand_counts_34_index", ()) or ()
    )
    riichi_signature = tuple(
        sorted(
            _cache_signature_int(seat)
            for seat in getattr(round_state, "reach_accepted", set()) or ()
        )
    )
    return (
        round_identity,
        discard_signature,
        meld_signature,
        visible_counts_signature,
        self_hand_counts_signature,
        riichi_signature,
    )


def build_live_player_names_by_seat(capture_state: CaptureState) -> dict[int, str]:
    """Return the current relative-seat player names for the UI panels."""

    names = dict(DEFAULT_PLAYER_NAMES_BY_SEAT)
    for seat in range(4):
        player = capture_state.players.get(seat)
        if player is None or not player.name:
            continue
        names[seat] = player.name
    return names


def build_live_round_identity(capture_state: CaptureState) -> object | None:
    """Return a stable token that changes when INIT/REINIT rebuilds the live table."""

    round_state = capture_state.current_round
    if round_state is None:
        return None
    logical_round_identity = round_state.round_id or (
        round_state.kyoku_index,
        round_state.honba,
        round_state.kyotaku,
        round_state.oya,
    )
    return (
        logical_round_identity,
        int(getattr(round_state, "snapshot_bootstrap_sequence", 0)),
    )


def _format_round_text(kyoku_index: int | None, honba: int | None) -> str:
    """Format the current round as `東1局 0本場` when enough state is present."""

    if kyoku_index is None:
        return "局情報なし"
    wind_label = ROUND_WIND_LABELS[kyoku_index // 4] if 0 <= kyoku_index // 4 < len(ROUND_WIND_LABELS) else "?"
    hand_number = kyoku_index % 4 + 1
    return f"{wind_label}{hand_number}局 {int(honba or 0)}本場"


def _build_seat_wind_labels_by_seat(oya_rel: int | None) -> dict[int, str]:
    """Return the current seat-wind label for each relative seat."""

    if oya_rel is None:
        return {}
    try:
        normalized_oya_rel = int(oya_rel)
    except (TypeError, ValueError):
        return {}
    seat_winds: dict[int, str] = {}
    for seat in (int(Player.JICHA), int(Player.SHIMOCHA), int(Player.TOIMEN), int(Player.KAMICHA)):
        wind_index = (int(seat) - normalized_oya_rel) % 4
        if 0 <= wind_index < len(ROUND_WIND_LABELS):
            seat_winds[int(seat)] = str(ROUND_WIND_LABELS[wind_index])
    return seat_winds


def _format_round_bootstrap_text(round_state: RoundState) -> str:
    """Return a compact INIT/REINIT/MAP rebuild counter for the center panel."""

    try:
        sequence = int(getattr(round_state, "snapshot_bootstrap_sequence", 0) or 0)
    except (TypeError, ValueError):
        sequence = 0
    if sequence <= 0:
        return ""

    raw_reinit_attrs = dict(getattr(round_state, "raw_reinit_attrs", {}) or {})
    raw_init_attrs = dict(getattr(round_state, "raw_init_attrs", {}) or {})
    raw_attrs = dict(getattr(round_state, "raw_attrs", {}) or {})
    source_text = str(
        raw_reinit_attrs.get("source")
        or raw_init_attrs.get("source")
        or raw_attrs.get("source")
        or ""
    ).strip()
    if source_text == "bridge_table_snapshot":
        label = "MAP"
    elif raw_reinit_attrs:
        label = "REINIT"
    elif raw_init_attrs:
        label = "INIT"
    else:
        label = "BOOT"
    return f"{label} #{sequence}"


def build_live_round_info_panel(capture_state: CaptureState) -> table_view.RoundInfoPanelData:
    """Return the compact center-panel payload derived from the active round state."""

    round_state = capture_state.current_round
    if round_state is None:
        return table_view.RoundInfoPanelData()
    return table_view.RoundInfoPanelData(
        round_text=_format_round_text(round_state.kyoku_index, round_state.honba),
        kyotaku_text=str(int(round_state.kyotaku or 0)),
        bootstrap_text=_format_round_bootstrap_text(round_state),
        seat_wind_labels_by_seat=_build_seat_wind_labels_by_seat(round_state.oya_rel),
    )


def _build_awaseuchi_round_events(round_state: object | None) -> list[object]:
    """Return only dora-reveal events needed by the renderer's awaseuchi marker logic."""

    if round_state is None:
        return []
    return [
        event
        for event in getattr(round_state, "events", ())
        if str(getattr(event, "event_type", "")).lower() == "dora"
    ]


def _clone_tracker_discard_for_live_snapshot(discard: object) -> object:
    """Return one lightweight copy of a tracker discard for UI snapshot use."""

    cloned_discard = copy.copy(discard)
    self_hand_tiles = getattr(discard, "self_hand_tiles_before_discard_136", None)
    if isinstance(self_hand_tiles, list):
        cloned_discard.self_hand_tiles_before_discard_136 = list(self_hand_tiles)
    return cloned_discard


def _clone_tracker_discard_map_for_live_snapshot(
    discard_map: dict[Player, list[object]],
) -> dict[Player, list[object]]:
    """Clone tracker discards without paying for a full recursive deepcopy."""

    return {
        player: [
            _clone_tracker_discard_for_live_snapshot(discard)
            for discard in discards
        ]
        for player, discards in discard_map.items()
    }


def _clone_capture_discard_for_live_snapshot(discard: CaptureDiscard) -> CaptureDiscard:
    """Return one lightweight copy of a round discard for danger/render snapshot use."""

    cloned_discard = copy.copy(discard)
    cloned_discard.hand_tiles_before_discard_136 = list(
        getattr(discard, "hand_tiles_before_discard_136", ())
    )
    cloned_discard.self_hand_tiles_before_discard_136 = list(
        getattr(discard, "self_hand_tiles_before_discard_136", ())
    )
    return cloned_discard


def _clone_capture_meld_for_live_snapshot(meld: Meld) -> Meld:
    """Return one lightweight copy of a meld for live snapshot use."""

    cloned_meld = copy.copy(meld)
    cloned_meld.consumed_tile_ids = list(getattr(meld, "consumed_tile_ids", ()))
    cloned_meld.tiles_136 = list(getattr(meld, "tiles_136", ()))
    cloned_meld.tiles_34 = list(getattr(meld, "tiles_34", ()))
    cloned_meld.tiles_37 = list(getattr(meld, "tiles_37", ()))
    return cloned_meld


def _clone_capture_event_for_live_snapshot(event: CaptureEvent) -> CaptureEvent:
    """Return one lightweight copy of a retained round event."""

    cloned_event = copy.copy(event)
    cloned_event.attrs = dict(getattr(event, "attrs", {}))
    return cloned_event


def _clone_round_state_for_live_snapshot(round_state: RoundState | None) -> RoundState | None:
    """Clone only the current-round fields needed by redraw/danger workers."""

    if round_state is None:
        return None
    cloned_round = RoundState(
        kyoku_index=round_state.kyoku_index,
        honba=round_state.honba,
        kyotaku=round_state.kyotaku,
        dice_1_minus_1=round_state.dice_1_minus_1,
        dice_2_minus_1=round_state.dice_2_minus_1,
        oya=round_state.oya,
        oya_abs=round_state.oya_abs,
        oya_rel=round_state.oya_rel,
        seat_order=list(round_state.seat_order),
        round_key=tuple(round_state.round_key) if round_state.round_key is not None else None,
        round_id=round_state.round_id,
        scores=list(round_state.scores),
        dora_indicators_136=list(round_state.dora_indicators_136),
        initial_self_hand_136=list(round_state.initial_self_hand_136),
        current_hands_136={
            seat: list(round_state.current_hands_136.get(seat, ()))
            for seat in range(4)
        },
        snapshot_is_partial=bool(round_state.snapshot_is_partial),
        started_from_init_like=bool(round_state.started_from_init_like),
        snapshot_bootstrap_sequence=int(getattr(round_state, "snapshot_bootstrap_sequence", 0)),
        discards={
            seat: [
                _clone_capture_discard_for_live_snapshot(discard)
                for discard in round_state.discards.get(seat, ())
            ]
            for seat in range(4)
        },
        melds={
            seat: [
                _clone_capture_meld_for_live_snapshot(meld)
                for meld in round_state.melds.get(seat, ())
            ]
            for seat in range(4)
        },
        reach_state=dict(round_state.reach_state),
        raw_attrs=dict(getattr(round_state, "raw_attrs", {}) or {}),
        raw_init_attrs=dict(getattr(round_state, "raw_init_attrs", {}) or {}),
        raw_reinit_attrs=dict(getattr(round_state, "raw_reinit_attrs", {}) or {}),
        events=[
            _clone_capture_event_for_live_snapshot(event)
            for event in getattr(round_state, "events", ())
            if str(getattr(event, "event_type", "")).lower() == "dora"
        ],
    )
    return cloned_round


def _count_chi_pon_extra_discards(round_state: object) -> int:
    """チー/ポンで増えた「山を減らさない打牌」を数える。

    チーとポンは、山を引かずに 1 打だけ余分に増える。大明槓・暗槓・加槓は嶺上牌側で山減少を
    持つので、この add-back には含めず、別の `kan_penalties` で処理する。
    """

    count = 0
    for melds in getattr(round_state, "melds", {}).values():
        for meld in melds:
            if meld.meld_type in {"chi", "pon"}:
                count += 1
    return count


def _count_kan_wall_penalties(round_state: object) -> int:
    """Count kans that reduce the maximum drawable wall tiles by one."""

    count = 0
    for melds in getattr(round_state, "melds", {}).values():
        for meld in melds:
            if meld.meld_type in {"daiminkan", "ankan", "kakan"}:
                count += 1
    return count


def _count_pending_turn_holders(round_state: object) -> int:
    """Count seats currently holding a pre-discard concealed count.

    Concealed counts `14 / 11 / 8 / 5 / 2` all satisfy `count % 3 == 2`, so this catches
    "just drew" and "just called chi/pon and must discard" from the current snapshot.
    """

    count = 0
    for seat in range(4):
        concealed_count = len(getattr(round_state, "current_hands_136", {}).get(seat, []))
        if concealed_count > 0 and concealed_count % 3 == 2:
            count += 1
    return count


def _latest_self_discard_tile_37(round_state: object | None) -> int | None:
    """Return the newest self discard in UI tile ids when one exists."""

    if round_state is None:
        return None
    discards = getattr(round_state, "discards", {}).get(int(Player.JICHA), ())
    if not discards:
        return None
    latest_discard = discards[-1]
    return tile136_to_tile37(getattr(latest_discard, "tile_136", None))


def _live_pystyle_visible_total_tile_count(
    hand_tiles_37: Sequence[int],
    meld_requests: Sequence[PystyleRequestMeld],
) -> int:
    """Return the current visible hand size on the simulator's effective 14-tile basis."""

    return len(tuple(int(tile) for tile in hand_tiles_37)) + (3 * len(tuple(meld_requests)))


def build_live_pystyle_display_context(capture_state: CaptureState) -> PystyleDisplayContext:
    """Return the current AI TOP3 POST/display context derived from the live table state."""

    round_state = capture_state.current_round
    hand_tiles_37 = tiles136_to_tiles37(capture_state.live_hand_tiles_136)
    meld_map = build_live_meld_map(capture_state)
    meld_tiles_37 = flatten_visible_meld_tiles(meld_map)
    self_meld_requests = _build_pystyle_self_meld_requests(
        list(meld_map.get(Player.JICHA, ()))
    )
    dora_indicator_tiles_37 = tiles136_to_tiles37(capture_state.live_dora_indicator_tiles_136)
    remaining_wall = _build_pystyle_remaining_wall(
        _collect_uncalled_discard_tiles37(capture_state),
        hand_tiles_37,
        meld_tiles_37,
        dora_indicator_tiles_37,
    )
    visible_total_tile_count = _live_pystyle_visible_total_tile_count(
        hand_tiles_37,
        self_meld_requests,
    )
    allow_history_persist = visible_total_tile_count == 14
    request_fallback_tile_37 = (
        _latest_self_discard_tile_37(round_state)
        if capture_state.live_last_draw_tile_136 is None and visible_total_tile_count == 13
        else None
    )
    if round_state is None:
        wall_tiles_remaining = 70
        return PystyleDisplayContext(
            turn_index=max(0, int(math.ceil(18 - (wall_tiles_remaining / 4.0)))),
            turn_source="remaining_wall_formula",
            wall_tiles_remaining=wall_tiles_remaining,
            dora_indicator_tiles_37=tuple(dora_indicator_tiles_37),
            melds=self_meld_requests,
            remaining_wall=remaining_wall,
            round_token=_pystyle_round_token(round_state),
            request_fallback_tile_37=request_fallback_tile_37,
            allow_history_persist=allow_history_persist,
        )

    total_discards = sum(len(discards) for discards in round_state.discards.values())
    chi_pon_extra_discards = _count_chi_pon_extra_discards(round_state)
    pending_turn_holders = _count_pending_turn_holders(round_state)
    kan_penalties = _count_kan_wall_penalties(round_state)
    # 山は「打牌総数」からそのまま引かず、チー/ポンで増えただけの打牌は戻し入れる。
    # さらに、今まさにツモ後/鳴き後でまだ打っていない席は山を 1 枚使っているので引き、
    # カンは嶺上ぶんだけ別途 1 枚減らす。
    wall_tiles_remaining = max(
        0,
        70 - total_discards + chi_pon_extra_discards - pending_turn_holders - kan_penalties,
    )
    turn_index = max(0, int(math.ceil(18 - (wall_tiles_remaining / 4.0))))
    return PystyleDisplayContext(
        turn_index=turn_index,
        turn_source="remaining_wall_formula",
        wall_tiles_remaining=wall_tiles_remaining,
        round_wind=_pystyle_round_wind_tile(round_state.kyoku_index),
        seat_wind=_pystyle_self_seat_wind_tile(round_state.oya_rel),
        dora_indicator_tiles_37=tuple(dora_indicator_tiles_37),
        melds=self_meld_requests,
        remaining_wall=remaining_wall,
        round_token=_pystyle_round_token(round_state),
        request_fallback_tile_37=request_fallback_tile_37,
        allow_history_persist=allow_history_persist,
    )


def _snapshot_live_capture_state(
    capture_state: CaptureState,
    *,
    blocking: bool = True,
) -> tuple[CaptureState, dict[int, str], int] | None:
    """Copy the mutable live capture state once for one redraw pass."""

    state_lock = capture_state.state_lock
    if not state_lock.acquire(blocking=blocking):
        return None
    try:
        discard_map = _clone_tracker_discard_map_for_live_snapshot(capture_state.tracker.discards)
        round_state = _clone_round_state_for_live_snapshot(capture_state.current_round)
        hand_tiles_136 = list(capture_state.live_hand_tiles_136)
        last_draw_tile_136 = capture_state.live_last_draw_tile_136
        dora_indicator_tiles_136 = list(capture_state.live_dora_indicator_tiles_136)
        player_names_by_seat = {
            seat: (
                capture_state.players.get(seat).name
                if capture_state.players.get(seat) is not None
                else None
            )
            for seat in range(4)
        }
        refresh_token = int(capture_state.live_update_sequence)
    finally:
        state_lock.release()

    snapshot_state = CaptureState(
        tracker=SutehaiTracker(discards=discard_map),
        current_round=round_state,
        live_hand_tiles_136=hand_tiles_136,
        live_last_draw_tile_136=last_draw_tile_136,
        live_dora_indicator_tiles_136=dora_indicator_tiles_136,
    )
    resolved_player_names_by_seat = dict(DEFAULT_PLAYER_NAMES_BY_SEAT)
    for seat, name in player_names_by_seat.items():
        if name:
            resolved_player_names_by_seat[seat] = name
    return snapshot_state, resolved_player_names_by_seat, refresh_token


def _read_live_snapshot_cache_state_locked(
    capture_state: CaptureState,
) -> tuple[tuple[int, int], tuple[int, int], LiveTableSnapshot | None, object | None]:
    """Read the current UI/cache refresh tokens plus cached snapshot while holding `state_lock`."""

    live_refresh_token = int(capture_state.live_update_sequence)
    refresh_token = (
        live_refresh_token,
        _combined_live_async_update_sequence(capture_state)
        if LIVE_ASYNC_BUNDLE_REFRESH_ENABLED
        else 0,
    )
    cache_refresh_token = (
        live_refresh_token,
        _combined_live_async_update_sequence(capture_state),
    )
    cached_snapshot = getattr(capture_state, "cached_live_table_snapshot", None)
    cached_refresh_token = getattr(
        capture_state,
        "cached_live_table_snapshot_refresh_token",
        None,
    )
    return refresh_token, cache_refresh_token, cached_snapshot, cached_refresh_token


def build_live_table_snapshot(capture_state: CaptureState) -> LiveTableSnapshot:
    """Build one consistent live-table snapshot for the renderer."""

    progress_thread_name = (
        "ui" if threading.current_thread() is threading.main_thread() else "live_snapshot"
    )
    progress_subject = (
        "UI thread" if progress_thread_name == "ui" else "live snapshot worker"
    )
    mark_runtime_thread_progress(
        capture_state,
        progress_thread_name,
        "build_live_table_snapshot",
        detail="building live table snapshot",
        blocked_hint=f"{progress_subject} is building the live table snapshot",
        stale_after_s=2.0,
        repeat_after_s=5.0,
    )
    state_lock = capture_state.state_lock
    if not state_lock.acquire(blocking=False):
        cached_snapshot = getattr(capture_state, "cached_live_table_snapshot", None)
        if isinstance(cached_snapshot, LiveTableSnapshot):
            # Redraw should prefer a slightly stale frame over blocking behind live parser work.
            mark_runtime_thread_progress(
                capture_state,
                progress_thread_name,
                "snapshot_ready",
                detail=f"cached_refresh_token={cached_snapshot.refresh_token}",
                blocked_hint=f"{progress_subject} has not published a fresh live snapshot",
                stale_after_s=4.0,
                repeat_after_s=10.0,
            )
            return cached_snapshot
        with state_lock:
            refresh_token, cache_refresh_token, cached_snapshot, cached_refresh_token = _read_live_snapshot_cache_state_locked(
                capture_state
            )
    else:
        try:
            refresh_token, cache_refresh_token, cached_snapshot, cached_refresh_token = _read_live_snapshot_cache_state_locked(
                capture_state
            )
        finally:
            state_lock.release()
    if cached_refresh_token == cache_refresh_token and isinstance(cached_snapshot, LiveTableSnapshot):
        mark_runtime_thread_progress(
            capture_state,
            progress_thread_name,
            "snapshot_ready",
            detail=f"cached_refresh_token={cached_snapshot.refresh_token}",
            blocked_hint=f"{progress_subject} has not published a fresh live snapshot",
            stale_after_s=4.0,
            repeat_after_s=10.0,
        )
        return cached_snapshot

    snapshot_result = _snapshot_live_capture_state(capture_state, blocking=False)
    if snapshot_result is None:
        if isinstance(cached_snapshot, LiveTableSnapshot):
            # A capture parse may be applying the next discard/draw right now. Keep the UI responsive
            # and let the next redraw publish the fresh frame instead of blocking the Tk thread.
            mark_runtime_thread_progress(
                capture_state,
                progress_thread_name,
                "snapshot_ready",
                detail=f"reused_cached_refresh_token={cached_snapshot.refresh_token}",
                blocked_hint=f"{progress_subject} reused cached live snapshot while capture state was busy",
                stale_after_s=4.0,
                repeat_after_s=10.0,
            )
            return cached_snapshot
        snapshot_result = _snapshot_live_capture_state(capture_state, blocking=True)
    if snapshot_result is None:
        raise RuntimeError("failed to snapshot live capture state")
    snapshot_state, player_names_by_seat, live_refresh_token = snapshot_result
    melds_by_player = build_live_meld_map(snapshot_state)
    visible_summary = build_live_visible_tile_summary(snapshot_state)
    round_identity = build_live_round_identity(snapshot_state)
    suji_input_signature = _build_live_suji_input_signature(snapshot_state, visible_summary)
    current_suji_bundle, fallback_suji_bundle = _request_live_suji_bundle(
        capture_state,
        snapshot_state,
        visible_summary,
        source_refresh_token=live_refresh_token,
        round_identity=round_identity,
        input_signature=suji_input_signature,
    )
    effective_hand_danger_percentages = (
        current_suji_bundle.hand_danger_percentages
        if current_suji_bundle is not None
        else (
            fallback_suji_bundle.hand_danger_percentages
            if fallback_suji_bundle is not None
            else []
        )
    )
    effective_opponent_suji_panel_summaries = (
        current_suji_bundle.opponent_suji_panel_summaries
        if current_suji_bundle is not None
        else (
            fallback_suji_bundle.opponent_suji_panel_summaries
            if fallback_suji_bundle is not None
            else _build_loading_opponent_suji_panel_summaries(snapshot_state.current_round)
        )
    )
    effective_player_push_alert_percentages = (
        current_suji_bundle.player_push_alert_percentages
        if current_suji_bundle is not None
        else (
            fallback_suji_bundle.player_push_alert_percentages
            if fallback_suji_bundle is not None
            else {}
        )
    )
    effective_player_alert_indicators_by_seat = (
        current_suji_bundle.player_alert_indicators_by_seat
        if current_suji_bundle is not None
        else (
            fallback_suji_bundle.player_alert_indicators_by_seat
            if fallback_suji_bundle is not None
            else {}
        )
    )
    current_red_tint_indices, fallback_red_tint_indices = _request_live_red_tint_bundle(
        capture_state,
        snapshot_state,
        source_refresh_token=live_refresh_token,
        round_identity=round_identity,
    )
    effective_discard_red_tint_indices = (
        current_red_tint_indices
        if current_red_tint_indices is not None
        else (fallback_red_tint_indices if fallback_red_tint_indices is not None else {})
    )
    round_events = _build_awaseuchi_round_events(snapshot_state.current_round)
    table_situation_auto_scores_by_seat = (
        table_view._build_table_situation_auto_scores_by_seat(
            snapshot_state.tracker.discards,
            effective_discard_red_tint_indices,
        )
        if table_view.TABLE_SITUATION_ENABLED
        else {}
    )
    same_jun_marker_indices_by_seat = (
        table_view._same_jun_match_discard_indices_by_seat(
            snapshot_state.tracker.discards,
            melds_by_player,
            round_events,
        )
        if table_view.AWASEUCHI_MARKERS_ENABLED
        else {}
    )
    snapshot = LiveTableSnapshot(
        discard_map={
            player: list(snapshot_state.tracker.discards.get(player, []))
            for player in Player
        },
        discard_red_tint_indices_by_seat=effective_discard_red_tint_indices,
        hand_tiles=tiles136_to_tiles37(snapshot_state.live_hand_tiles_136),
        hand_draw_tile=build_live_hand_draw_tile(snapshot_state),
        hand_danger_percentages=effective_hand_danger_percentages,
        opponent_suji_panel_summaries=effective_opponent_suji_panel_summaries,
        player_push_alert_percentages=effective_player_push_alert_percentages,
        player_alert_indicators_by_seat=effective_player_alert_indicators_by_seat,
        player_score_diffs_by_seat=build_player_score_diffs_by_seat(snapshot_state.current_round),
        player_names_by_seat=player_names_by_seat,
        meld_tiles=flatten_visible_meld_tiles(melds_by_player),
        dora_indicator_tiles=tiles136_to_tiles37(snapshot_state.live_dora_indicator_tiles_136),
        round_events=round_events,
        round_info_panel=build_live_round_info_panel(snapshot_state),
        melds_by_player=melds_by_player,
        visible_summary=visible_summary,
        round_identity=round_identity,
        refresh_token=refresh_token,
        hand_recommendation_request_context=build_live_pystyle_display_context(snapshot_state),
        table_situation_auto_scores_by_seat=table_situation_auto_scores_by_seat,
        same_jun_marker_indices_by_seat=same_jun_marker_indices_by_seat,
    )
    with capture_state.state_lock:
        current_refresh_token = (
            int(capture_state.live_update_sequence),
            _combined_live_async_update_sequence(capture_state),
        )
        if current_refresh_token == cache_refresh_token:
            capture_state.cached_live_table_snapshot_refresh_token = cache_refresh_token
            capture_state.cached_live_table_snapshot = snapshot
    mark_runtime_thread_progress(
        capture_state,
        progress_thread_name,
        "snapshot_ready",
        detail=f"refresh_token={snapshot.refresh_token}",
        blocked_hint=f"{progress_subject} has not published a fresh live snapshot",
        stale_after_s=4.0,
        repeat_after_s=10.0,
    )
    return snapshot


def force_live_table_snapshot_reinit(capture_state: CaptureState) -> tuple[int, int]:
    """Drop the live snapshot cache and force one refresh from the current capture state."""

    mark_runtime_thread_progress(
        capture_state,
        "ui",
        "force_live_table_snapshot_reinit",
        detail="invalidating cached live snapshot",
        blocked_hint="UI thread is forcing one live snapshot rebuild",
        stale_after_s=2.0,
        repeat_after_s=5.0,
    )
    with capture_state.state_lock:
        capture_state.cached_live_table_snapshot = None
        capture_state.cached_live_table_snapshot_refresh_token = None
        capture_state.mark_live_update()
        async_state = _get_live_suji_async_state(capture_state)
        red_tint_async_state = _get_live_red_tint_async_state(capture_state)
        return (
            int(capture_state.live_update_sequence),
            (
                (int(async_state.update_sequence) << 32) | int(red_tint_async_state.update_sequence)
            )
            if LIVE_ASYNC_BUNDLE_REFRESH_ENABLED
            else 0,
        )


def build_live_refresh_token(capture_state: CaptureState) -> tuple[int, int]:
    """Return the current live update token under the capture-state lock."""

    mark_runtime_thread_progress(
        capture_state,
        "ui",
        "build_live_refresh_token",
        detail="reading live refresh token",
        blocked_hint="UI thread is reading the live refresh token",
        stale_after_s=2.0,
        repeat_after_s=5.0,
    )
    state_lock = capture_state.state_lock
    if not state_lock.acquire(blocking=False):
        cached_refresh_token = getattr(
            capture_state,
            "cached_live_table_snapshot_refresh_token",
            None,
        )
        if isinstance(cached_refresh_token, tuple) and len(cached_refresh_token) == 2:
            return (
                int(cached_refresh_token[0]),
                int(cached_refresh_token[1]),
            )
        async_state = getattr(capture_state, "live_suji_async_state", None)
        red_tint_async_state = getattr(capture_state, "live_red_tint_async_state", None)
        return (
            int(getattr(capture_state, "live_update_sequence", 0)),
            (
                (int(getattr(async_state, "update_sequence", 0)) << 32)
                | int(getattr(red_tint_async_state, "update_sequence", 0))
            )
            if LIVE_ASYNC_BUNDLE_REFRESH_ENABLED
            else 0,
        )
    try:
        async_state = _get_live_suji_async_state(capture_state)
        red_tint_async_state = _get_live_red_tint_async_state(capture_state)
        return (
            int(capture_state.live_update_sequence),
            (
                (int(async_state.update_sequence) << 32) | int(red_tint_async_state.update_sequence)
            )
            if LIVE_ASYNC_BUNDLE_REFRESH_ENABLED
            else 0,
        )
    finally:
        state_lock.release()


class AsyncLiveTableSnapshotProvider:
    """Build live table snapshots away from the Tk thread and publish completed frames."""

    def __init__(
        self,
        capture_state: CaptureState,
        initial_snapshot: LiveTableSnapshot,
        *,
        snapshot_builder: Callable[[CaptureState], LiveTableSnapshot] = build_live_table_snapshot,
        refresh_token_reader: Callable[[CaptureState], object | None] = build_live_refresh_token,
        reinit_action: Callable[[CaptureState], object | None] = force_live_table_snapshot_reinit,
    ) -> None:
        self._capture_state = capture_state
        self._snapshot_builder = snapshot_builder
        self._refresh_token_reader = refresh_token_reader
        self._reinit_action = reinit_action
        self._lock = threading.Lock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._latest_snapshot = initial_snapshot
        self._pending_refresh_token: object | None = None
        self._in_flight_refresh_token: object | None = None
        self._last_error_text = ""
        self._last_request_latest_monotonic_s = 0.0

    def _ensure_worker_locked(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="live-table-snapshot",
            daemon=True,
        )
        if threading.current_thread() is threading.main_thread():
            table_view.show_thread_activity_notice("live snapshot")
        self._worker_thread.start()

    def _queue_refresh_token(self, refresh_token: object | None) -> None:
        with self._lock:
            latest_refresh_token = getattr(self._latest_snapshot, "refresh_token", None)
            if refresh_token == latest_refresh_token or refresh_token == self._in_flight_refresh_token:
                return
            if refresh_token == self._pending_refresh_token:
                return
            self._pending_refresh_token = refresh_token
            self._ensure_worker_locked()
            self._wake_event.set()

    def request_latest(self) -> None:
        now_monotonic_s = time.monotonic()
        with self._lock:
            if (
                now_monotonic_s - self._last_request_latest_monotonic_s
                < LIVE_SNAPSHOT_REQUEST_MIN_INTERVAL_S
            ):
                return
            self._last_request_latest_monotonic_s = now_monotonic_s
        try:
            refresh_token = self._refresh_token_reader(self._capture_state)
        except Exception as exc:  # noqa: BLE001 - UI polling must stay non-blocking.
            error_text = f"{type(exc).__name__}: {exc}"
            with self._lock:
                if self._last_error_text != error_text:
                    self._last_error_text = error_text
                    print(f"Live snapshot refresh-token read skipped: {error_text}", file=sys.stderr)
            return
        self._queue_refresh_token(refresh_token)

    def current_snapshot(self) -> LiveTableSnapshot:
        self.request_latest()
        with self._lock:
            return self._latest_snapshot

    def current_refresh_token(self) -> object | None:
        self.request_latest()
        with self._lock:
            return getattr(self._latest_snapshot, "refresh_token", None)

    def force_reinit(self) -> object | None:
        try:
            refresh_token = self._reinit_action(self._capture_state)
        except Exception as exc:  # noqa: BLE001 - manual REINIT should surface as a deferred retry.
            error_text = f"{type(exc).__name__}: {exc}"
            with self._lock:
                if self._last_error_text != error_text:
                    self._last_error_text = error_text
                    print(f"Live snapshot REINIT skipped: {error_text}", file=sys.stderr)
            return self.current_refresh_token()
        self._queue_refresh_token(refresh_token)
        with self._lock:
            return getattr(self._latest_snapshot, "refresh_token", None)

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        worker_thread = self._worker_thread
        if (
            worker_thread is not None
            and worker_thread is not threading.current_thread()
            and worker_thread.is_alive()
        ):
            worker_thread.join(timeout=1.0)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                refresh_token = self._pending_refresh_token
                self._pending_refresh_token = None
                self._in_flight_refresh_token = refresh_token
            if refresh_token is None:
                self._wake_event.wait()
                self._wake_event.clear()
                continue
            table_view.begin_thread_activity_notice("live snapshot")
            try:
                snapshot = self._snapshot_builder(self._capture_state)
            except Exception as exc:  # noqa: BLE001 - keep the snapshot worker alive after transient parse/cache errors.
                error_text = f"{type(exc).__name__}: {exc}"
                with self._lock:
                    self._in_flight_refresh_token = None
                    if self._last_error_text != error_text:
                        self._last_error_text = error_text
                        print(f"Live snapshot build skipped: {error_text}", file=sys.stderr)
                continue
            finally:
                table_view.finish_thread_activity_notice("live snapshot")
            with self._lock:
                self._latest_snapshot = snapshot
                self._in_flight_refresh_token = None
                self._last_error_text = ""


def main() -> None:
    """Parse args, prepare state, and launch the Tkinter table UI."""

    parser = argparse.ArgumentParser(
        description="Tenhou Helper UI",
        epilog=(
            "Execution modes:\n"
            "  Live capture:\n"
            "    py src/tenhou_hojo.py\n"
            f"    py src/tenhou_hojo.py --tls-keylog {TLS_KEYLOG_FILE}\n"
            "    py src/tenhou_hojo.py --debug-tags\n"
            "\n"
            "  Pcap replay:\n"
            "    py src/tenhou_hojo.py --test sample.pcapng --tls-keylog sample.keys --test-interval-ms 0\n"
            "    py src/tenhou_hojo.py --test sample.pcapng --tls-keylog sample.keys --debug-tags\n"
            "\n"
            "  XML log:\n"
            "    py src/tenhou_hojo.py --xml-url https://...\n"
            "    py src/tenhou_hojo.py --xml-url-list urls.txt\n"
            "    py src/tenhou_hojo.py --xml-url https://... --xml-self-player-name パシフィック\n"
            "\n"
            "  Mock:\n"
            "    py src/tenhou_hojo.py --mock\n"
            "    py src/tenhou_hojo.py --mock 2"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--mock",
        nargs="?",
        const=DEFAULT_MOCK_PATTERN,
        type=int,
        choices=AVAILABLE_MOCK_PATTERNS,
        metavar="PATTERN",
        help="Use mock packet data pattern 1-3. Omit the number to use pattern 1.",
    )
    input_group.add_argument(
        "--test",
        type=Path,
        metavar="INPUT_PCAPNG",
        help="Replay decrypted tag packets from a .pcapng file via tshark.",
    )
    input_group.add_argument(
        "--xml-url",
        metavar="URL",
        help="Fetch a URL, follow its log/? XML link, and load the Tenhou XML log.",
    )
    input_group.add_argument(
        "--xml-url-list",
        type=Path,
        metavar="URL_LIST_TXT",
        help="Read newline-delimited XML/viewer URLs from a text file and import them sequentially.",
    )
    parser.add_argument(
        "--test-interval-ms",
        type=int,
        default=DEFAULT_TEST_PACKET_INTERVAL_MS,
        metavar="MILLISECONDS",
        help=(
            "When --test is used, feed matching decrypted tag packets at this interval in "
            "milliseconds. Default: %(default)s."
        ),
    )
    parser.add_argument(
        "--tls-keylog",
        type=Path,
        metavar="TLS_KEYS",
        help=(
            "Use this TLS keylog file for live capture or --test replay decryption. "
            f"If omitted, the default path {TLS_KEYLOG_FILE} is used."
        ),
    )
    parser.add_argument(
        "--tshark-interface",
        metavar="IFACE",
        help=(
            "Live-capture tshark interface index or name. "
            f"If omitted, prefer a non-loopback adapter and otherwise fall back to {TSHARK_INTERFACE}."
        ),
    )
    parser.add_argument(
        "--debug-tags",
        action="store_true",
        help="Print every extracted tag fragment and parsed event summary to stdout for debugging.",
    )
    parser.add_argument(
        "--p",
        action="store_true",
        dest="start_pystyle_auto_mode",
        help="Start with pystyle auto mode enabled.",
    )
    parser.add_argument(
        "--test-tls-keylog",
        dest="legacy_test_tls_keylog",
        type=Path,
        metavar="TLS_KEYS",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--xml-self-abs-seat",
        type=int,
        choices=range(4),
        metavar="SEAT",
        help="Override XML self absolute seat (0-3). If omitted, --xml-url tw= is used when present.",
    )
    parser.add_argument(
        "--xml-self-player-name",
        metavar="NAME",
        help="Resolve XML self seat by matching this player name against UN.n0..n3.",
    )
    parser.add_argument(
        "--disable-tenhou-ui-bridge",
        action="store_true",
        help="Do not start the localhost WebSocket server used by the Chrome Tenhou UI Bridge.",
    )
    parser.add_argument(
        "--tenhou-ui-bridge-host",
        default=os.environ.get("TENHOU_UI_BRIDGE_HOST", DEFAULT_TENHOU_UI_BRIDGE_HOST),
        metavar="HOST",
        help=(
            "Local WebSocket host for the Tenhou UI Bridge service worker. "
            "Default: %(default)s."
        ),
    )
    parser.add_argument(
        "--tenhou-ui-bridge-port",
        type=int,
        default=int(
            os.environ.get(
                "TENHOU_UI_BRIDGE_PORT",
                DEFAULT_TENHOU_UI_BRIDGE_PORT,
            )
        ),
        metavar="PORT",
        help=(
            "Local WebSocket port for the Tenhou UI Bridge service worker. "
            "Default: %(default)s."
        ),
    )
    args = parser.parse_args()

    if args.legacy_test_tls_keylog is not None:
        if args.tls_keylog is not None and args.tls_keylog != args.legacy_test_tls_keylog:
            parser.error("--tls-keylog and --test-tls-keylog must match when both are provided.")
        args.tls_keylog = args.legacy_test_tls_keylog

    if args.test is not None and args.test.suffix.lower() != ".pcapng":
        parser.error("--test expects a .pcapng input file.")
    if args.test is None and args.test_interval_ms != DEFAULT_TEST_PACKET_INTERVAL_MS:
        parser.error("--test-interval-ms can only be used together with --test.")
    if args.test_interval_ms < 0:
        parser.error("--test-interval-ms must be >= 0.")
    if args.tls_keylog is not None and (
        args.mock is not None or args.xml_url is not None or args.xml_url_list is not None
    ):
        parser.error("--tls-keylog can only be used with live capture or --test.")
    if args.test is not None and not args.test.exists():
        parser.error(f"--test input file not found: {args.test}")
    if args.tls_keylog is not None and not args.tls_keylog.exists():
        parser.error(f"--tls-keylog file not found: {args.tls_keylog}")
    if args.xml_url is None and args.xml_url_list is None and (
        args.xml_self_abs_seat is not None or args.xml_self_player_name is not None
    ):
        parser.error("--xml-self-abs-seat and --xml-self-player-name require --xml-url or --xml-url-list.")
    if args.xml_url_list is not None and not args.xml_url_list.exists():
        parser.error(f"--xml-url-list file not found: {args.xml_url_list}")
    if args.xml_url_list is not None and not args.xml_url_list.is_file():
        parser.error(f"--xml-url-list must point to a text file: {args.xml_url_list}")
    if not str(args.tenhou_ui_bridge_host).strip():
        parser.error("--tenhou-ui-bridge-host must not be empty.")
    if not 1 <= args.tenhou_ui_bridge_port <= 65535:
        parser.error("--tenhou-ui-bridge-port must be in 1..65535.")
    if args.xml_url_list is not None:
        url_list_iter = _iter_xml_url_list(args.xml_url_list)
        try:
            first_input_url = next(url_list_iter)
        except StopIteration:
            parser.error(f"--xml-url-list did not contain any URLs: {args.xml_url_list}")
        processed = 0
        failed = 0
        for input_url in itertools.chain((first_input_url,), url_list_iter):
            try:
                capture_state = _load_capture_state_from_xml_url(
                    input_url,
                    self_abs_seat=args.xml_self_abs_seat,
                    self_player_name=args.xml_self_player_name,
                )
            except Exception as exc:
                failed += 1
                print(f"[xml-url-list] failed: {input_url} :: {exc}", file=sys.stderr)
                continue
            processed += 1
            for diagnostic in capture_state.diagnostics:
                if diagnostic.get("code") == "xml_db_imported":
                    print(
                        "[xml-url-list] imported "
                        f"{input_url} :: hanchan_id={diagnostic.get('hanchan_id', '')} "
                        f"updated_rows={diagnostic.get('updated_rows', 0)} "
                        f"lag_rows_refined={diagnostic.get('lag_rows_refined', 0)}",
                        file=sys.stderr,
                    )
                if diagnostic.get("code") == "xml_db_import_failed":
                    print(
                        f"[xml-url-list] import skipped: {input_url} :: {diagnostic.get('message', '')}",
                        file=sys.stderr,
                    )
        print(f"[xml-url-list] completed: processed={processed} failed={failed}", file=sys.stderr)
        return

    root = tkinter.Tk()
    configure_window(root)

    img = table_view.initialize_image(root)
    capture_state: CaptureState | None = None
    bridge_visible_hand_provider: Callable[[], VisibleHandState] | None = None
    tenhou_ui_bridge_server: TenhouUiBridgeServer | None = None
    tenhou_ui_bridge_client: TenhouUiBridgeClient | None = None
    # The recommendation service owns cross-thread POST state; the renderer only sees immutable
    # panel snapshots plus a request callback.
    hand_recommendation_service = HandRecommendationService()
    hand_recommendation_service.set_thread_activity_callbacks(
        start_callback=table_view.begin_thread_activity_notice,
        finish_callback=table_view.finish_thread_activity_notice,
    )
    auto_refresh_ms: int | None = None
    hand_tiles = None
    hand_tiles_provider = None
    meld_tiles = None
    meld_tiles_provider = None
    dora_indicator_tiles = None
    dora_indicator_tiles_provider = None
    visible_summary = None
    visible_summary_provider = None
    hand_draw_tile = None
    hand_draw_tile_provider = None
    hand_recommendation_panel = _build_hand_recommendation_panel_data(hand_recommendation_service)
    hand_recommendation_panel_provider = (
        lambda: _build_hand_recommendation_panel_data(hand_recommendation_service)
    )
    hand_recommendation_request_context = None
    hand_recommendation_request_context_provider = None
    hand_recommendation_request_action = (
        lambda hand_tiles_37, request_context=None: hand_recommendation_service.request(
            hand_tiles_37,
            display_context=request_context,
        )
    )
    hand_recommendation_reset_action = hand_recommendation_service.reset
    hand_recommendation_history_action = None
    hand_danger_percentages = None
    hand_danger_percentages_provider = None
    opponent_suji_panel_summaries = None
    opponent_suji_panel_summaries_provider = None
    player_push_alert_percentages = {}
    player_alert_indicators_by_seat: dict[int, tuple[table_view.PlayerAlertIndicator, ...]] = {}
    player_score_diffs_by_seat: dict[int, int] = {
        int(Player.KAMICHA): 0,
        int(Player.TOIMEN): 0,
        int(Player.SHIMOCHA): 0,
    }
    discard_red_tint_indices_by_seat: dict[int, tuple[int, ...]] = {}
    player_names_by_seat = None
    player_names_by_seat_provider = None
    round_info_panel = table_view.RoundInfoPanelData()
    round_info_panel_provider = None
    round_identity = None
    round_identity_provider = None
    refresh_token = None
    refresh_token_provider = None
    melds_by_player = {player: [] for player in Player}
    melds_by_player_provider = None
    table_snapshot_provider = None
    table_snapshot_reinit_action = None
    live_table_snapshot_provider: AsyncLiveTableSnapshotProvider | None = None
    capture_state: CaptureState | None = None
    live_runtime_watchdog_enabled = False

    if args.mock is not None:
        mock_inputs = get_mock_inputs(args.mock)
        tracker = build_mock_tracker(args.mock)
        melds_by_player = build_mock_meld_map(args.mock)
        player_push_alert_percentages = {}
        hand_tiles = tiles136_to_tiles37(mock_inputs.hand_tiles_136)
        meld_tiles = flatten_visible_meld_tiles(melds_by_player)
        dora_indicator_tiles = tiles136_to_tiles37(mock_inputs.dora_indicator_tiles_136)
        hand_recommendation_request_context = PystyleDisplayContext(
            dora_indicator_tiles_37=tuple(dora_indicator_tiles),
            melds=_build_pystyle_self_meld_requests(
                list(melds_by_player.get(Player.JICHA, ()))
            ),
            remaining_wall=_build_pystyle_remaining_wall(
                [
                    int(discard.tile_id)
                    for discards in tracker.discards.values()
                    for discard in discards
                    if not discard.called
                ],
                hand_tiles,
                meld_tiles,
                dora_indicator_tiles,
            ),
        )
        visible_summary = collect_visible_tile_summary(
            discard_map=tracker.discards,
            hand_tiles=hand_tiles,
            meld_tiles=meld_tiles,
            dora_indicator_tiles=dora_indicator_tiles,
        )
        player_score_diffs_by_seat = {
            int(Player.KAMICHA): 0,
            int(Player.TOIMEN): 0,
            int(Player.SHIMOCHA): 0,
        }
        player_names_by_seat = dict(DEFAULT_PLAYER_NAMES_BY_SEAT)
        hand_draw_tile = None
        hand_danger_percentages = None
        hand_tiles_provider = None
        meld_tiles_provider = None
        dora_indicator_tiles_provider = None
        bridge_visible_hand_provider = lambda: build_visible_hand_state(
            hand_tiles,
            hand_draw_tile,
        )
    elif args.xml_url is not None:
        capture_state = _load_capture_state_from_xml_url(
            args.xml_url,
            self_abs_seat=args.xml_self_abs_seat,
            self_player_name=args.xml_self_player_name,
        )
        tracker = capture_state.tracker
        hand_tiles = tiles136_to_tiles37(capture_state.live_hand_tiles_136)
        melds_by_player = build_live_meld_map(capture_state)
        meld_tiles = flatten_visible_meld_tiles(melds_by_player)
        dora_indicator_tiles = tiles136_to_tiles37(capture_state.live_dora_indicator_tiles_136)
        visible_summary = build_live_visible_tile_summary(capture_state)
        hand_draw_tile = build_live_hand_draw_tile(capture_state)
        hand_danger_percentages = build_live_hand_danger_metrics(capture_state)
        opponent_suji_panel_summaries = build_live_opponent_suji_panel_summaries(capture_state)
        player_push_alert_percentages = build_live_player_push_alert_percentages(capture_state)
        player_alert_indicators_by_seat = table_view.build_player_panel_alert_indicators_by_seat(
            opponent_suji_panel_summaries,
            player_push_alert_percentages,
        )
        player_score_diffs_by_seat = build_live_player_score_diffs_by_seat(capture_state)
        discard_red_tint_indices_by_seat = build_live_discard_red_tint_indices_by_seat(
            capture_state
        )
        player_names_by_seat = build_live_player_names_by_seat(capture_state)
        round_info_panel = build_live_round_info_panel(capture_state)
        round_identity = build_live_round_identity(capture_state)
        refresh_token = capture_state.live_update_sequence
        hand_recommendation_request_context = build_live_pystyle_display_context(capture_state)
        bridge_visible_hand_provider = lambda: build_live_visible_hand_state(capture_state)
        hand_recommendation_history_action = (
            lambda hand_tiles_37, hand_recommendation_panel, display_context: _remember_visible_pystyle_history(
                capture_state,
                hand_tiles_37,
                hand_recommendation_panel,
                display_context,
            )
        )
        hand_tiles_provider = None
        hand_danger_percentages_provider = None
        opponent_suji_panel_summaries_provider = None
        player_names_by_seat_provider = None
        meld_tiles_provider = None
        dora_indicator_tiles_provider = None
        if not capture_state.seat_mapping_resolved:
            print(
                "XML seat mapping is unresolved. Pass --xml-self-abs-seat or "
                "--xml-self-player-name if the URL does not include tw=.",
                file=sys.stderr,
            )
    else:
        capture_state = CaptureState()
        live_runtime_watchdog_enabled = True
        _start_live_runtime_watchdog(capture_state)
        initial_snapshot = build_live_table_snapshot(capture_state)
        live_table_snapshot_provider = AsyncLiveTableSnapshotProvider(
            capture_state,
            initial_snapshot,
        )
        tracker = initial_snapshot.discard_map
        hand_tiles = initial_snapshot.hand_tiles
        meld_tiles = initial_snapshot.meld_tiles
        dora_indicator_tiles = initial_snapshot.dora_indicator_tiles
        visible_summary = initial_snapshot.visible_summary
        hand_draw_tile = initial_snapshot.hand_draw_tile
        hand_danger_percentages = initial_snapshot.hand_danger_percentages
        opponent_suji_panel_summaries = initial_snapshot.opponent_suji_panel_summaries
        player_push_alert_percentages = initial_snapshot.player_push_alert_percentages
        player_alert_indicators_by_seat = initial_snapshot.player_alert_indicators_by_seat
        player_score_diffs_by_seat = initial_snapshot.player_score_diffs_by_seat
        discard_red_tint_indices_by_seat = initial_snapshot.discard_red_tint_indices_by_seat
        player_names_by_seat = initial_snapshot.player_names_by_seat
        round_info_panel = initial_snapshot.round_info_panel
        round_identity = initial_snapshot.round_identity
        refresh_token = initial_snapshot.refresh_token
        hand_recommendation_request_context = initial_snapshot.hand_recommendation_request_context
        auto_refresh_ms = None
        start_capture_thread(
            capture_state,
            test_input_path=args.test,
            tls_keylog_path=args.tls_keylog,
            tshark_interface=args.tshark_interface,
            test_interval_ms=args.test_interval_ms,
            debug_tags=args.debug_tags,
        )
        hand_recommendation_history_action = (
            lambda hand_tiles_37, hand_recommendation_panel, display_context: _remember_visible_pystyle_history(
                capture_state,
                hand_tiles_37,
                hand_recommendation_panel,
                display_context,
            )
        )
        refresh_token_provider = live_table_snapshot_provider.current_refresh_token
        table_snapshot_provider = live_table_snapshot_provider.current_snapshot
        table_snapshot_reinit_action = live_table_snapshot_provider.force_reinit
        melds_by_player = initial_snapshot.melds_by_player
        bridge_visible_hand_provider = lambda: build_live_visible_hand_state(capture_state)

    naga_query_state_provider = (
        (lambda: _build_naga_query_state_from_capture_state(capture_state))
        if capture_state is not None
        else None
    )
    naga_ui_state = NagaAnalyzerUiState(
        storage_state_path=naga_analyzer.resolve_storage_state_path(),
        raw_output_dir=naga_analyzer.resolve_raw_output_dir(),
        query_state_provider=naga_query_state_provider,
        capture_state=capture_state,
    )

    # Live redraw must react to both packet updates and finished AI responses, so combine the
    # capture refresh token with the recommendation-service refresh sequence.
    refresh_token_provider, refresh_token = _build_combined_refresh_token_provider(
        refresh_token,
        refresh_token_provider,
        hand_recommendation_service,
        extra_update_sequence_provider=lambda: naga_ui_state.auto_update_sequence,
    )
    if bridge_visible_hand_provider is None:
        bridge_visible_hand_provider = lambda: build_visible_hand_state(
            hand_tiles,
            hand_draw_tile,
        )
    if not args.disable_tenhou_ui_bridge:
        try:
            # Start the browser-executor bridge inside the same local process so the visualizer can
            # remain the single source of truth for action decisions.
            tenhou_ui_bridge_server = TenhouUiBridgeServer(
                host=args.tenhou_ui_bridge_host,
                port=args.tenhou_ui_bridge_port,
            )
            tenhou_ui_bridge_server.start()
            tenhou_ui_bridge_client = TenhouUiBridgeClient(
                tenhou_ui_bridge_server,
                visible_hand_provider=bridge_visible_hand_provider,
            )
            root.tenhou_ui_bridge_server = tenhou_ui_bridge_server
            root.tenhou_ui_bridge_client = tenhou_ui_bridge_client
            print(
                f"Tenhou UI Bridge listening on "
                f"{build_tenhou_ui_bridge_ws_url(args.tenhou_ui_bridge_host, args.tenhou_ui_bridge_port)}",
                file=sys.stderr,
            )
            print(
                "Tenhou UI Bridge startup order: app -> confirm extension enabled in browser -> "
                "open/reload Tenhou page (browser may already be open).",
                file=sys.stderr,
            )
        except Exception as exc:
            print(f"Tenhou UI Bridge disabled: {exc}", file=sys.stderr)

    hand_auto_discard_action = _build_tenhou_ui_bridge_auto_discard_action(
        tenhou_ui_bridge_client
    )
    hand_bridge_discard_by_index_action = _build_tenhou_ui_bridge_manual_discard_action(
        tenhou_ui_bridge_client
    )
    bridge_status_provider = _build_tenhou_ui_bridge_status_provider(
        tenhou_ui_bridge_client
    )
    bridge_ui_snapshot_action = _build_tenhou_ui_bridge_snapshot_action(
        tenhou_ui_bridge_client
    )
    bridge_table_snapshot_action = (
        _build_tenhou_ui_bridge_table_snapshot_action(
            tenhou_ui_bridge_client,
            capture_state,
        )
        if capture_state is not None
        else None
    )
    bridge_click_control_action = _build_tenhou_ui_bridge_control_click_action(
        tenhou_ui_bridge_client
    )

    if live_runtime_watchdog_enabled and capture_state is not None:
        _schedule_live_runtime_ui_heartbeat(root, capture_state)

    root.after(
        0,
        lambda: _install_naga_button(
            root,
            capture_state=capture_state,
            query_state_provider=naga_query_state_provider,
            ui_state=naga_ui_state,
        ),
    )
    _schedule_naga_auto_refresh(root, naga_ui_state)

    table_view.create_canvas(
        root,
        img,
        tracker,
        hand_tiles=hand_tiles,
        hand_draw_tile=hand_draw_tile,
        hand_recommendation_panel=hand_recommendation_panel,
        hand_danger_percentages=hand_danger_percentages,
        opponent_suji_panel_summaries=opponent_suji_panel_summaries,
        player_push_alert_percentages=player_push_alert_percentages,
        player_alert_indicators_by_seat=player_alert_indicators_by_seat,
        player_score_diffs_by_seat=player_score_diffs_by_seat,
        discard_red_tint_indices_by_seat=discard_red_tint_indices_by_seat,
        player_names_by_seat=player_names_by_seat,
        meld_tiles=meld_tiles,
        dora_indicator_tiles=dora_indicator_tiles,
        round_info_panel=round_info_panel,
        auto_refresh_ms=auto_refresh_ms,
        hand_tiles_provider=hand_tiles_provider,
        hand_draw_tile_provider=hand_draw_tile_provider,
        hand_recommendation_panel_provider=hand_recommendation_panel_provider,
        hand_recommendation_request_action=hand_recommendation_request_action,
        hand_recommendation_reset_action=hand_recommendation_reset_action,
        hand_auto_discard_action=hand_auto_discard_action,
        hand_bridge_discard_by_index_action=hand_bridge_discard_by_index_action,
        bridge_status_provider=bridge_status_provider,
        bridge_ui_snapshot_action=bridge_ui_snapshot_action,
        bridge_table_snapshot_action=bridge_table_snapshot_action,
        bridge_click_control_action=bridge_click_control_action,
        start_pystyle_auto_mode=bool(args.start_pystyle_auto_mode),
        hand_recommendation_history_action=hand_recommendation_history_action,
        hand_recommendation_request_context=hand_recommendation_request_context,
        hand_recommendation_request_context_provider=hand_recommendation_request_context_provider,
        hand_danger_percentages_provider=hand_danger_percentages_provider,
        opponent_suji_panel_summaries_provider=opponent_suji_panel_summaries_provider,
        player_names_by_seat_provider=player_names_by_seat_provider,
        meld_tiles_provider=meld_tiles_provider,
        dora_indicator_tiles_provider=dora_indicator_tiles_provider,
        round_info_panel_provider=round_info_panel_provider,
        naga_auto_panel_provider=lambda: _build_naga_auto_panel_data(naga_ui_state),
        melds_by_player=melds_by_player,
        melds_by_player_provider=melds_by_player_provider,
        visible_summary=visible_summary,
        visible_summary_provider=visible_summary_provider,
        round_identity=round_identity,
        round_identity_provider=round_identity_provider,
        table_snapshot_provider=table_snapshot_provider,
        table_snapshot_reinit_action=table_snapshot_reinit_action,
        refresh_token=refresh_token,
        refresh_token_provider=refresh_token_provider,
    )


if __name__ == "__main__":
    main()
