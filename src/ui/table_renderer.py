from __future__ import annotations

from collections import deque
from collections.abc import Sequence as SequenceABC
from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
import json
from pathlib import Path
import queue
import random
import threading
import time
import tkinter
import tkinter.font as tkfont
from typing import Any, Callable, Collection, Iterable, Mapping, Sequence

try:
    import winsound
except ImportError:  # pragma: no cover - non-Windows fallback
    winsound = None

from PIL import Image, ImageTk

from app.pystyle_simulator_protocol import PystyleDisplayContext
from app.tenhou_ui_bridge_protocol import TenhouUiBridgeStatus
from capture.storage import load_player_profile, save_player_profile_user_memo
from capture.state import (
    LAG_FLAG_TRUE_UNCALLED_PROBABLE,
    LAG_FLAG_UNCONFIRMED,
    Meld,
    tile136_to_tile34_index,
    tile136_to_tile37,
)
from logic.danger_suji import (
    HAND_PATTERN_ALERT_RED_LEVEL,
    HAND_PATTERN_ALERT_YELLOW_LEVEL,
    MENZEN_ALERT_RED_SCORE,
    MENZEN_ALERT_YELLOW_SCORE,
    NO_TEMP_REMAIN_RED_TINT_THRESHOLD,
)
from sutehai import Discard, DrawType, Player, SutehaiTracker
from visible_tiles import (
    THREE_VISIBLE_TILES_ENABLED,
    VisibleTileInferenceSummary,
    VisibleTileSummary,
    VISIBLE_TILE_IDS_34,
    build_visible_tile_inference_summary,
    collect_visible_tile_summary,
    tile37_to_tile34,
    tile37_to_tile34_index,
)
from ui.tile_images import (
    PLAYER_ROTATIONS,
    TileImageTable,
    build_tile_photoimage_from_base_overlay,
    build_tile_photoimage,
    initialize_image,
    logical_tile_id_to_asset_tile_id,
    resolve_tiles_dir as _resolve_tiles_dir,
    tile_size as _tile_size,
    warm_unrotated_tile_overlay_bases,
)

# 37種表現の牌画像を読み込む前提なので、赤5を含めた総数を固定値で持つ。
N_TILES = 37
# ウィンドウ最小サイズ。リサイズ時もこの大きさを下回らない前提でレイアウト計算する。
WINDOW_MIN_WIDTH = 670
WINDOW_MIN_HEIGHT = 640
# 手牌が未指定のときに描画へ使う仮手牌。赤5は各スート1枚までに抑える。
DEFAULT_HAND_TILES = [1, 2, 3, 10, 5, 6, 11, 15, 16, 21, 25, 31, 32]
# 詳細パネル内で使う縮小牌画像の最大サイズ。
DETAIL_TILE_MAX_WIDTH = 22
DETAIL_TILE_MAX_HEIGHT = 32
DETAIL_VISIBLE_COLUMNS = 8
DETAIL_VISIBLE_ROWS = 3
# 中央局情報パネル内で使うドラ表示牌画像の最大サイズ。
CENTER_DORA_MAX_WIDTH = 18
CENTER_DORA_MAX_HEIGHT = 28

# 卓外背景と卓枠の配色定義。
BOARD_OUTER = "#101820"
BOARD_FRAME = "#1a2430"
TABLE_FILL = "#2a4f86"
TABLE_BORDER = "#16202c"
# 中央パネルや文字色の配色定義。
CENTER_PANEL = "#11161f"
CENTER_PANEL_BORDER = "#737f93"
TEXT_PRIMARY = "#f2f4f8"
TEXT_SECONDARY = "#b9c0d0"
# 捨て牌エリアや影など盤面部品の配色定義。
ZONE_FILL = "#223f6c"
ZONE_OUTLINE = "#3d5d90"
SHADOW = "#09101c"
WALL_TILE = "#d8dce4"
WALL_EDGE = "#8f98ab"
WALL_DARK = "#1f2430"
# 河の牌は画像の透明余白ぶんだけ少し重ねて、間延びを防ぐ。
DISCARD_X_TIGHTEN = 4
DISCARD_Y_TIGHTEN = 6
HAND_TILE_GAP = 0
DETAIL_PANEL_WIDTH = 220
DETAIL_PANEL_GAP = 20
HORIZONTAL_PANEL_WIDTH = 680
HORIZONTAL_PANEL_HEIGHT = 96
VERTICAL_PANEL_WIDTH = 110
# 左右プレイヤーパネルは必要以上に下へ伸ばさず、卓の縦バランスに収まる高さを基本値にする。
VERTICAL_PANEL_HEIGHT = 524
SIDE_MELD_MIN_WIDTH = 72
TOP_DISCARD_WIDTH = 280
TOP_DISCARD_HEIGHT = 150
SIDE_DISCARD_WIDTH = 190
SIDE_DISCARD_HEIGHT = 210
BOTTOM_DISCARD_WIDTH = 280
BOTTOM_DISCARD_HEIGHT = 116
CENTER_PANEL_WIDTH = 148
CENTER_PANEL_HEIGHT = 124
HAND_STRIP_WIDTH = 430
HAND_STRIP_HEIGHT = 74
SELF_LOWER_LAYOUT_SHIFT = 18
INFERRED_VISIBLE_TILE_PANEL_BUTTON_MARGIN_ABOVE_HAND = 24
INFERRED_VISIBLE_TILE_PANEL_SELECTOR_TILE_SCALE = 0.65
INFERRED_VISIBLE_TILE_PANEL_SELECTOR_COLUMNS = 10
INFERRED_VISIBLE_TILE_PANEL_SELECTOR_WINDOW_GAP = 18
INFERRED_VISIBLE_SELECTED_TILE_CARD_HEIGHT = 96
BRIDGE_SKIP_CONTROL_ID = 2360326
BRIDGE_SKIP_CONTROL_LABEL_HINTS = (
    "×",
    "skip",
    "pass",
    "cancel",
    "スキップ",
    "パス",
    "キャンセル",
    "見送り",
)
BRIDGE_CHI_CONTROL_IDS = frozenset({409610, 409609, 409608, 409614, 409613, 409612})
BRIDGE_PON_CONTROL_IDS = frozenset({409606, 409607})
BRIDGE_KAN_CONTROL_IDS = frozenset({409604, 401412, 401416, 401417, 401414, 401415, 401418, 401419})
BRIDGE_NAKI_CONTROL_IDS = frozenset({3671045})
BRIDGE_RIICHI_CONTROL_IDS = frozenset({2359814})
BRIDGE_AGARI_CONTROL_IDS = frozenset({2360328})
BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID = 1183752
BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID = 1183749
BRIDGE_ACTION_KIND_ORDER = ("ron", "tsumo", "riichi", "naki", "pon", "chi", "kan")
BRIDGE_ACTION_KIND_LABELS = {
    "chi": "チー",
    "kan": "カン",
    "naki": "鳴き",
    "pon": "ポン",
    "riichi": "リーチ",
    "ron": "ロン",
    "tsumo": "ツモ",
}
DISCARD_ZONE_GAP = 0
# 副露は牌画像の実寸で詰めて見せる。牌同士は隙間なし、面子間だけ最小限の余白を取る。
MELD_GROUP_GAP = 8
MELD_TILE_GAP = 0
MELD_ZONE_MARGIN = 6
MELD_ZONE_FILL = "#1d3154"
MELD_ZONE_OUTLINE = "#45648f"
MELD_RYANMEN_CHI_BORDER = "#facc15"
MELD_RYANMEN_CHI_BORDER_WIDTH = 2
MELD_RYANMEN_CHI_BORDER_PADDING = 2
CALLED_DISCARD_BORDER = "#c62828"
CALLED_DISCARD_BORDER_WIDTH = 2
POST_CALL_TEDASHI_DISCARD_BORDER = "#facc15"
POST_CALL_TEDASHI_DISCARD_BORDER_WIDTH = 2
THREE_VISIBLE_DISCARD_MARKER = "#ec4899"
FOUR_VISIBLE_DISCARD_MARKER = "#a855f7"
INFERRED_VISIBLE_DETAIL_BORDER = "#60a5fa"
LAG_DISCARD_MARKER = "#2563eb"
# Green lag markers highlight cases where someone else likely had the actual call window.
PON_LAG_LIKELY_DISCARD_MARKER = "#22c55e"
# Backward-compatible alias: two-player same-tile lag is still one of the green-marker triggers.
MULTI_PLAYER_LAG_DISCARD_MARKER = PON_LAG_LIKELY_DISCARD_MARKER
SAME_JUN_MATCH_DISCARD_MARKER = "#facc15"
PUSH_DISCARD_MARKER = "#a855f7"
LAG_MARKER_BADGE_FILL = "#4a2228"
PUSH_DISCARD_MARKER_BADGE_FILL = "#6a5611"
AWASEUCHI_MARKERS_ENABLED = True
AWASEUCHI_PROVISIONAL_PUBLIC_EVENT_WINDOW = 7
THREE_VISIBLE_MARKERS_ENABLED = THREE_VISIBLE_TILES_ENABLED
INFERRED_VISIBLE_ENABLED = False
PEAK_THINKING_TIME_DISCARD_MARKER = "#dc2626"
LAG_MARKER_REFERENCE_KIND_BLUE = "blue"
LAG_MARKER_REFERENCE_KIND_GREEN = "green"
LAG_MARKER_REFERENCE_KIND_BLACK = "black"
LAG_MARKER_REFERENCE_BUTTON_WIDTH = 56
LAG_MARKER_REFERENCE_BUTTON_HEIGHT = 20
LAG_MARKER_REFERENCE_BUTTON_GAP = 8
LAG_MARKER_REFERENCE_CIRCLE_RADIUS = 9
LAG_MARKER_REFERENCE_CIRCLE_GAP = 24
LAG_MARKER_REFERENCE_LABEL_TOP_GAP = 8
INFERRED_VISIBLE_REASON_PON_LAG = "pon_lag"
INFERRED_VISIBLE_REASON_RED_TINT_NEIGHBOR = "red_tint_neighbor"
INFERRED_VISIBLE_PON_LAG_AMOUNT = 1.8
INFERRED_VISIBLE_REVEAL_REDUCTION = 0.9
INFERRED_VISIBLE_RED_TINT_ADJACENT_AMOUNT = 0.9
INFERRED_VISIBLE_RED_TINT_TWO_AWAY_AMOUNT = 0.7
INFERRED_VISIBLE_FILL = "#121923"
INFERRED_VISIBLE_OUTLINE = "#36506f"
INFERRED_VISIBLE_ACTIVE_OUTLINE = "#dc2626"
INFERRED_VISIBLE_TEXT = "#d7deea"
INFERRED_VISIBLE_MUTED_TEXT = "#8fa2bb"
INFERRED_VISIBLE_BUTTON_FILL = "#1c2735"
INFERRED_VISIBLE_BUTTON_ACTIVE_FILL = "#29415d"
INFERRED_VISIBLE_BUTTON_OFF_FILL = "#0f172a"
INFERRED_VISIBLE_BUTTON_OFF_TEXT = "#607086"
INFERRED_VISIBLE_BUTTON_HEIGHT = 18
INFERRED_VISIBLE_BUTTON_GAP = 4
INFERRED_VISIBLE_SECTION_GAP = 6
INFERRED_VISIBLE_DELETE_BUTTON_WIDTH = 34
INFERRED_VISIBLE_MANUAL_BUTTON_WIDTH = 24
INFERRED_VISIBLE_MANUAL_BUTTON_GAP = 3
INFERRED_VISIBLE_TILE_SCALE = 0.6
INFERRED_VISIBLE_LABEL_BY_SEAT = {
    int(Player.KAMICHA): "上家",
    int(Player.TOIMEN): "対面",
    int(Player.SHIMOCHA): "下家",
}
# River tint priority follows the screen spec: qualifying red-highlight tiles are promoted to
# brown when every 3-sequence through the tile is dead by other 4-visible tiles, or to purple
# when the tile itself is 4-visible.
DISCARD_TINT_BRIGHTEN_COLOR = (255, 255, 255)
DISCARD_TINT_BRIGHTEN_BLEND = 0.08
DISCARD_RED_TINT_COLOR = (245, 124, 124)
DISCARD_RED_TINT_BLEND = 0.24
DISCARD_BROWN_TINT_COLOR = (186, 128, 62)
DISCARD_BROWN_TINT_BLEND = 0.36
DISCARD_FOUR_VISIBLE_TINT_COLOR = (192, 120, 255)
DISCARD_FOUR_VISIBLE_TINT_BLEND = 0.24
RIICHI_STICK_FILL = "#f8fafc"
RIICHI_STICK_RED = "#ef4444"
RIICHI_STICK_OUTLINE = "#94a3b8"
THINKING_TIME_MAX_MS = 7000.0
THINKING_TIME_TINT_STEPS = 50
THINKING_TIME_GREEN_COLOR = (120, 224, 120)
THINKING_TIME_BLUE_COLOR = (96, 165, 250)
THINKING_TIME_YELLOW_COLOR = (250, 204, 21)
THINKING_TIME_RED_COLOR = (220, 38, 38)
THINKING_TIME_PURPLE_COLOR = (168, 85, 247)
THINKING_TIME_OVERLAY_MAX_BLEND = 0.7
THINKING_TIME_UPPER_BAND_START_RATIO = 0.5
THINKING_TIME_UPPER_BAND_END_RATIO = 0.75
THINKING_TIME_LOWER_BAND_START_RATIO = 0.75
THINKING_TIME_LOWER_BAND_END_RATIO = 1.0
HAND_DANGER_TINT_MIN_PERCENT = 5.0
HAND_DANGER_TINT_MAX_PERCENT = 70.0
HAND_DANGER_TINT_STEPS = 50
HAND_DANGER_TINT_YELLOW_COLOR = (250, 204, 21)
HAND_DANGER_TINT_RED_COLOR = (220, 38, 38)
HAND_DANGER_TINT_MAX_BLEND = 0.55
HAND_DANGER_BAR_BLOCK_HEIGHT = 48
HAND_DANGER_BAR_TOP_MARGIN = 3
HAND_DANGER_BAR_MAX_HEIGHT = 26
HAND_DANGER_BAR_WIDTH = 5
HAND_DANGER_BAR_GAP = 3
HAND_DANGER_BAR_MIN_VISIBLE_HEIGHT = 2
HAND_DANGER_BAR_MAX_PERCENT = 30
HAND_DANGER_PERCENT_TEXT_TOP_MARGIN = 2
TABLE_SITUATION_PANEL_GAP = 6
TABLE_SITUATION_PANEL_HEIGHT = 118
TABLE_SITUATION_COMMON_PANEL_WIDTH = 126
TABLE_SITUATION_COMMON_PANEL_HEIGHT = 84
TABLE_SITUATION_COMMON_PANEL_RIGHT_SHIFT = 18
TABLE_SITUATION_SEAT_PANEL_WIDTH = 104
TABLE_SITUATION_SEAT_PANEL_HEIGHT = 102
TABLE_SITUATION_CELL_GAP = 4
TABLE_SITUATION_TITLE_FONT = ("Yu Gothic UI", 8, "bold")
TABLE_SITUATION_COMMON_TITLE_FONT = ("Yu Gothic UI", 5, "bold")
TABLE_SITUATION_HEADER_FONT = ("Consolas", 6, "bold")
TABLE_SITUATION_CELL_FONT = ("Consolas", 8, "bold")
TABLE_SITUATION_TOTAL_FONT = ("Consolas", 9, "bold")
TABLE_SITUATION_FILL = "#101826"
TABLE_SITUATION_OUTLINE = "#334155"
TABLE_SITUATION_TEXT = "#dbe7f3"
TABLE_SITUATION_MUTED_TEXT = "#8ea0b6"
TABLE_SITUATION_TOTAL_FILL = "#182434"
TABLE_SITUATION_TOTAL_OUTLINE = "#475569"
TABLE_SITUATION_BLOCK_COUNT = 10
TABLE_SITUATION_ENABLED = False
TABLE_SITUATION_MANUAL_SCORE_MAX = 4
TABLE_SITUATION_DISPLAY_SCORE_MAX = 4.0
TABLE_SITUATION_AUTO_FAST_TEDASHI_LIMIT = 4
TABLE_SITUATION_AUTO_FAST_THINKING_MS_MAX = 2000.0
TABLE_SITUATION_AUTO_BASE_ADJACENT_SCORE = -1.5
TABLE_SITUATION_AUTO_BASE_INNER_TWO_AWAY_SCORE = -1.0
TABLE_SITUATION_AUTO_FAST_ADJACENT_SCORE = -2.0
TABLE_SITUATION_AUTO_FAST_INNER_TWO_AWAY_SCORE = -1.5
TABLE_SITUATION_AUTO_RED_TINT_ADJACENT_SCORE = 1.5
TABLE_SITUATION_AUTO_RED_TINT_TWO_AWAY_SCORE = 1.0
TABLE_SITUATION_COL_LABELS = ("123", "456", "789")
TABLE_SITUATION_ROW_LABELS = ("M", "P", "S")
TABLE_SITUATION_COMMON_LABEL = "総計"
TABLE_SITUATION_CELL_LABELS = (
    "M123",
    "M456",
    "M789",
    "P123",
    "P456",
    "P789",
    "S123",
    "S456",
    "S789",
    "字",
)
LAYOUT_COMPONENT_OFFSET_LIMIT = 360
LAYOUT_DRAG_OUTLINE = "#67e8f9"
LAYOUT_DRAG_ACTIVE_OUTLINE = "#f59e0b"
LAYOUT_DRAG_LABEL_FILL = "#0f172a"
LAYOUT_DRAG_LABEL_TEXT = "#dbeafe"
LAYOUT_DRAG_LABEL_FONT = ("Consolas", 7, "bold")
LAYOUT_DRAG_LABEL_MARGIN = 4
LAYOUT_DRAG_DASH = (4, 2)


def _is_visual_lag_flag(lagged: int) -> bool:
    """Return True only for unresolved/probable uncalled lag that should stay visible on rivers."""

    return lagged in {
        LAG_FLAG_UNCONFIRMED,
        LAG_FLAG_TRUE_UNCALLED_PROBABLE,
    }


def _is_riseki_completion_discard(discard: object) -> bool:
    """Return whether one discard is an away/disconnect auto-tsumogiri completion."""

    return bool(getattr(discard, "is_tsumogiri_estimated", False))
HAND_DANGER_PERCENT_TEXT_FONT = ("Consolas", 6, "bold")
HAND_DANGER_NUMERATOR_TEXT_TOP_MARGIN = 8
HAND_DANGER_NUMERATOR_TEXT_FONT = ("Consolas", 5, "bold")
HAND_RESPONSE_BUTTON_WIDTH = 56
HAND_BETAORI_RESPONSE_BUTTON_WIDTH = 64
HAND_RESPONSE_BUTTON_HEIGHT = 22
HAND_RESPONSE_PANEL_WIDTH = 178
HAND_RESPONSE_PANEL_HEIGHT = 114
HAND_RESPONSE_PANEL_MARGIN = 8
HAND_RESPONSE_PANEL_RAISE = 10
HAND_RESPONSE_BUTTON_GAP = 6
HAND_RESPONSE_RESERVED_DRAW_SLOT_GAP = 16
HAND_RESPONSE_TILE_SCALE = 0.65
HAND_RESPONSE_ROW_GAP = 18
HAND_RESPONSE_BUTTON_FONT = ("Consolas", 8, "bold")
HAND_RESPONSE_TITLE_FONT = ("Consolas", 8, "bold")
HAND_RESPONSE_ROW_FONT = ("Consolas", 8, "bold")
HAND_RESPONSE_SUBTITLE_FONT = ("Consolas", 7)
HAND_RESPONSE_FILL = "#121923"
HAND_RESPONSE_OUTLINE = "#36506f"
HAND_RESPONSE_BUTTON_FILL = "#1c2735"
HAND_RESPONSE_BUTTON_ACTIVE_FILL = "#29415d"
HAND_RESPONSE_TEXT = "#d7deea"
HAND_RESPONSE_MUTED_TEXT = "#9fb0c6"
HAND_RESPONSE_HIGHLIGHT = "#34d399"
HAND_RESPONSE_NEAR_TOP_EV_THRESHOLD_PT = 50.0
HAND_SELF_ALERT_WIDTH = 72
HAND_SELF_ALERT_GAP = 6
HAND_SELF_ALERT_FONT = ("Consolas", 7, "bold")
HAND_SELF_DORA_VISIBLE_GAP = 6
HAND_SELF_DORA_VISIBLE_WIDTH = 42
HAND_SELF_DORA_VISIBLE_FONT = ("Yu Gothic UI", 7, "bold")
HAND_AUTO_BUTTON_WIDTH = 84
HAND_AUTO_BUTTON_HEIGHT = 22
HAND_AUTO_BUTTON_OFF_FILL = "#1c2735"
HAND_AUTO_BUTTON_ON_FILL = "#1f5136"
HAND_AUTO_BUTTON_RUN_FILL = "#1d4f91"
HAND_AUTO_BUTTON_ERROR_FILL = "#5b1e28"
HAND_AUTO_BUTTON_DISABLED_FILL = "#3a4250"
HAND_AUTO_BUTTON_TEXT = "#d7deea"
HAND_AUTO_BUTTON_DISABLED_TEXT = "#9aa4b5"
HAND_AUTO_MODE_KIND_RECOMMENDATION = "recommendation"
HAND_AUTO_MODE_KIND_BETAORI = "betaori"
HAND_AUTO_RECOMMENDATION_RETRY_S = 3.0
HAND_AUTO_RECOMMENDATION_ERROR_FALLBACK_S = 2.0
HAND_PYSTYLE_AUTO_THINK_DELAY_S = 1.0
HAND_PYSTYLE_RESPONSE_EXTRA_THINK_DELAY_S = 0.9
HAND_PYSTYLE_TIMEOUT_FALLBACK_DELAY_S = 0.1
HAND_BETAORI_AUTO_THINK_BASE_S = 1.5
HAND_BETAORI_AUTO_THINK_SWING_S = 0.8
THREAD_ACTIVITY_NOTICE_TTL_S = 5.0
THREAD_ACTIVITY_NOTICE_FILL = "#16202c"
THREAD_ACTIVITY_NOTICE_OUTLINE = "#29415d"
THREAD_ACTIVITY_NOTICE_TEXT = "#d7deea"
THREAD_ACTIVITY_NOTICE_REDRAW_MIN_INTERVAL_S = 0.25
PLAYER_PANEL_ALERT_SOUND_MIN_INTERVAL_S = 0.9
SELF_HAND_ALERT_SOUND_MIN_INTERVAL_S = 0.9
BRIDGE_STATUS_TICK_MS = 250
BRIDGE_PERIODIC_SNAPSHOT_ENABLED = False
BRIDGE_SNAPSHOT_POLL_S = 0.8
BRIDGE_CONTROL_FOLLOWUP_SNAPSHOT_DELAYS_MS = (120, 320)
BRIDGE_TABLE_SNAPSHOT_READY_RETRY_MS = 1000
BRIDGE_TABLE_SNAPSHOT_READY_RETRY_LIMIT = 6
BRIDGE_STATUS_SUCCESS_TTL_S = 3.0
BRIDGE_STATUS_ERROR_TTL_S = 6.0
SLOW_REDRAW_LOG_THRESHOLD_MS = 250.0
UI_AUTO_REINIT_STALL_THRESHOLD_S = 15.0
UI_AUTO_REINIT_COOLDOWN_S = 15.0
UI_REDRAW_WATCHDOG_THREAD_POLL_S = 1.0
HAND_HONOR_VISIBLE_COUNT_TEXT = "#111827"
HAND_SELF_ALERT_FILL = "#171f2b"
HAND_SELF_ALERT_OUTLINE = "#3b4c63"
HAND_SELF_ALERT_MUTED_TEXT = "#8ea0b6"
HAND_SELF_ALERT_ACTIVE_FILL = "#2a1618"
HAND_SELF_ALERT_ACTIVE_OUTLINE = "#8b1e27"
HAND_SELF_ALERT_ACTIVE_TEXT = "#fecaca"
HAND_SELF_ALERT_WARNING_FILL = "#2a2416"
HAND_SELF_ALERT_WARNING_OUTLINE = "#b58f1b"
HAND_SELF_ALERT_WARNING_TEXT = "#fde68a"
HAND_SELF_ALERT_HIGH_FILL = "#16281e"
HAND_SELF_ALERT_HIGH_OUTLINE = "#23814a"
HAND_SELF_ALERT_HIGH_TEXT = "#bbf7d0"
HAND_SELF_ALERT_DOT_RADIUS = 4
HAND_SELF_ALERT_THRESHOLD = 600.0
HAND_SELF_ALERT_WARNING_THRESHOLD = 800.0
HAND_SELF_ALERT_HIGH_THRESHOLD = 3000.0
HAND_SELF_ALERT_OPEN_HAND_FACTOR = 0.8
HAND_SELF_ALERT_KIND_NONE = "none"
HAND_SELF_ALERT_KIND_LOW = "low_ev"
HAND_SELF_ALERT_KIND_WARNING = "warning_ev"
HAND_SELF_ALERT_KIND_HIGH = "high_ev"
HAND_DANGER_BAR_SEAT_ORDER = (int(Player.KAMICHA), int(Player.TOIMEN), int(Player.SHIMOCHA))
HAND_DANGER_BAR_COLOR_BY_SEAT = {
    int(Player.KAMICHA): "#2563eb",
    int(Player.TOIMEN): "#facc15",
    int(Player.SHIMOCHA): "#22c55e",
}

PhaseTiming = tuple[str, float]


def _append_phase_timing(
    timings: list[PhaseTiming],
    label: str,
    started_at: float,
) -> None:
    """Append one elapsed timing entry in milliseconds."""

    elapsed_ms = max(0.0, (time.perf_counter() - started_at) * 1000.0)
    timings.append((str(label), elapsed_ms))


def _format_phase_timing_breakdown(
    timings: Sequence[PhaseTiming] | None,
    *,
    top_n: int = 8,
    minimum_ms: float = 0.1,
) -> str:
    """Return one compact `label=12.3ms` breakdown string."""

    if not timings:
        return ""
    filtered = [
        (str(label), float(elapsed_ms))
        for label, elapsed_ms in timings
        if float(elapsed_ms) >= minimum_ms
    ]
    if not filtered:
        return ""
    filtered.sort(key=lambda entry: entry[1], reverse=True)
    limited = filtered[: max(1, int(top_n))]
    return ", ".join(f"{label}={elapsed_ms:.1f}ms" for label, elapsed_ms in limited)


def _capture_canvas_item_ids(canvas: tkinter.Canvas) -> tuple[int, ...]:
    """Return the current canvas item ids, or an empty tuple when unsupported."""

    find_all = getattr(canvas, "find_all", None)
    if not callable(find_all):
        return ()
    try:
        return tuple(int(item_id) for item_id in find_all())
    except (tkinter.TclError, TypeError, ValueError):
        return ()


def _tag_new_canvas_items(
    canvas: tkinter.Canvas,
    *,
    tag: str,
    previous_item_ids: Sequence[int],
) -> None:
    """Attach one tag to items created since `previous_item_ids` was sampled."""

    addtag_withtag = getattr(canvas, "addtag_withtag", None)
    if not callable(addtag_withtag):
        return
    previous_ids = set(int(item_id) for item_id in previous_item_ids)
    for item_id in _capture_canvas_item_ids(canvas):
        if item_id in previous_ids:
            continue
        try:
            addtag_withtag(tag, item_id)
        except tkinter.TclError:
            continue


def _delete_canvas_items_by_tags(canvas: tkinter.Canvas, *tags: str) -> None:
    """Delete the requested tagged canvas items while tolerating stale/destroyed widgets."""

    delete = getattr(canvas, "delete", None)
    if not callable(delete):
        return
    for tag in tags:
        try:
            delete(tag)
        except tkinter.TclError:
            continue


def _stable_render_signature(value: object) -> object:
    """Normalize nested render inputs into one comparable immutable signature."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if is_dataclass(value) and not isinstance(value, type):
        return (
            type(value).__name__,
            tuple(
                (field_info.name, _stable_render_signature(getattr(value, field_info.name)))
                for field_info in fields(value)
            ),
        )
    if isinstance(value, Mapping):
        normalized_items = [
            (_stable_render_signature(key), _stable_render_signature(item_value))
            for key, item_value in value.items()
        ]
        normalized_items.sort(key=lambda entry: repr(entry[0]))
        return tuple(normalized_items)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_stable_render_signature(item) for item in value), key=repr))
    if isinstance(value, SequenceABC) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_stable_render_signature(item) for item in value)
    return repr(value)


def _reset_transient_canvas_draw_state(canvas: tkinter.Canvas) -> None:
    """Clear per-frame mutable render caches before one board redraw path repopulates them."""

    canvas.detail_images = []
    canvas.center_panel_images = []
    canvas.player_panel_button_specs = []
    canvas.lag_marker_reference_button_specs = []
    canvas.inferred_visible_candidate_button_specs = []
    canvas.inferred_visible_tile_count_click_specs = []
    canvas.inferred_visible_manual_count_button_specs = []
    canvas.inferred_visible_delete_button_specs = []
    canvas.selected_inferred_visible_delete_button_specs = []
    canvas.table_situation_cell_click_specs = []
    canvas.hand_response_button_spec = None
    canvas.hand_betaori_response_button_spec = None
    canvas.self_hand_bridge_click_specs = []
    canvas.layout_drag_specs = []


PLAYER_PANEL_SUMMARY_FONT = ("Consolas", 8, "bold")
PLAYER_PANEL_SUMMARY_COMPACT_FONT = ("Consolas", 7, "bold")
PLAYER_PANEL_SUMMARY_REMAIN_LABEL_FONT = PLAYER_PANEL_SUMMARY_FONT
PLAYER_PANEL_SUMMARY_REMAIN_FONT = ("Consolas", 8, "bold")
PLAYER_PANEL_SUMMARY_LINE_FONT = ("Consolas", 7, "bold")
PLAYER_PANEL_SUMMARY_TINY_FONT = ("Consolas", 6, "bold")
PLAYER_PANEL_PUBLIC_HONOR_HEADING = "字牌2見え以下"
PLAYER_PANEL_PUBLIC_HONOR_TILE_GAP = 2
PLAYER_PANEL_PUBLIC_HONOR_SECTION_GAP = 2
PLAYER_PANEL_PUBLIC_HONOR_ROW_GAP = 2
PLAYER_PANEL_PUBLIC_HONOR_MAX_ROWS = 2
PLAYER_PANEL_PUBLIC_HONOR_DIM_OVERLAY_BANDS = (
    (0.0, 1.0, (24, 24, 24), (24, 24, 24), 0.42),
)
# 自家字牌ショートリストは河の中央より少しだけ下へ寄せ、副露帯と往復で見比べやすくする。
PLAYER_PANEL_PUBLIC_HONOR_SELF_MELD_BIAS_RATIO = 0.18
PLAYER_PANEL_TILE_RANK_TILE_SCALE = 0.24
PLAYER_PANEL_TILE_RANK_TILE_GAP = 1
PLAYER_PANEL_TILE_RANK_HORIZONTAL_ROW_GAP = 0
PLAYER_PANEL_TILE_RANK_VERTICAL_ROW_GAP = 0
PLAYER_PANEL_SUMMARY_LINE_ROW_GAP = 1
# 対面横長パネルは SUMMARY をやや広く、ALERT は少し詰めてボタン幅を確保する。
PLAYER_PANEL_HORIZONTAL_SUMMARY_RATIO = 0.62
PLAYER_PANEL_HORIZONTAL_ALERT_RATIO = 0.74
# 左右縦長パネルは SUMMARY を上下2ブロックで使い、ALERT はより小さくする。
# 左右縦長パネルは高さを詰める前提なので、ALERT を小さくして BUTTONS を確保する。
PLAYER_PANEL_VERTICAL_SUMMARY_RATIO = 0.56
PLAYER_PANEL_VERTICAL_ALERT_RATIO = 0.63
PLAYER_PANEL_NAME_FONT = ("Yu Gothic UI", 8, "bold")
PLAYER_PANEL_TILE_RANK_HEADING = "危険ランク"
PLAYER_PANEL_FALLBACK_NAME_BY_SEAT = {
    int(Player.JICHA): "YOU",
    int(Player.KAMICHA): "KAMI",
    int(Player.TOIMEN): "TOIMEN",
    int(Player.SHIMOCHA): "SHIMO",
}
PLAYER_PANEL_DETAIL_MEMO_FILL = "#274836"
PLAYER_PANEL_DETAIL_MEMO_ACTIVE_FILL = "#35664d"
PLAYER_PANEL_DETAIL_MEMO_OUTLINE = "#6aa37f"
PLAYER_ALERT_YELLOW = "#facc15"
PLAYER_ALERT_RED = "#dc2626"
PLAYER_ALERT_GREEN = "#22c55e"
PLAYER_ALERT_PURPLE = "#a855f7"
PLAYER_ALERT_NONE_TEXT = "#6b7a90"
PLAYER_ALERT_ROW_GAP = 16
PLAYER_ALERT_DOT_RADIUS = 4
PLAYER_PUSH_ALERT_PERSIST_TURNS = 3
PLAYER_PUSH_ALERT_PERSIST_DISCARD_WINDOW = PLAYER_PUSH_ALERT_PERSIST_TURNS * 4
PLAYER_PANEL_SECTION_MARGIN = 8
PLAYER_PANEL_SECTION_GAP = 8
PLAYER_PANEL_VERTICAL_SUMMARY_MIN_HEIGHT = 160
PLAYER_PANEL_VERTICAL_ALERT_MIN_HEIGHT = 68
PLAYER_PANEL_VERTICAL_SCORE_MIN_HEIGHT = 74
PLAYER_PANEL_HORIZONTAL_SCORE_WIDTH = 86
PLAYER_PANEL_SCORE_VALUE_FONT = ("Consolas", 11, "bold")
PLAYER_PANEL_SCORE_CAPTION_FONT = ("Yu Gothic UI", 7, "bold")
PLAYER_PANEL_SCORE_POSITIVE_TEXT = "#fca5a5"
PLAYER_PANEL_SCORE_NEGATIVE_TEXT = "#86efac"
PLAYER_PANEL_SCORE_NEUTRAL_TEXT = "#d7deea"
PLAYER_PANEL_SCORE_BUTTON_LABEL = "条件表示"
PLAYER_PANEL_SCORE_BUTTON_TOP_MARGIN = 48
PLAYER_PANEL_SCORE_BUTTON_BOTTOM_MARGIN = 6
PLAYER_PANEL_HORIZONTAL_BUTTON_HEIGHT = 12
PLAYER_PANEL_HORIZONTAL_BUTTON_GAP = 4
PLAYER_PANEL_HORIZONTAL_BUTTON_TOP_MARGIN = 22
PLAYER_PANEL_HORIZONTAL_BUTTON_BOTTOM_MARGIN = 4
PLAYER_PANEL_VERTICAL_BUTTON_HEIGHT = 18
PLAYER_PANEL_VERTICAL_BUTTON_GAP = 6
PLAYER_PANEL_VERTICAL_BUTTON_TOP_MARGIN = 22
PLAYER_PANEL_VERTICAL_BUTTON_BOTTOM_MARGIN = 4
PLAYER_PANEL_HORIZONTAL_SUMMARY_TOP_PACK = 6
DETAIL_EDITOR_TITLE_FONT = ("Yu Gothic UI", 10, "bold")
DETAIL_EDITOR_SUBTITLE_FONT = ("Yu Gothic UI", 8, "bold")
DETAIL_EDITOR_TEXT_FONT = ("Yu Gothic UI", 9)
DETAIL_EDITOR_STATUS_FONT = ("Consolas", 7, "bold")
DETAIL_EDITOR_INNER_MARGIN = 12
DETAIL_EDITOR_TITLE_HEIGHT = 36
DETAIL_EDITOR_ACTION_HEIGHT = 28
PLAYER_PANEL_BUTTON_LABELS = ("DETAIL", "STATUS", "プレイヤー補正")
RESPONSIVE_TRIGGER_SCREEN_WIDTH_RATIO = 0.5
RESPONSIVE_FALLBACK_TRIGGER_WIDTH = 960.0
RESPONSIVE_MIN_SCALE = 0.65
RESPONSIVE_SCALE_STEP = 0.05
PLAYER_PANEL_TITLE_BY_SEAT = {
    int(Player.KAMICHA): "KAMI",
    int(Player.TOIMEN): "TOIMEN",
    int(Player.SHIMOCHA): "SHIMO",
}

SeatMeldMap = Mapping[Player, Sequence[Meld]]
HandDangerPercentages = Mapping[int, object]
OpponentSujiPanelSummaries = Mapping[int, object]
PlayerPushAlertPercentages = Mapping[int, object]
PlayerAlertIndicatorsBySeat = Mapping[int, Sequence["PlayerAlertIndicator"]]
PlayerScoreDiffs = Mapping[int, object]
DiscardRedTintIndicesBySeat = Mapping[int, object]
PlayerNamesBySeat = Mapping[int, object]


@dataclass(frozen=True)
class RoundInfoPanelData:
    """Current round text shown in the compact center panel."""

    round_text: str = "東3局 1本場"
    kyotaku_text: str = "0"
    bootstrap_text: str = ""
    seat_wind_labels_by_seat: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PlayerAlertIndicator:
    color: str
    label: str
    key: str = ""


@dataclass(frozen=True)
class SameJunPublicEventSourceState:
    round_identity: object | None = None
    discard_counts_by_seat: tuple[int, ...] = ()
    discard_last_signatures_by_seat: tuple[tuple[object, ...] | None, ...] = ()
    meld_counts_by_seat: tuple[int, ...] = ()
    meld_last_signatures_by_seat: tuple[tuple[object, ...] | None, ...] = ()
    dora_count: int = 0
    dora_last_signature: tuple[object, ...] | None = None


@dataclass(frozen=True)
class PlayerPanelButtonSpec:
    seat: int
    label: str
    rect: tuple[float, float, float, float]


@dataclass(frozen=True)
class LagMarkerReferenceButtonSpec:
    kind: str
    center: tuple[float, float]
    radius: float
    entry_key: tuple[object, ...] = ()
    base_kind: str = LAG_MARKER_REFERENCE_KIND_BLUE


@dataclass(frozen=True)
class InferredVisibleCandidateButtonSpec:
    entry_key: tuple[object, ...]
    seat: int
    all_candidate_seats: tuple[int, ...]
    rect: tuple[float, float, float, float]
    entry_keys: tuple[tuple[object, ...], ...] = ()


@dataclass(frozen=True)
class InferredVisibleTileCountClickSpec:
    tile_34_index: int
    rect: tuple[float, float, float, float]


@dataclass(frozen=True)
class InferredVisibleManualCountButtonSpec:
    tile_34_index: int
    count: int
    rect: tuple[float, float, float, float]


@dataclass(frozen=True)
class InferredVisibleDeleteButtonSpec:
    entry_key: tuple[object, ...]
    rect: tuple[float, float, float, float]


@dataclass(frozen=True)
class DiscardTileSelectionClickSpec:
    tile_34_index: int
    rect: tuple[float, float, float, float]
    tile_37: int | None = None


@dataclass(frozen=True)
class InferredVisibleSelectedTileDeleteButtonSpec:
    rect: tuple[float, float, float, float]


@dataclass(frozen=True)
class TableSituationCellClickSpec:
    """One clickable manual score cell in the hand-side situation summary tables."""

    rect: tuple[float, float, float, float]
    seat: int
    block_index: int


@dataclass(frozen=True)
class InferredVisibleEntry:
    key: tuple[object, ...]
    tile_37: int
    tile_34_index: int
    source_kind: str
    source_event_index: int
    source_discard_index: int
    candidate_seats: tuple[int, ...]
    active_candidate_seats: tuple[int, ...]
    inactive_candidate_seats: tuple[int, ...]
    revealed_candidate_seats: tuple[int, ...]
    seat_adjustments_34_index: dict[int, tuple[float, ...]]
    total_adjustment: float


@dataclass
class DetailPanelState:
    view_kind: str = "visible"
    seat: int | None = None
    button_label: str = ""


@dataclass(frozen=True)
class HandRecommendationItem:
    """One discard recommendation row shown beside the self hand."""

    rank: int
    tile_text: str
    tile_37: int | None = None
    expected_value: float | None = None
    expected_value_text: str = ""
    win_probability: float | None = None


@dataclass(frozen=True)
class HandRecommendationPanelData:
    """Compact panel payload rendered by the self-hand `AI TOP3` popup."""

    items: tuple[HandRecommendationItem, ...] = ()
    hand_key: tuple[int, ...] = ()
    shanten: int | None = None
    round_token: str = ""
    request_context_key: tuple[object, ...] = ()
    top_expected_value: float | None = None
    subtitle_text: str = "pystyle.info へ現在手牌を POST します。"
    status_text: str = "AI TOP3 を押すと取得します。"
    is_loading: bool = False


@dataclass(frozen=True)
class HandResponseButtonSpec:
    rect: tuple[float, float, float, float]


@dataclass(frozen=True)
class HandResponseRenderState:
    hand_rect: tuple[float, float, float, float]
    button_anchor_right: float
    hand_visual_top: float
    baseline_y: float
    dora_indicator_tiles: tuple[int, ...]
    visible_summary: VisibleTileSummary | None
    recommendation_request_tiles: tuple[int, ...]
    round_identity: object | None
    self_melds: tuple[Meld, ...]
    hand_danger_percentages: tuple[HandDangerPercentages, ...] = ()


@dataclass(frozen=True)
class LiveAsyncRenderState:
    layout: dict[str, object]
    discard_map: dict[Player, list[Discard]]
    melds_by_player: dict[Player, list[Meld]]
    dora_indicator_tiles: tuple[int, ...]
    visible_summary: VisibleTileSummary
    hand_tiles: tuple[int, ...]
    hand_draw_tile: int | None
    hand_recommendation_panel: HandRecommendationPanelData
    player_score_diffs_by_seat: dict[int, int]
    player_names_by_seat: dict[int, str]
    round_events: tuple[object, ...]
    self_hand_value_alert: SelfHandValueAlertState


@dataclass(frozen=True)
class SidePanelRenderCache:
    signature: object
    player_panel_button_specs: tuple[PlayerPanelButtonSpec, ...] = ()
    lag_marker_reference_button_specs: tuple[LagMarkerReferenceButtonSpec, ...] = ()
    detail_images: tuple[ImageTk.PhotoImage, ...] = ()


@dataclass
class HandResponsePanelState:
    visible: bool = False
    betaori_visible: bool = False


@dataclass(frozen=True)
class HandAutoDiscardCandidate:
    """One current auto-discard candidate derived from the latest live pystyle result."""

    attempt_key: tuple[object, ...]
    tile_37: int
    hand_index: int | None = None
    tile_text: str = ""


@dataclass(frozen=True)
class SelfHandBridgeClickSpec:
    """Clickable self-hand tile bounds mapped to the currently displayed hand index."""

    rect: tuple[float, float, float, float]
    hand_index: int
    tile_37: int


@dataclass(frozen=True)
class BridgeActionControlSpec:
    """One classified bridge action button shown in the dedicated app-side action row."""

    control_id: int
    kind: str
    label: str


@dataclass(frozen=True)
class HandAutoModeState:
    """UI-facing state for the hand-side Auto mode toggle."""

    enabled: bool = False
    mode: str = HAND_AUTO_MODE_KIND_RECOMMENDATION
    in_flight: bool = False
    last_attempt_key: tuple[object, ...] | None = None
    last_error: str = ""


def _resolve_hand_response_panel_state_for_auto_mode(
    current_state: HandResponsePanelState | None,
    *,
    auto_mode_enabled: bool,
    auto_mode: str,
) -> HandResponsePanelState:
    """Keep AI TOP3 visible whenever recommendation auto mode is active."""

    visible = bool(getattr(current_state, "visible", False))
    betaori_visible = bool(getattr(current_state, "betaori_visible", False))
    if auto_mode_enabled and str(auto_mode) == HAND_AUTO_MODE_KIND_RECOMMENDATION:
        visible = True
    return HandResponsePanelState(visible=visible, betaori_visible=betaori_visible)


@dataclass(frozen=True)
class SelfHandValueAlertState:
    active: bool = False
    kind: str = HAND_SELF_ALERT_KIND_NONE
    round_token: str = ""
    label: str = "SELF"
    dot_color: str | None = None
    fill_color: str = HAND_SELF_ALERT_FILL
    outline_color: str = HAND_SELF_ALERT_OUTLINE
    text_color: str = HAND_SELF_ALERT_MUTED_TEXT
    adjusted_top_expected_value: float | None = None
    raw_top_expected_value: float | None = None


@dataclass(frozen=True)
class LayoutTuningSettings:
    """Persisted renderer tuning values used by the optional LAYOUT window."""

    horizontal_panel_width: int = 719
    horizontal_panel_height: int = 109
    vertical_panel_width: int = 138
    vertical_panel_height: int = 540
    detail_panel_width: int = DETAIL_PANEL_WIDTH
    detail_panel_gap: int = DETAIL_PANEL_GAP
    detail_panel_top: int = 40
    main_left_margin: int = 12
    panel_table_gap: int = 80
    side_panels_top: int = 64
    top_panel_top: int = 8
    right_panel_margin: int = 0
    bottom_panel_margin: int = 10
    hand_panel_gap: int = 12
    hand_bottom_margin: int = 18
    discard_tile_scale: float = 1.0
    top_bottom_discard_width: int = 180
    top_bottom_discard_height: int = 117
    side_discard_width: int = 90
    side_discard_height: int = 180
    meld_tile_scale: float = 0.7
    top_bottom_meld_height: int = 55
    side_meld_width: int = SIDE_MELD_MIN_WIDTH
    side_meld_height: int = 180
    top_meld_width: int = 900
    bottom_meld_width: int = 900
    panel_summary_top: int = 17
    top_summary_ratio: float = 0.62
    top_alert_ratio: float = 0.74
    side_summary_ratio: float = 0.56
    side_alert_ratio: float = 0.63
    panel_tile_rank_scale: float = 0.24
    top_tile_rank_row_gap: int = 0
    side_tile_rank_row_gap: int = 0
    hand_response_button_offset_x: int = 18
    hand_response_button_offset_y: int = 0
    component_offsets: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {
            "player_toimen": (-2, -3),
            "player_kamicha": (-6, 28),
            "player_shimocha": (3, 27),
            "discard_toimen": (0, 83),
            "discard_kamicha": (0, 83),
            "discard_shimocha": (0, 83),
            "discard_jicha": (0, 0),
            "meld_toimen": (3, 82),
            "meld_kamicha": (0, 83),
            "meld_shimocha": (0, 83),
            "meld_jicha": (0, 0),
        }
    )


_THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS: tkinter.Canvas | None = None
_INFERRED_VISIBLE_WORKER_STOP = object()
_SELECTED_INFERRED_VISIBLE_POPUP_ENTRY_KIND = "selected_inferred_visible_popup"
_ALERT_AUDIO_REFRESH_TOKEN_UNSET = object()
_HAND_RESPONSE_UI_TAG = "hand_response_ui"
_LIVE_BACKGROUND_TAG = "live_background"
_LIVE_FRAME_TAG = "live_frame"
_LIVE_ASYNC_SIDE_PANEL_TAG = "live_async_side_panels"
_LIVE_ASYNC_DISCARD_TAG = "live_async_discards"
_LIVE_DETAIL_OVERLAY_TAG = "live_detail_overlays"
_LIVE_ASYNC_HAND_TAG = "live_async_hand"
_LIVE_LAYOUT_DRAG_TAG = "live_layout_drag"
_THREAD_ACTIVITY_NOTICE_TAG = "thread_activity_notice"


@dataclass(frozen=True)
class LayoutTuningControlSpec:
    field_name: str
    label: str
    min_value: float
    max_value: float
    resolution: float


@dataclass(frozen=True)
class LayoutComponentDefinition:
    key: str
    label: str


@dataclass(frozen=True)
class LayoutDragSpec:
    key: str
    label: str
    rect: tuple[float, float, float, float]
    drag_kind: str = "component"
    field_names: tuple[str, str] | None = None


@dataclass
class LayoutDragState:
    spec: LayoutDragSpec
    start_pointer: tuple[float, float]
    start_offset: tuple[int, int]


LAYOUT_TUNING_WINDOW_COLUMN_COUNT = 2
LAYOUT_BUTTON_X = 8
LAYOUT_BUTTON_Y = 8
TABLE_SITUATION_VISIBILITY_BUTTON_X = 8
TABLE_SITUATION_VISIBILITY_BUTTON_Y = 36
FORCE_CAPTURE_REINIT_BUTTON_X = 8
FORCE_CAPTURE_REINIT_BUTTON_Y = 64
PYSTYLE_AUTO_BUTTON_X = 82
PYSTYLE_AUTO_BUTTON_Y = 8
BETAORI_AUTO_BUTTON_X = 82
BETAORI_AUTO_BUTTON_Y = 36
BRIDGE_TOGGLE_CONTROLS_MARGIN_RIGHT = 14
BRIDGE_TOGGLE_CONTROLS_MARGIN_BOTTOM = 12
BRIDGE_ACTION_CONTROLS_MARGIN_ABOVE_HAND = 10
BRIDGE_ACTION_CONTROLS_SIDE_MARGIN = 12
LAYOUT_TUNING_SCHEMA_VERSION = 2

LAYOUT_TUNING_CONTROL_SPECS: tuple[LayoutTuningControlSpec, ...] = (
    LayoutTuningControlSpec("horizontal_panel_width", "Top/Bottom panel width", 380, 900, 1),
    LayoutTuningControlSpec("horizontal_panel_height", "Top/Bottom panel height", 68, 180, 1),
    LayoutTuningControlSpec("vertical_panel_width", "Side panel width", 92, 220, 1),
    LayoutTuningControlSpec("vertical_panel_height", "Side panel height", 320, 700, 1),
    LayoutTuningControlSpec("detail_panel_width", "Detail panel width", 168, 360, 1),
    LayoutTuningControlSpec("detail_panel_gap", "Detail panel gap", 8, 80, 1),
    LayoutTuningControlSpec("detail_panel_top", "Detail panel top", 20, 140, 1),
    LayoutTuningControlSpec("main_left_margin", "Main left margin", 4, 80, 1),
    LayoutTuningControlSpec("panel_table_gap", "Panel-table gap", 0, 80, 1),
    LayoutTuningControlSpec("side_panels_top", "Side panels top", 40, 160, 1),
    LayoutTuningControlSpec("top_panel_top", "Top panel top", 0, 80, 1),
    LayoutTuningControlSpec("right_panel_margin", "Right panel margin", 0, 80, 1),
    LayoutTuningControlSpec("bottom_panel_margin", "Bottom panel margin", 0, 60, 1),
    LayoutTuningControlSpec("hand_panel_gap", "Hand-panel gap", 0, 60, 1),
    LayoutTuningControlSpec("hand_bottom_margin", "Hand bottom margin", 0, 60, 1),
    LayoutTuningControlSpec("discard_tile_scale", "Discard tile scale", 0.7, 1.8, 0.05),
    LayoutTuningControlSpec("top_bottom_discard_width", "Top/Bottom discard width", 180, 420, 1),
    LayoutTuningControlSpec("top_bottom_discard_height", "Top/Bottom discard height", 117, 260, 1),
    LayoutTuningControlSpec("side_discard_width", "Side discard width", 90, 240, 1),
    LayoutTuningControlSpec("side_discard_height", "Side discard height", 180, 480, 1),
    LayoutTuningControlSpec("meld_tile_scale", "Meld tile scale", 0.7, 1.8, 0.05),
    LayoutTuningControlSpec("top_bottom_meld_height", "Top/Bottom meld height", 48, 140, 1),
    LayoutTuningControlSpec("side_meld_width", "Side meld width", 48, 220, 1),
    LayoutTuningControlSpec("side_meld_height", "Side meld height", 96, 480, 1),
    LayoutTuningControlSpec("top_meld_width", "Toimen meld width", 60, 900, 1),
    LayoutTuningControlSpec("bottom_meld_width", "Self meld width", 60, 900, 1),
    LayoutTuningControlSpec("panel_summary_top", "Panel summary top", 12, 40, 1),
    LayoutTuningControlSpec("top_summary_ratio", "Top summary ratio", 0.45, 0.82, 0.01),
    LayoutTuningControlSpec("top_alert_ratio", "Top alert ratio", 0.58, 0.92, 0.01),
    LayoutTuningControlSpec("side_summary_ratio", "Side summary ratio", 0.40, 0.76, 0.01),
    LayoutTuningControlSpec("side_alert_ratio", "Side alert ratio", 0.52, 0.88, 0.01),
    LayoutTuningControlSpec("panel_tile_rank_scale", "Panel tile-rank scale", 0.16, 0.40, 0.01),
    LayoutTuningControlSpec("top_tile_rank_row_gap", "Top tile-rank extra gap", 0, 18, 1),
    LayoutTuningControlSpec("side_tile_rank_row_gap", "Side tile-rank extra gap", 0, 24, 1),
    LayoutTuningControlSpec("hand_response_button_offset_x", "AI TOP3 X", -180, 240, 1),
    LayoutTuningControlSpec("hand_response_button_offset_y", "AI TOP3 Y", -120, 120, 1),
)

LAYOUT_TUNING_HIDDEN_FIELDS = frozenset(
    {
        "hand_response_button_offset_x",
        "hand_response_button_offset_y",
    }
)
LAYOUT_TUNING_CONTROLS: tuple[LayoutTuningControlSpec, ...] = tuple(
    control
    for control in LAYOUT_TUNING_CONTROL_SPECS
    if control.field_name not in LAYOUT_TUNING_HIDDEN_FIELDS
)
LAYOUT_TUNING_CONTROL_BY_FIELD = {
    control.field_name: control
    for control in LAYOUT_TUNING_CONTROL_SPECS
}

LAYOUT_COMPONENT_DEFINITIONS: tuple[LayoutComponentDefinition, ...] = (
    LayoutComponentDefinition("player_toimen", "PANEL TOIMEN"),
    LayoutComponentDefinition("player_kamicha", "PANEL KAMI"),
    LayoutComponentDefinition("player_shimocha", "PANEL SHIMO"),
    LayoutComponentDefinition("discard_toimen", "DISCARD TOIMEN"),
    LayoutComponentDefinition("discard_kamicha", "DISCARD KAMI"),
    LayoutComponentDefinition("discard_shimocha", "DISCARD SHIMO"),
    LayoutComponentDefinition("discard_jicha", "DISCARD YOU"),
    LayoutComponentDefinition("meld_toimen", "MELD TOIMEN"),
    LayoutComponentDefinition("meld_kamicha", "MELD KAMI"),
    LayoutComponentDefinition("meld_shimocha", "MELD SHIMO"),
    LayoutComponentDefinition("meld_jicha", "MELD YOU"),
)
def _layout_tuning_settings_path() -> Path:
    """Return the JSON path used by the LAYOUT tuning window."""

    return Path(__file__).resolve().parents[2] / "csv_db" / "ui_layout_tuning.json"


def _normalize_component_offsets(
    raw_offsets: object,
) -> dict[str, tuple[int, int]]:
    """Clamp per-component drag offsets into the supported preview range."""

    if isinstance(raw_offsets, Mapping):
        raw_values = raw_offsets
    else:
        raw_values = {}

    normalized: dict[str, tuple[int, int]] = {}
    for definition in LAYOUT_COMPONENT_DEFINITIONS:
        raw_offset = raw_values.get(definition.key, (0, 0))
        raw_dx: object = 0
        raw_dy: object = 0
        if isinstance(raw_offset, Mapping):
            raw_dx = raw_offset.get("dx", raw_offset.get("x", 0))
            raw_dy = raw_offset.get("dy", raw_offset.get("y", 0))
        elif (
            isinstance(raw_offset, Sequence)
            and not isinstance(raw_offset, (str, bytes))
            and len(raw_offset) >= 2
        ):
            raw_dx = raw_offset[0]
            raw_dy = raw_offset[1]
        try:
            dx = int(round(float(raw_dx)))
        except (TypeError, ValueError):
            dx = 0
        try:
            dy = int(round(float(raw_dy)))
        except (TypeError, ValueError):
            dy = 0
        normalized[definition.key] = (
            max(-LAYOUT_COMPONENT_OFFSET_LIMIT, min(LAYOUT_COMPONENT_OFFSET_LIMIT, dx)),
            max(-LAYOUT_COMPONENT_OFFSET_LIMIT, min(LAYOUT_COMPONENT_OFFSET_LIMIT, dy)),
        )
    return normalized


def _normalize_layout_tuning_settings(
    raw_settings: LayoutTuningSettings | Mapping[str, object] | None,
) -> LayoutTuningSettings:
    """Clamp external tuning data into the renderer's supported control ranges."""

    defaults = LayoutTuningSettings()
    default_values = asdict(defaults)
    if isinstance(raw_settings, LayoutTuningSettings):
        raw_values = asdict(raw_settings)
    elif isinstance(raw_settings, Mapping):
        raw_values = dict(raw_settings)
    else:
        raw_values = {}

    legacy_field_aliases = {
        "side_meld_width": ("side_meld_min_width",),
    }
    normalized: dict[str, int | float] = {}
    component_offsets = _normalize_component_offsets(raw_values.get("component_offsets", {}))
    for field in fields(LayoutTuningSettings):
        field_name = field.name
        if field_name == "component_offsets":
            continue
        control = LAYOUT_TUNING_CONTROL_BY_FIELD[field_name]
        default_value = default_values[field_name]
        raw_value = raw_values.get(field_name, default_value)
        if raw_value == default_value:
            for alias in legacy_field_aliases.get(field_name, ()):
                if alias in raw_values:
                    raw_value = raw_values[alias]
                    break
        try:
            numeric_value = float(raw_value)
        except (TypeError, ValueError):
            numeric_value = float(default_value)
        try:
            min_value = float(control.min_value)
        except (TypeError, ValueError):
            min_value = None
        try:
            max_value = float(control.max_value)
        except (TypeError, ValueError):
            max_value = None
        if min_value is not None:
            numeric_value = max(min_value, numeric_value)
        if max_value is not None:
            numeric_value = min(max_value, numeric_value)
        if isinstance(default_value, int):
            try:
                normalized[field_name] = int(round(numeric_value))
            except (TypeError, ValueError):
                normalized[field_name] = int(default_value)
        else:
            try:
                normalized[field_name] = round(float(numeric_value), 3)
            except (TypeError, ValueError):
                normalized[field_name] = round(float(default_value), 3)

    normalized["top_alert_ratio"] = round(
        max(
            float(normalized["top_summary_ratio"]) + 0.04,
            float(normalized["top_alert_ratio"]),
        ),
        3,
    )
    normalized["side_alert_ratio"] = round(
        max(
            float(normalized["side_summary_ratio"]) + 0.04,
            float(normalized["side_alert_ratio"]),
        ),
        3,
    )
    normalized["top_alert_ratio"] = min(
        LAYOUT_TUNING_CONTROL_BY_FIELD["top_alert_ratio"].max_value,
        float(normalized["top_alert_ratio"]),
    )
    normalized["side_alert_ratio"] = min(
        LAYOUT_TUNING_CONTROL_BY_FIELD["side_alert_ratio"].max_value,
        float(normalized["side_alert_ratio"]),
    )
    normalized["component_offsets"] = component_offsets
    return LayoutTuningSettings(**normalized)


def _load_layout_tuning_settings() -> LayoutTuningSettings:
    """Load persisted tuning JSON and fall back to safe defaults on any failure."""

    settings_path = _layout_tuning_settings_path()
    try:
        raw_json = json.loads(settings_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return LayoutTuningSettings()
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return LayoutTuningSettings()
    return _normalize_layout_tuning_settings(raw_json)


def _save_layout_tuning_settings(settings: LayoutTuningSettings) -> None:
    """Persist the current tuning snapshot as JSON."""

    settings_path = _layout_tuning_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_settings = {
        "layout_schema_version": LAYOUT_TUNING_SCHEMA_VERSION,
        **asdict(_normalize_layout_tuning_settings(settings)),
    }
    settings_path.write_text(
        json.dumps(serialized_settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _current_layout_tuning(canvas: tkinter.Canvas) -> LayoutTuningSettings:
    """Return the canvas-local tuning snapshot in normalized form."""

    return _normalize_layout_tuning_settings(getattr(canvas, "layout_tuning_settings", None))


def _set_layout_tuning_status(
    canvas: tkinter.Canvas,
    text: str,
    color: str,
) -> None:
    """Update the non-modal LAYOUT window status label when it is open."""

    status_label = getattr(canvas, "layout_tuning_status_label", None)
    if status_label is not None and status_label.winfo_exists():
        status_label.configure(text=text, fg=color)


def _canvas_board_rect(
    canvas: tkinter.Canvas,
) -> tuple[int, int, tuple[float, float, float, float]]:
    """Return the current canvas size and the board rectangle used by `_render_table`."""

    width = max(canvas.winfo_width(), WINDOW_MIN_WIDTH)
    height = max(canvas.winfo_height(), WINDOW_MIN_HEIGHT)
    outer_margin = max(14, min(width, height) // 30)
    return (
        width,
        height,
        (
            outer_margin,
            outer_margin,
            width - outer_margin,
            height - outer_margin,
        ),
    )


def _build_layout_signature(
    canvas: tkinter.Canvas,
    *,
    ui_scale: float,
    layout_tuning: LayoutTuningSettings | Mapping[str, object] | None = None,
) -> tuple[int, int, float, LayoutTuningSettings]:
    """Return the geometry/tuning signature that decides whether cached layout is reusable."""

    width, height, _board_rect = _canvas_board_rect(canvas)
    return (
        int(width),
        int(height),
        round(float(ui_scale), 3),
        _normalize_layout_tuning_settings(layout_tuning),
    )


def _format_layout_signature_delta(
    previous_signature: object,
    current_signature: object,
) -> str:
    """Return a compact description of why the cached layout signature no longer matches."""

    if not (
        isinstance(previous_signature, tuple)
        and isinstance(current_signature, tuple)
        and len(previous_signature) == 4
        and len(current_signature) == 4
    ):
        return "layout_signature_changed"
    previous_width, previous_height, previous_scale, previous_tuning = previous_signature
    current_width, current_height, current_scale, current_tuning = current_signature
    parts: list[str] = []
    if previous_width != current_width:
        parts.append(f"width={previous_width}->{current_width}")
    if previous_height != current_height:
        parts.append(f"height={previous_height}->{current_height}")
    if previous_scale != current_scale:
        parts.append(f"ui_scale={previous_scale}->{current_scale}")
    if previous_tuning != current_tuning:
        parts.append("layout_tuning_changed")
    if not parts:
        parts.append("layout_signature_changed")
    return ", ".join(parts)


def _cached_layout_skip_reason(
    canvas: tkinter.Canvas,
    current_layout_signature: object,
) -> str | None:
    """Return why cached-layout redraw is unavailable, or None when reuse should be attempted."""

    if _inferred_visible_runtime_enabled(canvas):
        return "inferred_visible_runtime_enabled"
    if bool(getattr(canvas, "layout_drag_enabled", False)):
        return "layout_drag_enabled"
    previous_layout_signature = getattr(canvas, "last_render_layout_signature", None)
    if previous_layout_signature != current_layout_signature:
        return _format_layout_signature_delta(previous_layout_signature, current_layout_signature)
    layout = getattr(canvas, "last_render_layout", None)
    if not isinstance(layout, Mapping):
        return "missing_cached_layout"
    detail_content_rect = layout.get("detail_content_rect")
    hand_rect = layout.get("hand_rect")
    if (
        not isinstance(detail_content_rect, tuple)
        or len(detail_content_rect) != 4
        or not isinstance(hand_rect, tuple)
        or len(hand_rect) != 4
    ):
        return "cached_layout_missing_rects"
    return None


def _cached_layout_runtime_guard_reason(canvas: tkinter.Canvas) -> str | None:
    """Return late guard failures that can still trip after the caller pre-check passes."""

    if not bool(getattr(canvas, "winfo_exists", lambda: False)()):
        return "canvas_destroyed"
    if _inferred_visible_runtime_enabled(canvas):
        return "inferred_visible_runtime_enabled"
    if bool(getattr(canvas, "layout_drag_enabled", False)):
        return "layout_drag_enabled"
    layout = getattr(canvas, "last_render_layout", None)
    if not isinstance(layout, Mapping):
        return "missing_cached_layout"
    detail_content_rect = layout.get("detail_content_rect")
    hand_rect = layout.get("hand_rect")
    if (
        not isinstance(detail_content_rect, tuple)
        or len(detail_content_rect) != 4
        or not isinstance(hand_rect, tuple)
        or len(hand_rect) != 4
    ):
        return "cached_layout_missing_rects"
    return None


def _log_full_redraw_reason(canvas: tkinter.Canvas, reason: str) -> None:
    """Print one one-line reason when the redraw path falls back to a full canvas refresh."""

    normalized_reason = str(reason or "").strip() or "unknown"
    refresh_token = getattr(canvas, "current_refresh_token", None)
    reason_key = (refresh_token, normalized_reason)
    if getattr(canvas, "last_full_redraw_notice_key", None) == reason_key:
        return
    canvas.last_full_redraw_notice_key = reason_key
    print(f"UI full redraw: reason={normalized_reason} refresh_token={refresh_token}")


def _mark_ui_refresh_completed(
    canvas: tkinter.Canvas,
    *,
    refresh_token: object | None = None,
    completed_monotonic_s: float | None = None,
) -> None:
    """Remember the latest refresh token that successfully reached the visible UI."""

    resolved_refresh_token = (
        refresh_token
        if refresh_token is not None
        else getattr(canvas, "current_refresh_token", None)
    )
    resolved_monotonic = (
        float(completed_monotonic_s)
        if completed_monotonic_s is not None
        else time.monotonic()
    )
    canvas.last_completed_redraw_refresh_token = resolved_refresh_token
    canvas.last_completed_redraw_monotonic_s = resolved_monotonic
    canvas.last_redraw_finished_monotonic_s = resolved_monotonic
    canvas.uncompleted_refresh_token_started_monotonic_s = 0.0


def _force_manual_ui_reinit(
    canvas: tkinter.Canvas,
    *,
    request_redraw: Callable[..., None] | None,
    table_snapshot_reinit_action: Callable[[], object | None] | None = None,
) -> str:
    """Reset redraw/UI caches and force one live refresh from the current local state."""

    reasons: list[str] = []
    if callable(table_snapshot_reinit_action):
        next_refresh_token = table_snapshot_reinit_action()
        reasons.append("snapshot_cache_invalidated")
        if next_refresh_token is not None:
            canvas.current_refresh_token = next_refresh_token
            canvas.last_refresh_token_change_monotonic_s = time.monotonic()
            reasons.append("refresh_token_updated")
    if bool(getattr(canvas, "redraw_in_progress", False)):
        canvas.redraw_in_progress = False
        canvas.last_redraw_started_monotonic_s = 0.0
        reasons.append("cleared_redraw_in_progress")
    if bool(getattr(canvas, "redraw_request_pending", False)):
        canvas.redraw_request_pending = False
        canvas.last_redraw_request_monotonic_s = 0.0
        reasons.append("cleared_pending_redraw_request")
    canvas.live_async_render_state = None
    canvas.last_render_layout = None
    canvas.last_render_layout_signature = None
    canvas.last_render_detail_content_rect = None
    canvas.side_panel_render_cache = None
    reasons.append("cleared_ui_render_cache")
    if callable(request_redraw):
        request_redraw(replace_pending=True)
    return ",".join(reasons)


def _log_manual_ui_reinit(canvas: tkinter.Canvas, reason: str) -> None:
    """Print one one-line notice when the operator manually forces a UI REINIT."""

    normalized_reason = str(reason or "").strip() or "manual_reinit_requested"
    current_refresh_token = getattr(canvas, "current_refresh_token", None)
    last_completed_refresh_token = getattr(canvas, "last_completed_redraw_refresh_token", None)
    print(
        "UI REINIT forced manually: "
        f"reason={normalized_reason} "
        f"current_refresh_token={current_refresh_token} "
        f"last_completed_refresh_token={last_completed_refresh_token}"
    )


def _resolve_auto_ui_reinit_stall(
    canvas: tkinter.Canvas,
    *,
    now_monotonic: float,
) -> tuple[str, float] | None:
    """Return one stalled-redraw reason and age when auto REINIT should be considered."""

    if bool(getattr(canvas, "redraw_in_progress", False)):
        redraw_started = float(getattr(canvas, "last_redraw_started_monotonic_s", 0.0) or 0.0)
        if redraw_started > 0.0:
            stalled_for_s = max(0.0, now_monotonic - redraw_started)
            if stalled_for_s >= UI_AUTO_REINIT_STALL_THRESHOLD_S:
                return "redraw_in_progress_stalled", stalled_for_s
    if bool(getattr(canvas, "redraw_request_pending", False)):
        redraw_requested = float(getattr(canvas, "last_redraw_request_monotonic_s", 0.0) or 0.0)
        if redraw_requested > 0.0:
            stalled_for_s = max(0.0, now_monotonic - redraw_requested)
            if stalled_for_s >= UI_AUTO_REINIT_STALL_THRESHOLD_S:
                return "redraw_request_pending_stalled", stalled_for_s
    current_refresh_token = getattr(canvas, "current_refresh_token", None)
    last_completed_refresh_token = getattr(canvas, "last_completed_redraw_refresh_token", None)
    if current_refresh_token != last_completed_refresh_token:
        uncompleted_since = float(
            getattr(canvas, "uncompleted_refresh_token_started_monotonic_s", 0.0)
            or 0.0
        )
        if uncompleted_since <= 0.0:
            canvas.uncompleted_refresh_token_started_monotonic_s = now_monotonic
            return None
        stalled_for_s = max(0.0, now_monotonic - uncompleted_since)
        if stalled_for_s >= UI_AUTO_REINIT_STALL_THRESHOLD_S:
            return "refresh_token_stalled", stalled_for_s
    else:
        canvas.uncompleted_refresh_token_started_monotonic_s = 0.0
    return None


def _resolve_redraw_watchdog_thread_stall(
    canvas: tkinter.Canvas,
    *,
    now_monotonic: float,
) -> tuple[str, float] | None:
    """Read-only stall detector for the background watchdog thread."""

    if bool(getattr(canvas, "redraw_in_progress", False)):
        redraw_started = float(getattr(canvas, "last_redraw_started_monotonic_s", 0.0) or 0.0)
        if redraw_started > 0.0:
            stalled_for_s = max(0.0, now_monotonic - redraw_started)
            if stalled_for_s >= UI_AUTO_REINIT_STALL_THRESHOLD_S:
                return "thread_redraw_in_progress_stalled", stalled_for_s
    if bool(getattr(canvas, "redraw_request_pending", False)):
        redraw_requested = float(getattr(canvas, "last_redraw_request_monotonic_s", 0.0) or 0.0)
        if redraw_requested > 0.0:
            stalled_for_s = max(0.0, now_monotonic - redraw_requested)
            if stalled_for_s >= UI_AUTO_REINIT_STALL_THRESHOLD_S:
                return "thread_redraw_request_pending_stalled", stalled_for_s
    current_refresh_token = getattr(canvas, "current_refresh_token", None)
    last_completed_refresh_token = getattr(canvas, "last_completed_redraw_refresh_token", None)
    uncompleted_since = float(
        getattr(canvas, "uncompleted_refresh_token_started_monotonic_s", 0.0)
        or 0.0
    )
    if current_refresh_token != last_completed_refresh_token and uncompleted_since > 0.0:
        stalled_for_s = max(0.0, now_monotonic - uncompleted_since)
        if stalled_for_s >= UI_AUTO_REINIT_STALL_THRESHOLD_S:
            return "thread_refresh_token_stalled", stalled_for_s
    return None


def _redraw_watchdog_thread_worker(
    canvas: tkinter.Canvas,
    result_queue: queue.Queue[dict[str, object]],
    stop_event: threading.Event,
) -> None:
    """Monitor redraw state from a background thread and queue recovery requests."""

    last_request_monotonic_s = 0.0
    while not stop_event.wait(UI_REDRAW_WATCHDOG_THREAD_POLL_S):
        now_monotonic = time.monotonic()
        if (
            last_request_monotonic_s > 0.0
            and (now_monotonic - last_request_monotonic_s) < UI_AUTO_REINIT_COOLDOWN_S
        ):
            continue
        stalled = _resolve_redraw_watchdog_thread_stall(
            canvas,
            now_monotonic=now_monotonic,
        )
        if stalled is None:
            continue
        try:
            if result_queue.qsize() > 0:
                continue
        except NotImplementedError:
            pass
        stall_reason, stalled_for_s = stalled
        result_queue.put(
            {
                "kind": "auto_reinit",
                "reason": stall_reason,
                "stalled_for_s": stalled_for_s,
                "requested_monotonic_s": now_monotonic,
            }
        )
        last_request_monotonic_s = now_monotonic


def _start_redraw_watchdog_thread(canvas: tkinter.Canvas) -> None:
    """Start the background redraw watchdog once for this canvas."""

    existing_thread = getattr(canvas, "redraw_watchdog_thread", None)
    if isinstance(existing_thread, threading.Thread) and existing_thread.is_alive():
        return
    result_queue = getattr(canvas, "redraw_watchdog_result_queue", None)
    if result_queue is None:
        result_queue = queue.Queue()
        canvas.redraw_watchdog_result_queue = result_queue
    stop_event = getattr(canvas, "redraw_watchdog_stop_event", None)
    if not isinstance(stop_event, threading.Event):
        stop_event = threading.Event()
        canvas.redraw_watchdog_stop_event = stop_event
    else:
        stop_event.clear()
    watchdog_thread = threading.Thread(
        target=_redraw_watchdog_thread_worker,
        args=(canvas, result_queue, stop_event),
        name="ui-redraw-watchdog",
        daemon=True,
    )
    canvas.redraw_watchdog_thread = watchdog_thread
    watchdog_thread.start()


def _drain_redraw_watchdog_result_queue(
    canvas: tkinter.Canvas,
    *,
    now_monotonic: float,
    request_redraw: Callable[..., None] | None,
    table_snapshot_reinit_action: Callable[[], object | None] | None = None,
) -> bool:
    """Apply queued watchdog recovery requests on the Tk thread."""

    result_queue = getattr(canvas, "redraw_watchdog_result_queue", None)
    if result_queue is None:
        return False
    changed = False
    while True:
        try:
            payload = result_queue.get_nowait()
        except queue.Empty:
            break
        if not isinstance(payload, Mapping):
            continue
        if str(payload.get("kind", "") or "") != "auto_reinit":
            continue
        try:
            stalled_for_s = float(payload.get("stalled_for_s", 0.0) or 0.0)
        except (TypeError, ValueError):
            stalled_for_s = 0.0
        last_auto_reinit = float(getattr(canvas, "last_auto_reinit_monotonic_s", 0.0) or 0.0)
        if last_auto_reinit > 0.0 and (now_monotonic - last_auto_reinit) < UI_AUTO_REINIT_COOLDOWN_S:
            continue
        force_reason = _force_manual_ui_reinit(
            canvas,
            request_redraw=request_redraw,
            table_snapshot_reinit_action=table_snapshot_reinit_action,
        )
        stall_reason = str(payload.get("reason", "") or "thread_redraw_stalled")
        combined_reason = f"auto_{stall_reason}"
        if force_reason:
            combined_reason = f"{combined_reason},{force_reason}"
        canvas.last_auto_reinit_monotonic_s = now_monotonic
        canvas.last_auto_reinit_reason = combined_reason
        _log_auto_ui_reinit(
            canvas,
            combined_reason,
            stalled_for_s=stalled_for_s,
        )
        changed = True
    return changed


def _log_auto_ui_reinit(
    canvas: tkinter.Canvas,
    reason: str,
    *,
    stalled_for_s: float,
) -> None:
    """Print one one-line notice when redraw watchdog auto-forces a UI REINIT."""

    normalized_reason = str(reason or "").strip() or "auto_reinit_requested"
    current_refresh_token = getattr(canvas, "current_refresh_token", None)
    last_completed_refresh_token = getattr(canvas, "last_completed_redraw_refresh_token", None)
    print(
        "UI REINIT forced automatically: "
        f"reason={normalized_reason} "
        f"stalled_for={max(0.0, float(stalled_for_s)):.1f}s "
        f"current_refresh_token={current_refresh_token} "
        f"last_completed_refresh_token={last_completed_refresh_token}"
    )


def _maybe_auto_force_ui_reinit(
    canvas: tkinter.Canvas,
    *,
    now_monotonic: float,
    request_redraw: Callable[..., None] | None,
    table_snapshot_reinit_action: Callable[[], object | None] | None = None,
) -> str | None:
    """Force the same REINIT path as the button when redraw state stays stale too long."""

    last_auto_reinit = float(getattr(canvas, "last_auto_reinit_monotonic_s", 0.0) or 0.0)
    if last_auto_reinit > 0.0 and (now_monotonic - last_auto_reinit) < UI_AUTO_REINIT_COOLDOWN_S:
        return None
    stalled = _resolve_auto_ui_reinit_stall(
        canvas,
        now_monotonic=now_monotonic,
    )
    if stalled is None:
        return None
    stall_reason, stalled_for_s = stalled
    force_reason = _force_manual_ui_reinit(
        canvas,
        request_redraw=request_redraw,
        table_snapshot_reinit_action=table_snapshot_reinit_action,
    )
    combined_reason = f"auto_{stall_reason}"
    if force_reason:
        combined_reason = f"{combined_reason},{force_reason}"
    canvas.last_auto_reinit_monotonic_s = now_monotonic
    canvas.last_auto_reinit_reason = combined_reason
    _log_auto_ui_reinit(
        canvas,
        combined_reason,
        stalled_for_s=stalled_for_s,
    )
    return combined_reason


def _rect_has_area(rect: tuple[float, float, float, float]) -> bool:
    """Return True when one axis-aligned rectangle has positive area."""

    return rect[2] > rect[0] and rect[3] > rect[1]


def _translate_rect(
    rect: tuple[float, float, float, float],
    dx: float,
    dy: float,
) -> tuple[float, float, float, float]:
    """Translate one rectangle by the given deltas."""

    return (rect[0] + dx, rect[1] + dy, rect[2] + dx, rect[3] + dy)


def _ranges_overlap(
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float,
) -> bool:
    """Return True when two 1D closed-open spans overlap."""

    return start_a < end_b and end_a > start_b


def _clamp_layout_component_translation(
    base_rect: tuple[float, float, float, float],
    desired_dx: float,
    desired_dy: float,
    board_rect: tuple[float, float, float, float],
    blockers: Sequence[tuple[float, float, float, float]],
) -> tuple[float, float]:
    """Clamp one draggable component translation to board bounds and blocker rectangles."""

    if not _rect_has_area(base_rect):
        return 0.0, 0.0

    min_dx = board_rect[0] - base_rect[0]
    max_dx = board_rect[2] - base_rect[2]
    min_dy = board_rect[1] - base_rect[1]
    max_dy = board_rect[3] - base_rect[3]
    clamped_dy = max(min_dy, min(max_dy, desired_dy))

    candidate_top = base_rect[1] + clamped_dy
    candidate_bottom = base_rect[3] + clamped_dy
    if desired_dx > 0:
        for blocker in blockers:
            if not _rect_has_area(blocker):
                continue
            if blocker[0] < base_rect[2]:
                continue
            if not _ranges_overlap(candidate_top, candidate_bottom, blocker[1], blocker[3]):
                continue
            max_dx = min(max_dx, blocker[0] - base_rect[2])
    elif desired_dx < 0:
        for blocker in blockers:
            if not _rect_has_area(blocker):
                continue
            if blocker[2] > base_rect[0]:
                continue
            if not _ranges_overlap(candidate_top, candidate_bottom, blocker[1], blocker[3]):
                continue
            min_dx = max(min_dx, blocker[2] - base_rect[0])
    clamped_dx = max(min_dx, min(max_dx, desired_dx))

    candidate_left = base_rect[0] + clamped_dx
    candidate_right = base_rect[2] + clamped_dx
    if desired_dy > 0:
        for blocker in blockers:
            if not _rect_has_area(blocker):
                continue
            if blocker[1] < base_rect[3]:
                continue
            if not _ranges_overlap(candidate_left, candidate_right, blocker[0], blocker[2]):
                continue
            max_dy = min(max_dy, blocker[1] - base_rect[3])
    elif desired_dy < 0:
        for blocker in blockers:
            if not _rect_has_area(blocker):
                continue
            if blocker[3] > base_rect[1]:
                continue
            if not _ranges_overlap(candidate_left, candidate_right, blocker[0], blocker[2]):
                continue
            min_dy = max(min_dy, blocker[3] - base_rect[1])
    clamped_dy = max(min_dy, min(max_dy, desired_dy))
    return clamped_dx, clamped_dy


def _resolve_layout_component_rects(
    base_component_rects: Mapping[str, tuple[float, float, float, float]],
    component_offsets: Mapping[str, tuple[int, int]] | None,
    board_rect: tuple[float, float, float, float],
    fixed_blockers: Sequence[tuple[float, float, float, float]],
) -> tuple[dict[str, tuple[float, float, float, float]], dict[str, tuple[int, int]]]:
    """Resolve draggable component rectangles while keeping them inside the board and non-overlapping."""

    desired_offsets = _normalize_component_offsets(component_offsets)
    anticipated_rects: dict[str, tuple[float, float, float, float]] = {}
    for definition in LAYOUT_COMPONENT_DEFINITIONS:
        base_rect = base_component_rects.get(definition.key)
        if base_rect is None or not _rect_has_area(base_rect):
            continue
        desired_dx, desired_dy = desired_offsets[definition.key]
        actual_dx, actual_dy = _clamp_layout_component_translation(
            base_rect,
            desired_dx,
            desired_dy,
            board_rect,
            (),
        )
        anticipated_rects[definition.key] = _translate_rect(base_rect, actual_dx, actual_dy)

    resolved_rects: dict[str, tuple[float, float, float, float]] = {}
    for index, definition in enumerate(LAYOUT_COMPONENT_DEFINITIONS):
        base_rect = base_component_rects.get(definition.key)
        if base_rect is None or not _rect_has_area(base_rect):
            continue
        desired_dx, desired_dy = desired_offsets[definition.key]
        blockers = [
            blocker
            for blocker in fixed_blockers
            if _rect_has_area(blocker)
        ]
        blockers.extend(
            rect
            for rect in resolved_rects.values()
            if _rect_has_area(rect)
        )
        blockers.extend(
            anticipated_rects[remaining_definition.key]
            for remaining_definition in LAYOUT_COMPONENT_DEFINITIONS[index + 1 :]
            if remaining_definition.key in anticipated_rects
            and _rect_has_area(anticipated_rects[remaining_definition.key])
        )
        actual_dx, actual_dy = _clamp_layout_component_translation(
            base_rect,
            desired_dx,
            desired_dy,
            board_rect,
            blockers,
        )
        resolved_rects[definition.key] = _translate_rect(base_rect, actual_dx, actual_dy)

    resolved_offsets = {
        key: (
            int(round(rect[0] - base_component_rects[key][0])),
            int(round(rect[1] - base_component_rects[key][1])),
        )
        for key, rect in resolved_rects.items()
    }
    return resolved_rects, resolved_offsets


def _draw_layout_drag_overlays(
    canvas: tkinter.Canvas,
    layout: Mapping[str, object],
) -> None:
    """Draw draggable outlines and labels over movable components while LAYOUT mode is open."""

    drag_specs: list[LayoutDragSpec] = []
    active_state = getattr(canvas, "layout_drag_state", None)
    active_key = active_state.spec.key if isinstance(active_state, LayoutDragState) else None
    for definition in LAYOUT_COMPONENT_DEFINITIONS:
        rect = layout.get("drag_components", {}).get(definition.key)
        if rect is None or not _rect_has_area(rect):
            continue
        drag_specs.append(
            LayoutDragSpec(
                key=definition.key,
                label=definition.label,
                rect=rect,
            )
        )
        outline = LAYOUT_DRAG_ACTIVE_OUTLINE if definition.key == active_key else LAYOUT_DRAG_OUTLINE
        width = 2 if definition.key == active_key else 1
        canvas.create_rectangle(
            rect[0],
            rect[1],
            rect[2],
            rect[3],
            outline=outline,
            dash=LAYOUT_DRAG_DASH,
            width=width,
        )
        label_x = rect[0] + LAYOUT_DRAG_LABEL_MARGIN
        label_y = rect[1] + LAYOUT_DRAG_LABEL_MARGIN
        text_id = canvas.create_text(
            label_x,
            label_y,
            text=definition.label,
            anchor=tkinter.NW,
            fill=LAYOUT_DRAG_LABEL_TEXT,
            font=LAYOUT_DRAG_LABEL_FONT,
        )
        text_bounds = canvas.bbox(text_id)
        if text_bounds is not None:
            canvas.create_rectangle(
                text_bounds[0] - 2,
                text_bounds[1] - 1,
                text_bounds[2] + 2,
                text_bounds[3] + 1,
                fill=LAYOUT_DRAG_LABEL_FILL,
                outline=outline,
                width=1,
            )
            canvas.tag_raise(text_id)
    hand_response_button_spec = getattr(canvas, "hand_response_button_spec", None)
    if hand_response_button_spec is not None and _rect_has_area(hand_response_button_spec.rect):
        rect = hand_response_button_spec.rect
        drag_specs.append(
            LayoutDragSpec(
                key="button_ai_top3",
                label="AI TOP3",
                rect=rect,
                drag_kind="field_pair",
                field_names=("hand_response_button_offset_x", "hand_response_button_offset_y"),
            )
        )
        outline = LAYOUT_DRAG_ACTIVE_OUTLINE if active_key == "button_ai_top3" else LAYOUT_DRAG_OUTLINE
        width = 2 if active_key == "button_ai_top3" else 1
        canvas.create_rectangle(
            rect[0],
            rect[1],
            rect[2],
            rect[3],
            outline=outline,
            dash=LAYOUT_DRAG_DASH,
            width=width,
        )
        text_id = canvas.create_text(
            rect[0] + LAYOUT_DRAG_LABEL_MARGIN,
            rect[1] + LAYOUT_DRAG_LABEL_MARGIN,
            text="AI TOP3",
            anchor=tkinter.NW,
            fill=LAYOUT_DRAG_LABEL_TEXT,
            font=LAYOUT_DRAG_LABEL_FONT,
        )
        text_bounds = canvas.bbox(text_id)
        if text_bounds is not None:
            canvas.create_rectangle(
                text_bounds[0] - 2,
                text_bounds[1] - 1,
                text_bounds[2] + 2,
                text_bounds[3] + 1,
                fill=LAYOUT_DRAG_LABEL_FILL,
                outline=outline,
                width=1,
            )
            canvas.tag_raise(text_id)
    canvas.layout_drag_specs = drag_specs

def _build_hand_tiles_for_recommendation(
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    fallback_tile_37: int | None = None,
) -> list[int]:
    """Return the current visible self hand in the form expected by the AI POST flow."""

    normalized_tiles = [int(tile) for tile in hand_tiles]
    if (
        hand_draw_tile is not None
        and normalized_tiles
        and normalized_tiles[-1] == int(hand_draw_tile)
    ):
        return normalized_tiles
    if hand_draw_tile is None and fallback_tile_37 is not None:
        return [*normalized_tiles, int(fallback_tile_37)]
    if hand_draw_tile is None:
        return normalized_tiles
    return [*normalized_tiles, int(hand_draw_tile)]


def _build_hand_tiles_for_recommendation_history(
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    self_melds: Sequence[Meld],
) -> list[int]:
    """Return a 14-tile total-hand view used by local AI history persistence."""

    history_tiles = _build_hand_tiles_for_recommendation(hand_tiles, hand_draw_tile)
    history_tiles.extend(
        int(tile_37)
        for meld in self_melds
        for tile_37 in meld.tiles_37
    )
    return history_tiles


def _normalize_hand_recommendation_key(hand_tiles: Sequence[int]) -> tuple[int, ...]:
    """Normalize one recommendation hand into an order-insensitive equality key."""

    return tuple(sorted(int(tile) for tile in hand_tiles))


def _display_tile37_equivalent_ids(tile_37: int) -> tuple[int, ...]:
    """Return relaxed display matches for the three five groups only."""

    normalized_tile = int(tile_37)
    if normalized_tile in {5, 10}:
        return (5, 10)
    if normalized_tile in {15, 20}:
        return (15, 20)
    if normalized_tile in {25, 30}:
        return (25, 30)
    return (normalized_tile,)


def _resolve_request_hand_index_by_tile37(
    request_hand_tiles: Sequence[int],
    tile_37: int,
    *,
    occurrence: int = 0,
) -> int | None:
    """Resolve one displayed hand index directly from the renderer-side visible hand order."""

    target_occurrence = int(occurrence)
    if target_occurrence < 0:
        return None
    normalized_tiles = tuple(int(tile) for tile in request_hand_tiles)
    matched_indexes = [
        index
        for index, current_tile in enumerate(normalized_tiles)
        if current_tile == int(tile_37)
    ]
    if not matched_indexes:
        equivalent_ids = _display_tile37_equivalent_ids(tile_37)
        matched_indexes = [
            index
            for index, current_tile in enumerate(normalized_tiles)
            if current_tile in equivalent_ids
        ]
    if target_occurrence >= len(matched_indexes):
        return None
    return matched_indexes[target_occurrence]


def _hand_recommendation_display_context_meld_key(
    display_context: PystyleDisplayContext,
) -> tuple[object, ...]:
    """Serialize renderer-visible meld context into a stable request gate key."""

    return tuple(
        (
            meld.type,
            tuple(int(tile) for tile in meld.tiles),
            int(meld.discarded_tile) if meld.discarded_tile is not None else None,
            int(meld.from_seat) if meld.from_seat is not None else None,
        )
        for meld in display_context.melds
    )


def _hand_recommendation_request_display_key(
    request_hand_tiles: Sequence[int],
    display_context: PystyleDisplayContext | None,
) -> tuple[object, ...]:
    """Return the renderer-side dedupe key for AI TOP3 requests/display reuse."""

    normalized_hand_key = _normalize_hand_recommendation_key(request_hand_tiles)
    if display_context is None:
        return ("request", "", normalized_hand_key)
    round_token = str(display_context.round_token or "")
    if (
        display_context.request_fallback_tile_37 is not None
        and not display_context.allow_history_persist
    ):
        return ("reuse_post_discard", round_token, normalized_hand_key)
    return (
        "request",
        round_token,
        normalized_hand_key,
        int(display_context.turn_index),
        str(display_context.turn_source),
        display_context.wall_tiles_remaining,
        int(display_context.round_wind),
        int(display_context.seat_wind),
        tuple(int(tile) for tile in display_context.dora_indicator_tiles_37),
        _hand_recommendation_display_context_meld_key(display_context),
        tuple(int(count) for count in (display_context.remaining_wall or ())),
    )


def _hand_recommendation_request_context_key(
    display_context: PystyleDisplayContext | None,
) -> tuple[object, ...]:
    """Return the strict context key that identifies one live pystyle request context."""

    if display_context is None:
        return ()
    return (
        int(display_context.turn_index),
        str(display_context.turn_source),
        display_context.wall_tiles_remaining,
        int(display_context.round_wind),
        int(display_context.seat_wind),
        tuple(int(tile) for tile in display_context.dora_indicator_tiles_37),
        _hand_recommendation_display_context_meld_key(display_context),
        tuple(int(count) for count in (display_context.remaining_wall or ())),
        str(display_context.round_token),
    )


def _hand_recommendation_request_context_core_key(
    display_context: PystyleDisplayContext | None,
) -> tuple[object, ...]:
    """Return the stable subset of one request context used by AUTO candidate gating."""

    if display_context is None:
        return ()
    return (
        int(display_context.round_wind),
        int(display_context.seat_wind),
        tuple(int(tile) for tile in display_context.dora_indicator_tiles_37),
        _hand_recommendation_display_context_meld_key(display_context),
        str(display_context.round_token),
    )


def _sync_hand_recommendation_turn_timing(
    canvas: tkinter.Canvas,
    current_request_display_key: tuple[object, ...],
) -> float:
    """Track when the current draw/call turn became active for timeout fallback timing."""

    previous_turn_key = getattr(canvas, "hand_response_turn_display_key", None)
    if previous_turn_key != current_request_display_key:
        started_monotonic_s = time.monotonic()
        canvas.hand_response_turn_display_key = current_request_display_key
        canvas.hand_response_turn_started_monotonic_s = started_monotonic_s
        canvas.hand_response_timeout_fallback_applied_turn_key = None
        return started_monotonic_s
    existing_started_monotonic_s = getattr(
        canvas,
        "hand_response_turn_started_monotonic_s",
        None,
    )
    if existing_started_monotonic_s is None:
        existing_started_monotonic_s = time.monotonic()
        canvas.hand_response_turn_started_monotonic_s = existing_started_monotonic_s
    return float(existing_started_monotonic_s)


def _serialized_hand_recommendation_context_core_key(
    request_context_key: Sequence[object] | None,
) -> tuple[object, ...]:
    """Extract the stable AUTO-gating subset from one serialized panel context key."""

    if request_context_key is None:
        return ()
    serialized_key = tuple(request_context_key)
    if len(serialized_key) < 9:
        return ()
    try:
        return (
            int(serialized_key[3]),
            int(serialized_key[4]),
            tuple(int(tile) for tile in serialized_key[5]),
            tuple(serialized_key[6]),
            str(serialized_key[8]),
        )
    except (TypeError, ValueError):
        return ()


def _is_current_hand_recommendation_context_compatible(
    hand_recommendation_panel: HandRecommendationPanelData,
    display_context: PystyleDisplayContext | None,
) -> bool:
    """Return whether the current panel context is compatible with the current live turn."""

    strict_context_key = _hand_recommendation_request_context_key(display_context)
    if tuple(hand_recommendation_panel.request_context_key or ()) == strict_context_key:
        return True
    return _serialized_hand_recommendation_context_core_key(
        hand_recommendation_panel.request_context_key
    ) == _hand_recommendation_request_context_core_key(display_context)


def _has_usable_current_hand_recommendation(
    request_hand_tiles: Sequence[int],
    hand_recommendation_panel: HandRecommendationPanelData,
    display_context: PystyleDisplayContext | None,
) -> bool:
    """Return whether the current panel snapshot is good enough to drive AUTO right now."""

    if not hand_recommendation_panel.items:
        return False
    if _normalize_hand_recommendation_key(hand_recommendation_panel.hand_key) != _normalize_hand_recommendation_key(
        request_hand_tiles
    ):
        return False
    if str(hand_recommendation_panel.round_token or "") != str(getattr(display_context, "round_token", "") or ""):
        return False
    return _is_current_hand_recommendation_context_compatible(
        hand_recommendation_panel,
        display_context,
    )


def _hand_recommendation_top_expected_value(
    hand_recommendation_panel: HandRecommendationPanelData,
) -> float | None:
    """Return the current panel's numeric top EV when available."""

    explicit_top_expected_value = hand_recommendation_panel.top_expected_value
    if explicit_top_expected_value is not None:
        try:
            return float(explicit_top_expected_value)
        except (TypeError, ValueError):
            pass
    if not hand_recommendation_panel.items:
        return None
    first_expected_value = hand_recommendation_panel.items[0].expected_value
    if first_expected_value is None:
        return None
    try:
        return float(first_expected_value)
    except (TypeError, ValueError):
        return None


def _should_highlight_hand_recommendation_row(
    hand_recommendation_panel: HandRecommendationPanelData,
    recommendation: HandRecommendationItem,
    index: int,
) -> bool:
    """Return whether this TOP3 row should use the green accent.

    The top EV row is always highlighted. Rows within 50pt of the current top EV also stay green.
    """

    if index <= 0:
        return True
    top_expected_value = _hand_recommendation_top_expected_value(hand_recommendation_panel)
    if top_expected_value is None:
        return False
    if recommendation.expected_value is None:
        return False
    try:
        recommendation_expected_value = float(recommendation.expected_value)
    except (TypeError, ValueError):
        return False
    return recommendation_expected_value >= (
        top_expected_value - HAND_RESPONSE_NEAR_TOP_EV_THRESHOLD_PT
    )


def _format_hand_recommendation_win_probability_text(
    win_probability: float | None,
) -> str:
    """Return one compact agari-rate text for the AI TOP3 popup."""

    if win_probability is None:
        return ""
    try:
        numeric_value = float(win_probability)
    except (TypeError, ValueError):
        return ""
    if numeric_value < 0:
        return ""
    if numeric_value <= 1.0:
        numeric_value *= 100.0
    return f"{numeric_value:.1f}%"


def _format_hand_recommendation_value_text(
    recommendation: HandRecommendationItem,
) -> str:
    """Return the compact EV + agari-rate text shown in one TOP3 row."""

    expected_value_text = str(recommendation.expected_value_text or "").strip()
    win_probability_text = _format_hand_recommendation_win_probability_text(
        recommendation.win_probability
    )
    if expected_value_text and win_probability_text:
        return f"{expected_value_text} {win_probability_text}"
    return expected_value_text or win_probability_text


def _should_retry_hand_recommendation_for_auto(
    request_hand_tiles: Sequence[int],
    hand_recommendation_panel: HandRecommendationPanelData,
    display_context: PystyleDisplayContext | None,
    current_request_display_key: tuple[object, ...],
    last_requested_display_key: tuple[object, ...] | None,
    last_request_started_monotonic_s: float | None,
    *,
    auto_mode_enabled: bool,
) -> bool:
    """Return whether AUTO should retry the AI POST for the current hand/context."""

    if not auto_mode_enabled:
        return False
    if last_requested_display_key != current_request_display_key:
        return False
    if hand_recommendation_panel.is_loading:
        return False
    if _has_usable_current_hand_recommendation(
        request_hand_tiles,
        hand_recommendation_panel,
        display_context,
    ):
        return False
    if last_request_started_monotonic_s is None:
        return True
    return (time.monotonic() - float(last_request_started_monotonic_s)) >= HAND_AUTO_RECOMMENDATION_RETRY_S


def _should_use_pystyle_timeout_fallback(
    request_hand_tiles: Sequence[int],
    hand_recommendation_panel: HandRecommendationPanelData,
    display_context: PystyleDisplayContext | None,
    current_request_display_key: tuple[object, ...],
    last_requested_display_key: tuple[object, ...] | None,
    turn_started_monotonic_s: float | None,
    *,
    timeout_fallback_applied_turn_key: tuple[object, ...] | None = None,
    now_monotonic_s: float | None = None,
) -> bool:
    """Return whether recommendation AUTO should fall back after waiting too long.

    Timeout fallback is measured from the current draw/call turn becoming active on screen, not
    from the most recent pystyle POST start time.
    """

    if display_context is None:
        return False
    if display_context.request_fallback_tile_37 is not None:
        return False
    if last_requested_display_key != current_request_display_key:
        return False
    if timeout_fallback_applied_turn_key == current_request_display_key:
        return False
    if _has_usable_current_hand_recommendation(
        request_hand_tiles,
        hand_recommendation_panel,
        display_context,
    ):
        return False
    if turn_started_monotonic_s is None:
        return False
    current_monotonic_s = (
        float(now_monotonic_s)
        if now_monotonic_s is not None
        else float(time.monotonic())
    )
    return (
        current_monotonic_s - float(turn_started_monotonic_s)
    ) >= HAND_AUTO_RECOMMENDATION_RETRY_S


def _is_current_hand_recommendation_error_state(
    request_hand_tiles: Sequence[int],
    hand_recommendation_panel: HandRecommendationPanelData,
    display_context: PystyleDisplayContext | None,
) -> bool:
    """Return whether the current panel snapshot is a non-loading error/unavailable state."""

    if display_context is None:
        return False
    if display_context.request_fallback_tile_37 is not None:
        return False
    if hand_recommendation_panel.is_loading:
        return False
    if hand_recommendation_panel.items:
        return False
    if _normalize_hand_recommendation_key(hand_recommendation_panel.hand_key) != _normalize_hand_recommendation_key(
        request_hand_tiles
    ):
        return False
    return str(hand_recommendation_panel.round_token or "") == str(display_context.round_token or "")


def _should_use_pystyle_error_fallback(
    request_hand_tiles: Sequence[int],
    hand_recommendation_panel: HandRecommendationPanelData,
    display_context: PystyleDisplayContext | None,
    current_request_display_key: tuple[object, ...],
    last_requested_display_key: tuple[object, ...] | None,
    last_request_started_monotonic_s: float | None,
    *,
    now_monotonic_s: float | None = None,
) -> bool:
    """Return whether recommendation AUTO should use fallback after an error-like response."""

    if last_requested_display_key != current_request_display_key:
        return False
    if not _is_current_hand_recommendation_error_state(
        request_hand_tiles,
        hand_recommendation_panel,
        display_context,
    ):
        return False
    if last_request_started_monotonic_s is None:
        return False
    current_monotonic_s = (
        float(now_monotonic_s)
        if now_monotonic_s is not None
        else float(time.monotonic())
    )
    return (
        current_monotonic_s - float(last_request_started_monotonic_s)
    ) >= HAND_AUTO_RECOMMENDATION_ERROR_FALLBACK_S


def _select_hand_auto_discard_candidate(
    request_hand_tiles: Sequence[int],
    hand_recommendation_panel: HandRecommendationPanelData,
    display_context: PystyleDisplayContext | None,
) -> HandAutoDiscardCandidate | None:
    """Return the current auto-discard candidate from the latest visible-hand recommendation.

    Open-hand live requests can still return a useful top discard even when the upstream service
    treats the situation with closed-hand assumptions. For AUTO mode, prefer "same visible hand in
    the same round and the recommended tile is still present" over strict meld-context equality.
    """

    if display_context is None:
        return None
    if display_context.request_fallback_tile_37 is not None:
        return None
    if not hand_recommendation_panel.items:
        return None
    if _normalize_hand_recommendation_key(hand_recommendation_panel.hand_key) != _normalize_hand_recommendation_key(
        request_hand_tiles
    ):
        return None
    if str(hand_recommendation_panel.round_token or "") != str(display_context.round_token or ""):
        return None
    top_item = hand_recommendation_panel.items[0]
    if top_item.tile_37 is None:
        return None
    tile_37 = int(top_item.tile_37)
    resolved_hand_index = _resolve_request_hand_index_by_tile37(request_hand_tiles, tile_37)
    if resolved_hand_index is None:
        return None
    is_exact_context_match = _is_current_hand_recommendation_context_compatible(
        hand_recommendation_panel,
        display_context,
    )
    return HandAutoDiscardCandidate(
        attempt_key=(
            "auto_discard" if is_exact_context_match else "auto_discard_relaxed",
            *_hand_recommendation_request_display_key(request_hand_tiles, display_context),
            tile_37,
        ),
        tile_37=tile_37,
        hand_index=resolved_hand_index,
        tile_text=str(top_item.tile_text or ""),
    )


def _select_hand_betaori_candidate(
    request_hand_tiles: Sequence[int],
    hand_danger_percentages: Sequence[HandDangerPercentages],
    display_context: PystyleDisplayContext | None,
) -> HandAutoDiscardCandidate | None:
    """Return the safest current discard candidate by minimizing the current hand tint score."""

    if display_context is None:
        return None
    if display_context.request_fallback_tile_37 is not None:
        return None
    normalized_tiles = tuple(int(tile) for tile in request_hand_tiles)
    if not normalized_tiles:
        return None
    best_index: int | None = None
    best_tile_37: int | None = None
    best_score: float | None = None
    for hand_index, tile_37 in enumerate(normalized_tiles):
        danger_metrics = (
            hand_danger_percentages[hand_index]
            if hand_index < len(hand_danger_percentages)
            else _normalize_hand_danger_percentages(None)
        )
        score = _combined_hand_danger_probability_percent(danger_metrics)
        if best_score is None or score < best_score:
            best_index = hand_index
            best_tile_37 = tile_37
            best_score = score
    if best_index is None or best_tile_37 is None or best_score is None:
        return None
    rounded_score = round(float(best_score), 2)
    return HandAutoDiscardCandidate(
        attempt_key=(
            "betaori_discard",
            *_hand_recommendation_request_display_key(normalized_tiles, display_context),
            int(best_index),
            int(best_tile_37),
            rounded_score,
        ),
        tile_37=int(best_tile_37),
        hand_index=int(best_index),
        tile_text=_tile37_to_compact_label(int(best_tile_37)),
    )


def _build_hand_betaori_top3_panel_data(
    request_hand_tiles: Sequence[int],
    hand_danger_percentages: Sequence[HandDangerPercentages],
    display_context: PystyleDisplayContext | None,
) -> HandRecommendationPanelData:
    """Build a display-only safest-discard top3 from current hand danger scores."""

    normalized_tiles = tuple(int(tile) for tile in request_hand_tiles)
    if display_context is None:
        return HandRecommendationPanelData(
            hand_key=_normalize_hand_recommendation_key(normalized_tiles),
            subtitle_text="現在局面が未確定です。",
            status_text="ベタオリTOP3を表示できません。",
        )
    if not normalized_tiles:
        return HandRecommendationPanelData(
            round_token=str(getattr(display_context, "round_token", "") or ""),
            subtitle_text="現在手牌が空です。",
            status_text="ベタオリTOP3を表示できません。",
        )

    best_by_tile: dict[int, tuple[float, int]] = {}
    for hand_index, tile_37 in enumerate(normalized_tiles):
        if 31 <= int(tile_37) <= 37:
            continue
        danger_metrics = (
            hand_danger_percentages[hand_index]
            if hand_index < len(hand_danger_percentages)
            else _normalize_hand_danger_percentages(None)
        )
        score = _combined_hand_danger_probability_percent(danger_metrics)
        current = best_by_tile.get(int(tile_37))
        if current is None or (score, hand_index) < current:
            best_by_tile[int(tile_37)] = (float(score), int(hand_index))

    ranked = sorted(
        (
            (score, hand_index, tile_37)
            for tile_37, (score, hand_index) in best_by_tile.items()
        ),
        key=lambda entry: (entry[0], entry[1], entry[2]),
    )
    items = tuple(
        HandRecommendationItem(
            rank=index + 1,
            tile_text=_tile37_to_compact_label(tile_37),
            tile_37=tile_37,
            expected_value=None,
            expected_value_text=f"危険 {score:.1f}%",
        )
        for index, (score, _hand_index, tile_37) in enumerate(ranked[:3])
    )
    return HandRecommendationPanelData(
        items=items,
        hand_key=_normalize_hand_recommendation_key(normalized_tiles),
        round_token=str(getattr(display_context, "round_token", "") or ""),
        request_context_key=_hand_recommendation_request_context_key(display_context),
        top_expected_value=None,
        subtitle_text="ベタオリ安全度順です。",
        status_text=("" if items else "ベタオリTOP3を表示できません。"),
    )


def _select_hand_pystyle_honor_fallback_candidate(
    request_hand_tiles: Sequence[int],
    hand_danger_percentages: Sequence[HandDangerPercentages],
    display_context: PystyleDisplayContext | None,
) -> HandAutoDiscardCandidate | None:
    """Return one recommendation-mode fallback candidate: honor first, else betaori."""

    if display_context is None:
        return None
    if display_context.request_fallback_tile_37 is not None:
        return None
    normalized_tiles = tuple(int(tile) for tile in request_hand_tiles)
    if not normalized_tiles:
        return None

    best_honor_index: int | None = None
    best_honor_tile_37: int | None = None
    best_honor_score: float | None = None
    for hand_index, tile_37 in enumerate(normalized_tiles):
        if not 31 <= int(tile_37) <= 37:
            continue
        danger_metrics = (
            hand_danger_percentages[hand_index]
            if hand_index < len(hand_danger_percentages)
            else _normalize_hand_danger_percentages(None)
        )
        score = _combined_hand_danger_probability_percent(danger_metrics)
        if best_honor_score is None or score < best_honor_score:
            best_honor_index = hand_index
            best_honor_tile_37 = int(tile_37)
            best_honor_score = score
    if (
        best_honor_index is not None
        and best_honor_tile_37 is not None
        and best_honor_score is not None
    ):
        rounded_score = round(float(best_honor_score), 2)
        return HandAutoDiscardCandidate(
            attempt_key=(
                "pystyle_shanten_honor_discard",
                *_hand_recommendation_request_display_key(normalized_tiles, display_context),
                int(best_honor_index),
                int(best_honor_tile_37),
                rounded_score,
            ),
            tile_37=int(best_honor_tile_37),
            hand_index=int(best_honor_index),
            tile_text=_tile37_to_compact_label(int(best_honor_tile_37)),
        )

    betaori_candidate = _select_hand_betaori_candidate(
        normalized_tiles,
        hand_danger_percentages,
        display_context,
    )
    if betaori_candidate is None:
        return None
    return HandAutoDiscardCandidate(
        attempt_key=(
            "pystyle_shanten_betaori",
            *tuple(betaori_candidate.attempt_key[1:]),
        ),
        tile_37=int(betaori_candidate.tile_37),
        hand_index=(
            int(betaori_candidate.hand_index)
            if betaori_candidate.hand_index is not None
            else None
        ),
        tile_text=str(betaori_candidate.tile_text or ""),
    )


def _round_token_from_identity(round_identity: object | None) -> str:
    """Normalize the current round identity into a stable string token."""

    if round_identity is None:
        return ""
    if isinstance(round_identity, tuple) and len(round_identity) == 2:
        logical_round_identity, bootstrap_sequence = round_identity
        if isinstance(bootstrap_sequence, int):
            return str(logical_round_identity)
    return str(round_identity)


def _can_reuse_existing_hand_recommendation(
    request_hand_tiles: Sequence[int],
    hand_recommendation_panel: HandRecommendationPanelData,
    display_context: PystyleDisplayContext | None,
) -> bool:
    """Return whether an existing snapshot may be reused for post-discard display."""

    if display_context is None:
        return False
    if display_context.allow_history_persist:
        return False
    if display_context.request_fallback_tile_37 is None:
        return False
    if not hand_recommendation_panel.items:
        return False
    if str(hand_recommendation_panel.round_token or "") != str(display_context.round_token or ""):
        return False
    return _normalize_hand_recommendation_key(
        hand_recommendation_panel.hand_key
    ) == _normalize_hand_recommendation_key(request_hand_tiles)


def _has_self_low_ev_open_hand_penalty(self_melds: Sequence[Meld]) -> bool:
    """Return whether the self hand should receive the open-hand EV penalty."""

    return any(getattr(meld, "is_open", False) for meld in self_melds)


def _adjust_self_hand_alert_expected_value(
    raw_top_expected_value: float,
    self_melds: Sequence[Meld],
) -> float:
    """Return the alert-only EV after applying the open-hand penalty.

    The visible `AI TOP3` panel keeps pystyle's raw EV text. Only the SELF/LOW EV alert
    compares against the open-hand-adjusted value.
    """

    adjusted_top_expected_value = float(raw_top_expected_value)
    if _has_self_low_ev_open_hand_penalty(self_melds):
        adjusted_top_expected_value *= HAND_SELF_ALERT_OPEN_HAND_FACTOR
    return adjusted_top_expected_value


def _should_evaluate_alert_audio_for_refresh_token(
    canvas: tkinter.Canvas,
    refresh_token: object | None,
) -> bool:
    """Return whether alert audio should be reevaluated for this refresh token."""

    previous_refresh_token = getattr(
        canvas,
        "last_alert_audio_refresh_token",
        _ALERT_AUDIO_REFRESH_TOKEN_UNSET,
    )
    if previous_refresh_token == refresh_token:
        return False
    canvas.last_alert_audio_refresh_token = refresh_token
    return True


def _split_combined_refresh_token(
    refresh_token: object | None,
) -> tuple[object | None, int | None]:
    """Split one `(base_refresh_token, recommendation_update_sequence)` token."""

    if not isinstance(refresh_token, tuple) or len(refresh_token) != 2:
        return refresh_token, None
    recommendation_token = refresh_token[1]
    if isinstance(recommendation_token, bool):
        return refresh_token, None
    try:
        normalized_recommendation_token = int(recommendation_token)
    except (TypeError, ValueError):
        return refresh_token, None
    return refresh_token[0], normalized_recommendation_token


def _split_live_refresh_token(
    refresh_token: object | None,
) -> tuple[object | None, int | None]:
    """Split one `(live_refresh_token, async_update_sequence)` token."""

    if not isinstance(refresh_token, tuple) or len(refresh_token) != 2:
        return refresh_token, None
    async_token = refresh_token[1]
    if isinstance(async_token, bool):
        return refresh_token, None
    try:
        normalized_async_token = int(async_token)
    except (TypeError, ValueError):
        return refresh_token, None
    return refresh_token[0], normalized_async_token


def _should_use_hand_response_only_refresh(
    previous_refresh_token: object | None,
    next_refresh_token: object | None,
) -> bool:
    """Return whether only the recommendation-side token changed."""

    previous_base_token, previous_recommendation_token = _split_combined_refresh_token(
        previous_refresh_token
    )
    next_base_token, next_recommendation_token = _split_combined_refresh_token(next_refresh_token)
    return (
        previous_recommendation_token is not None
        and next_recommendation_token is not None
        and previous_base_token == next_base_token
        and previous_recommendation_token != next_recommendation_token
    )


def _should_use_live_async_only_refresh(
    previous_refresh_token: object | None,
    next_refresh_token: object | None,
) -> bool:
    """Return whether only the live async-bundle token changed."""

    previous_base_token, previous_recommendation_token = _split_combined_refresh_token(
        previous_refresh_token
    )
    next_base_token, next_recommendation_token = _split_combined_refresh_token(next_refresh_token)
    if previous_recommendation_token != next_recommendation_token:
        return False
    previous_live_token, previous_async_token = _split_live_refresh_token(previous_base_token)
    next_live_token, next_async_token = _split_live_refresh_token(next_base_token)
    return (
        previous_async_token is not None
        and next_async_token is not None
        and previous_live_token == next_live_token
        and previous_async_token != next_async_token
    )


def _should_play_self_hand_value_alert_sound(
    previous_kind: str | None,
    current_kind: str | None,
) -> bool:
    """Return whether the self-hand alert sound should fire for this transition."""

    normalized_previous = str(previous_kind or HAND_SELF_ALERT_KIND_NONE)
    normalized_current = str(current_kind or HAND_SELF_ALERT_KIND_NONE)
    return (
        normalized_current in {
            HAND_SELF_ALERT_KIND_LOW,
            HAND_SELF_ALERT_KIND_WARNING,
        }
        and normalized_current != normalized_previous
    )


def _should_play_low_ev_self_hand_alert_sound_for_round(
    current_kind: str | None,
    current_round_token: str | None,
    last_low_ev_sound_round_token: str | None,
) -> bool:
    """Return whether LOW EV may still beep in the current round."""

    if str(current_kind or HAND_SELF_ALERT_KIND_NONE) != HAND_SELF_ALERT_KIND_LOW:
        return True
    normalized_round_token = str(current_round_token or "").strip()
    if not normalized_round_token:
        return True
    return normalized_round_token != str(last_low_ev_sound_round_token or "").strip()


def _play_self_hand_value_alert_sound_worker(alert_kind: str) -> None:
    """Emit one short platform sound for the current self-hand alert kind."""

    if winsound is None:
        return

    frequency_hz, duration_ms = {
        HAND_SELF_ALERT_KIND_LOW: (660, 90),
        HAND_SELF_ALERT_KIND_WARNING: (880, 80),
        HAND_SELF_ALERT_KIND_HIGH: (1320, 80),
    }.get(str(alert_kind), (880, 80))
    try:
        winsound.Beep(frequency_hz, duration_ms)
    except RuntimeError:
        try:
            winsound.MessageBeep()
        except RuntimeError:
            return


def _play_self_hand_value_alert_sound_if_needed(
    canvas: tkinter.Canvas,
    self_hand_value_alert: SelfHandValueAlertState,
) -> None:
    """Play a short sound only when the self-hand alert state changes into an alert."""

    previous_kind = getattr(
        canvas,
        "last_self_hand_value_alert_kind",
        HAND_SELF_ALERT_KIND_NONE,
    )
    current_kind = str(self_hand_value_alert.kind or HAND_SELF_ALERT_KIND_NONE)
    current_round_token = str(self_hand_value_alert.round_token or "").strip()
    last_low_ev_sound_round_token = str(
        getattr(canvas, "last_self_low_ev_sound_round_token", "") or ""
    ).strip()
    canvas.last_self_hand_value_alert_kind = current_kind
    if not _should_play_self_hand_value_alert_sound(previous_kind, current_kind):
        return
    if not _should_play_low_ev_self_hand_alert_sound_for_round(
        current_kind,
        current_round_token,
        last_low_ev_sound_round_token,
    ):
        return
    now_monotonic_s = time.monotonic()
    if (
        now_monotonic_s
        - float(getattr(canvas, "last_self_hand_alert_sound_monotonic_s", 0.0) or 0.0)
        < SELF_HAND_ALERT_SOUND_MIN_INTERVAL_S
    ):
        if current_kind == HAND_SELF_ALERT_KIND_LOW and current_round_token:
            canvas.last_self_low_ev_sound_round_token = current_round_token
        return
    canvas.last_self_hand_alert_sound_monotonic_s = now_monotonic_s
    if current_kind == HAND_SELF_ALERT_KIND_LOW and current_round_token:
        canvas.last_self_low_ev_sound_round_token = current_round_token
    if winsound is None:
        try:
            canvas.bell()
        except tkinter.TclError:
            return
        return
    _start_tracked_background_thread(
        label="self alert sound",
        name="self-hand-alert-sound",
        target=_play_self_hand_value_alert_sound_worker,
        args=(current_kind,),
    )


def _build_self_hand_value_alert_state(
    hand_recommendation_panel: HandRecommendationPanelData,
    request_hand_tiles: Sequence[int],
    round_identity: object | None,
    self_melds: Sequence[Meld],
) -> SelfHandValueAlertState:
    """Return the current self-hand EV alert derived from the latest pystyle result."""

    current_hand_key = _normalize_hand_recommendation_key(request_hand_tiles)
    current_round_token = _round_token_from_identity(round_identity)
    raw_top_expected_value = hand_recommendation_panel.top_expected_value
    if (
        raw_top_expected_value is None
        or _normalize_hand_recommendation_key(hand_recommendation_panel.hand_key) != current_hand_key
        or hand_recommendation_panel.round_token != current_round_token
    ):
        return SelfHandValueAlertState(round_token=current_round_token)

    raw_top_expected_value = float(raw_top_expected_value)
    adjusted_top_expected_value = _adjust_self_hand_alert_expected_value(
        raw_top_expected_value,
        self_melds,
    )
    if adjusted_top_expected_value < HAND_SELF_ALERT_THRESHOLD:
        return SelfHandValueAlertState(
            active=True,
            kind=HAND_SELF_ALERT_KIND_LOW,
            round_token=current_round_token,
            label="LOW EV",
            dot_color=PLAYER_ALERT_RED,
            fill_color=HAND_SELF_ALERT_ACTIVE_FILL,
            outline_color=HAND_SELF_ALERT_ACTIVE_OUTLINE,
            text_color=HAND_SELF_ALERT_ACTIVE_TEXT,
            adjusted_top_expected_value=adjusted_top_expected_value,
            raw_top_expected_value=raw_top_expected_value,
        )
    if raw_top_expected_value < HAND_SELF_ALERT_WARNING_THRESHOLD:
        return SelfHandValueAlertState(
            active=True,
            kind=HAND_SELF_ALERT_KIND_WARNING,
            round_token=current_round_token,
            label="EV<800",
            dot_color=PLAYER_ALERT_YELLOW,
            fill_color=HAND_SELF_ALERT_WARNING_FILL,
            outline_color=HAND_SELF_ALERT_WARNING_OUTLINE,
            text_color=HAND_SELF_ALERT_WARNING_TEXT,
            adjusted_top_expected_value=adjusted_top_expected_value,
            raw_top_expected_value=raw_top_expected_value,
        )
    if raw_top_expected_value >= HAND_SELF_ALERT_HIGH_THRESHOLD:
        return SelfHandValueAlertState(
            active=True,
            kind=HAND_SELF_ALERT_KIND_HIGH,
            round_token=current_round_token,
            label="HIGH EV",
            dot_color=PLAYER_ALERT_GREEN,
            fill_color=HAND_SELF_ALERT_HIGH_FILL,
            outline_color=HAND_SELF_ALERT_HIGH_OUTLINE,
            text_color=HAND_SELF_ALERT_HIGH_TEXT,
            adjusted_top_expected_value=adjusted_top_expected_value,
            raw_top_expected_value=raw_top_expected_value,
        )
    return SelfHandValueAlertState(
        round_token=current_round_token,
        adjusted_top_expected_value=adjusted_top_expected_value,
        raw_top_expected_value=raw_top_expected_value,
    )


def create_canvas(
    root: tkinter.Tk,
    img_table: TileImageTable,
    discards: Mapping[Player, Iterable[Discard]] | SutehaiTracker,
    hand_tiles: Sequence[int] | None = None,
    hand_draw_tile: int | None = None,
    hand_recommendation_panel: HandRecommendationPanelData | None = None,
    hand_danger_percentages: Sequence[HandDangerPercentages] | None = None,
    opponent_suji_panel_summaries: OpponentSujiPanelSummaries | None = None,
    player_push_alert_percentages: PlayerPushAlertPercentages | None = None,
    player_alert_indicators_by_seat: PlayerAlertIndicatorsBySeat | None = None,
    player_score_diffs_by_seat: PlayerScoreDiffs | None = None,
    discard_red_tint_indices_by_seat: DiscardRedTintIndicesBySeat | None = None,
    player_names_by_seat: PlayerNamesBySeat | None = None,
    meld_tiles: Sequence[int] | None = None,
    dora_indicator_tiles: Sequence[int] | None = None,
    round_info_panel: RoundInfoPanelData | None = None,
    auto_refresh_ms: int | None = None,
    hand_tiles_provider: Callable[[], Sequence[int]] | None = None,
    hand_draw_tile_provider: Callable[[], int | None] | None = None,
    hand_recommendation_panel_provider: Callable[[], HandRecommendationPanelData] | None = None,
    hand_recommendation_request_action: Callable[[Sequence[int], Any | None], None] | None = None,
    hand_recommendation_reset_action: Callable[[], None] | None = None,
    hand_auto_discard_action: Callable[[int], Mapping[str, object] | None] | None = None,
    hand_bridge_discard_by_index_action: Callable[[int], Mapping[str, object] | None] | None = None,
    bridge_status_provider: Callable[[], TenhouUiBridgeStatus] | None = None,
    bridge_ui_snapshot_action: Callable[[], Mapping[str, object] | None] | None = None,
    bridge_table_snapshot_action: Callable[[], Mapping[str, object] | None] | None = None,
    bridge_click_control_action: Callable[[int], Mapping[str, object] | None] | None = None,
    start_pystyle_auto_mode: bool = False,
    hand_recommendation_history_action: Callable[
        [Sequence[int], HandRecommendationPanelData, PystyleDisplayContext],
        None,
    ] | None = None,
    hand_recommendation_request_context: PystyleDisplayContext | None = None,
    hand_recommendation_request_context_provider: Callable[
        [],
        PystyleDisplayContext | None,
    ] | None = None,
    hand_danger_percentages_provider: Callable[[], Sequence[HandDangerPercentages]] | None = None,
    opponent_suji_panel_summaries_provider: Callable[[], OpponentSujiPanelSummaries] | None = None,
    player_names_by_seat_provider: Callable[[], PlayerNamesBySeat] | None = None,
    meld_tiles_provider: Callable[[], Sequence[int]] | None = None,
    dora_indicator_tiles_provider: Callable[[], Sequence[int]] | None = None,
    round_info_panel_provider: Callable[[], RoundInfoPanelData] | None = None,
    melds_by_player: SeatMeldMap | None = None,
    melds_by_player_provider: Callable[[], SeatMeldMap] | None = None,
    visible_summary: VisibleTileSummary | None = None,
    visible_summary_provider: Callable[[], VisibleTileSummary] | None = None,
    round_identity: object | None = None,
    round_identity_provider: Callable[[], object | None] | None = None,
    table_snapshot_provider: Callable[[], Any] | None = None,
    table_snapshot_reinit_action: Callable[[], object | None] | None = None,
    refresh_token: object | None = None,
    refresh_token_provider: Callable[[], object | None] | None = None,
    refresh_watch_ms: int = 16,
) -> None:
    """天鳳風レイアウトの卓 Canvas を 1 枚描画する。"""

    # 呼び出し側が Tracker を渡しても dict を渡しても同じ形で扱えるよう正規化する。
    discard_map: Mapping[Player, Iterable[Discard]]
    if isinstance(discards, SutehaiTracker):
        discard_map = discards.discards
    else:
        discard_map = discards
    # None を許す引数はここで描画用の実配列へ確定させる。
    current_hand_tiles = list(hand_tiles) if hand_tiles is not None else list(DEFAULT_HAND_TILES)
    current_hand_draw_tile = hand_draw_tile
    current_hand_recommendation_panel = (
        hand_recommendation_panel
        if hand_recommendation_panel is not None
        else HandRecommendationPanelData()
    )
    current_hand_danger_percentages = (
        [_normalize_hand_danger_percentages(percentages) for percentages in hand_danger_percentages]
        if hand_danger_percentages is not None
        else []
    )
    current_opponent_suji_panel_summaries = _normalize_opponent_suji_panel_summaries(
        opponent_suji_panel_summaries
    )
    current_player_push_alert_percentages = _normalize_player_push_alert_percentages(
        player_push_alert_percentages
    )
    current_player_alert_indicators_by_seat = _normalize_player_alert_indicators_by_seat(
        player_alert_indicators_by_seat
    )
    if not current_player_alert_indicators_by_seat:
        current_player_alert_indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            current_opponent_suji_panel_summaries,
            current_player_push_alert_percentages,
        )
    current_player_score_diffs_by_seat = _normalize_player_score_diffs_by_seat(
        player_score_diffs_by_seat
    )
    current_discard_red_tint_indices_by_seat = _normalize_discard_red_tint_indices_by_seat(
        discard_red_tint_indices_by_seat
    )
    current_player_names_by_seat = _normalize_player_names_by_seat(player_names_by_seat)
    current_meld_tiles = list(meld_tiles) if meld_tiles is not None else []
    current_dora_indicator_tiles = list(dora_indicator_tiles) if dora_indicator_tiles is not None else []
    current_round_info_panel = (
        round_info_panel
        if round_info_panel is not None
        else RoundInfoPanelData()
    )
    current_melds_by_player = _normalize_meld_map(melds_by_player)
    detail_panel_state = DetailPanelState()

    # 卓全体を描く Canvas を初期化する。
    root.configure(bg=BOARD_OUTER)
    board_canvas = tkinter.Canvas(
        root,
        bg=BOARD_OUTER,
        highlightthickness=0,
        bd=0,
    )
    board_canvas.pack(fill=tkinter.BOTH, expand=True)
    # Tk が画像参照をGCしないよう Canvas に保持させる。
    board_canvas.base_image_table = img_table
    board_canvas.image_table = img_table
    board_canvas.scaled_image_table_cache = {1.0: img_table}
    board_canvas.thinking_tile_image_cache = {}
    board_canvas.hand_danger_tile_image_cache = {}
    board_canvas.hand_response_tile_image_cache = {}
    board_canvas.inferred_visible_tile_image_cache = {}
    board_canvas.detail_panel_state = detail_panel_state
    board_canvas.player_panel_button_specs = []
    board_canvas.lag_marker_reference_button_specs = []
    board_canvas.inferred_visible_candidate_button_specs = []
    board_canvas.inferred_visible_tile_count_click_specs = []
    board_canvas.inferred_visible_manual_count_button_specs = []
    board_canvas.inferred_visible_delete_button_specs = []
    board_canvas.selected_inferred_visible_delete_button_specs = []
    board_canvas.table_situation_cell_click_specs = []
    board_canvas.discard_tile_selection_click_specs = []
    board_canvas.inferred_visible_entry_excluded_seats = {}
    board_canvas.inferred_visible_deleted_entry_keys = set()
    board_canvas.inferred_visible_manual_counts_by_tile34 = {}
    board_canvas.inferred_visible_entries = []
    board_canvas.current_visible_tile_inference_summary = VisibleTileInferenceSummary()
    board_canvas.inferred_visible_runtime_enabled = bool(INFERRED_VISIBLE_ENABLED)
    board_canvas.table_situation_scores_by_seat = {
        seat: _empty_table_situation_scores()
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    board_canvas.table_situation_panels_visible = bool(TABLE_SITUATION_ENABLED)
    board_canvas.selected_inferred_visible_disabled_seats_by_tile34 = {}
    board_canvas.selected_inferred_visible_tile_34_index = None
    board_canvas.selected_inferred_visible_tile_37 = None
    board_canvas.inferred_visible_async_request_queue = queue.Queue()
    board_canvas.inferred_visible_async_result_queue = queue.Queue()
    board_canvas.inferred_visible_async_thread = None
    board_canvas.inferred_visible_async_in_flight = False
    board_canvas.inferred_visible_async_pending_key = None
    board_canvas.inferred_visible_async_requested_key = None
    board_canvas.inferred_visible_async_completed_cache_key = None
    board_canvas.hand_response_panel_state = _resolve_hand_response_panel_state_for_auto_mode(
        None,
        auto_mode_enabled=bool(start_pystyle_auto_mode),
        auto_mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
    )
    board_canvas.hand_response_button_spec = None
    board_canvas.hand_betaori_response_button_spec = None
    board_canvas.current_hand_tiles_for_response = list(current_hand_tiles)
    board_canvas.current_hand_recommendation_request_context = hand_recommendation_request_context or PystyleDisplayContext()
    board_canvas.hand_response_requested_hand_key = None
    board_canvas.hand_response_last_request_started_monotonic_s = None
    board_canvas.hand_response_turn_started_monotonic_s = None
    board_canvas.hand_response_turn_display_key = None
    board_canvas.hand_response_timeout_fallback_applied_turn_key = None
    board_canvas.inferred_visible_tile_selector_window = None
    board_canvas.inferred_visible_tile_selector_buttons_by_tile37 = {}
    board_canvas.inferred_visible_tile_selector_image_tables = {}
    board_canvas.hand_auto_mode_state = HandAutoModeState(
        enabled=bool(start_pystyle_auto_mode),
        mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
    )
    board_canvas.hand_auto_discard_action = hand_auto_discard_action
    board_canvas.hand_bridge_discard_by_index_action = hand_bridge_discard_by_index_action
    board_canvas.bridge_status_provider = bridge_status_provider
    board_canvas.bridge_ui_snapshot_action = bridge_ui_snapshot_action
    board_canvas.bridge_table_snapshot_action = bridge_table_snapshot_action
    board_canvas.bridge_click_control_action = bridge_click_control_action
    board_canvas.bridge_background_result_queue = queue.Queue()
    board_canvas.bridge_snapshot_in_flight = False
    board_canvas.bridge_snapshot_pending_force = False
    board_canvas.bridge_last_snapshot_started_monotonic_s = 0.0
    board_canvas.bridge_table_snapshot_in_flight = False
    board_canvas.bridge_snapshot_source_refresh_token = refresh_token
    board_canvas.bridge_last_requested_source_refresh_token = None
    board_canvas.bridge_feedback_text = ""
    board_canvas.bridge_feedback_is_error = False
    board_canvas.bridge_feedback_expires_monotonic_s = 0.0
    board_canvas.bridge_status_tick_job = None
    board_canvas.bridge_status_tick_closed = False
    board_canvas.last_bridge_status_tick_error_text = None
    board_canvas.bridge_followup_snapshot_jobs = []
    board_canvas.bridge_table_snapshot_retry_count = 0
    board_canvas.bridge_table_snapshot_retry_job = None
    board_canvas.bridge_hand_auto_ready = None
    board_canvas.bridge_hand_auto_rearm_pending = False
    board_canvas.bridge_toggle_active_overrides = {}
    board_canvas.bridge_toggle_buttons_by_id = {}
    board_canvas.bridge_action_buttons_by_key = {}
    board_canvas.bridge_control_buttons_by_id = {}
    board_canvas.thread_activity_notice_entries = []
    board_canvas.thread_activity_notice_text = ""
    board_canvas.thread_activity_notice_expires_monotonic_s = 0.0
    board_canvas.current_hand_rect = None
    board_canvas.self_hand_bridge_click_specs = []
    board_canvas.hand_auto_mode_result_queue = queue.Queue()
    board_canvas.lag_marker_reference_kind = LAG_MARKER_REFERENCE_KIND_BLUE
    board_canvas.lag_marker_reference_kinds_by_entry = {}
    board_canvas.last_self_hand_value_alert_kind = HAND_SELF_ALERT_KIND_NONE
    board_canvas.last_self_low_ev_sound_round_token = ""
    board_canvas.last_self_hand_alert_sound_monotonic_s = 0.0
    board_canvas.last_player_panel_alert_keys_by_seat = {
        seat: tuple() for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    board_canvas.last_player_panel_remain_sound_level_by_seat = {
        seat: 0 for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    board_canvas.last_player_panel_alert_sound_monotonic_s = 0.0
    board_canvas.last_thread_activity_notice_redraw_monotonic_s = 0.0
    board_canvas.same_jun_match_cache_key = None
    board_canvas.same_jun_match_cache_value = {}
    board_canvas.same_jun_public_event_source_state = None
    board_canvas.same_jun_match_candidate_cache_key = None
    board_canvas.same_jun_match_candidate_cache_value = {}
    board_canvas.same_jun_match_candidate_event_stream = ()
    board_canvas.same_jun_match_candidate_recent_public_events = ()
    board_canvas.same_jun_match_confirmed_cache_key = None
    board_canvas.same_jun_match_confirmed_cache_value = {}
    board_canvas.same_jun_match_async_result_queue = queue.Queue()
    board_canvas.same_jun_match_async_in_flight = False
    board_canvas.same_jun_match_async_pending_key = None
    board_canvas.player_push_alert_latches_by_seat = {
        seat: _empty_player_push_alert_payload(seat)
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    board_canvas.player_push_marker_latches_by_seat = _empty_player_push_marker_indices_by_seat()
    board_canvas.current_player_alert_indicators_by_seat = current_player_alert_indicators_by_seat
    board_canvas.hand_recommendation_request_action = hand_recommendation_request_action
    board_canvas.hand_recommendation_reset_action = hand_recommendation_reset_action
    board_canvas.hand_recommendation_history_action = hand_recommendation_history_action
    board_canvas.hand_recommendation_panel_provider = hand_recommendation_panel_provider
    board_canvas.current_hand_recommendation_panel = current_hand_recommendation_panel
    board_canvas.current_recommendation_request_tiles = tuple()
    board_canvas.current_self_melds_for_hand_response = tuple()
    board_canvas.hand_response_render_state = None
    board_canvas.live_async_render_state = None
    board_canvas.table_snapshot_reinit_action = table_snapshot_reinit_action
    board_canvas.current_player_names_by_seat = current_player_names_by_seat
    board_canvas.current_ui_scale = 1.0
    board_canvas.discard_tint_base_prewarm_scale_keys = set()
    board_canvas.current_round_identity = round_identity
    board_canvas.current_refresh_token = refresh_token
    board_canvas.last_alert_audio_refresh_token = _ALERT_AUDIO_REFRESH_TOKEN_UNSET
    board_canvas.layout_tuning_settings = _load_layout_tuning_settings()
    board_canvas.layout_resolved_component_offsets = _normalize_component_offsets(
        board_canvas.layout_tuning_settings.component_offsets
    )
    board_canvas.layout_tuning_window = None
    board_canvas.layout_tuning_status_label = None
    board_canvas.layout_tuning_slider_vars = {}
    board_canvas.layout_tuning_value_labels = {}
    board_canvas.layout_drag_enabled = False
    board_canvas.layout_drag_state = None
    board_canvas.layout_drag_specs = []
    board_canvas.player_memo_presence_cache = {}
    board_canvas.player_memo_presence_pending_names = set()
    board_canvas.detail_memo_save_request_id = 0
    board_canvas.detail_memo_pending_request_ids = set()
    board_canvas.memo_background_task_queue = queue.Queue()
    board_canvas.memo_background_poll_job = None
    board_canvas.redraw_action = None
    board_canvas.redraw_request_pending = False
    board_canvas.redraw_in_progress = False
    board_canvas.last_redraw_started_monotonic_s = 0.0
    board_canvas.last_redraw_request_monotonic_s = 0.0
    board_canvas.last_redraw_finished_monotonic_s = 0.0
    board_canvas.last_completed_redraw_monotonic_s = 0.0
    board_canvas.last_auto_reinit_monotonic_s = 0.0
    board_canvas.last_auto_reinit_reason = None
    board_canvas.last_refresh_token_change_monotonic_s = time.monotonic()
    board_canvas.uncompleted_refresh_token_started_monotonic_s = 0.0
    board_canvas.last_completed_redraw_refresh_token = refresh_token
    board_canvas.redraw_watchdog_result_queue = queue.Queue()
    board_canvas.redraw_watchdog_stop_event = threading.Event()
    board_canvas.redraw_watchdog_thread = None
    board_canvas.refresh_watch_closed = False
    board_canvas.last_redraw_error_text = None
    board_canvas.last_slow_redraw_refresh_token = None
    board_canvas.last_full_redraw_notice_key = None
    board_canvas.last_redraw_phase_timings = ()
    board_canvas.last_render_table_phase_timings = ()
    board_canvas.last_render_layout_signature = None
    board_canvas.last_render_detail_content_rect = None
    board_canvas.side_panel_render_cache = None
    global _THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS
    _THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS = board_canvas
    _ensure_discard_tint_base_prewarm(
        board_canvas,
        float(_current_layout_tuning(board_canvas).discard_tile_scale),
    )

    # リサイズ連打時に再描画が過剰発火しないよう after ID を持つ。
    resize_job: str | None = None
    refresh_job: str | None = None
    watch_job: str | None = None
    redraw_job: str | None = None

    def schedule_refresh_watch() -> None:
        nonlocal watch_job
        if refresh_token_provider is None or refresh_watch_ms <= 0:
            return
        if bool(getattr(board_canvas, "refresh_watch_closed", False)):
            return
        if not board_canvas.winfo_exists():
            return
        try:
            watch_job = board_canvas.after(refresh_watch_ms, watch_refresh_token)
        except tkinter.TclError:
            watch_job = None

    def redraw() -> None:
        redraw_phase_timings: list[PhaseTiming] = []
        phase_started_at = time.perf_counter()
        if _inferred_visible_runtime_enabled(board_canvas):
            _drain_inferred_visible_background_result_queue(board_canvas)
        live_width = max(board_canvas.winfo_width(), WINDOW_MIN_WIDTH)
        live_height = max(board_canvas.winfo_height(), WINDOW_MIN_HEIGHT)
        ui_scale = _compute_ui_scale(
            live_width,
            board_canvas.winfo_screenwidth(),
        )
        scaled_image_table_cache: dict[float, TileImageTable] = getattr(
            board_canvas,
            "scaled_image_table_cache",
            {1.0: img_table},
        )
        active_image_table = scaled_image_table_cache.get(ui_scale)
        if active_image_table is None:
            active_image_table = initialize_image(root, tile_scale=ui_scale)
            scaled_image_table_cache[ui_scale] = active_image_table
            board_canvas.scaled_image_table_cache = scaled_image_table_cache
        if getattr(board_canvas, "current_ui_scale", 1.0) != ui_scale:
            board_canvas.thinking_tile_image_cache = {}
            board_canvas.hand_danger_tile_image_cache = {}
            board_canvas.hand_response_tile_image_cache = {}
            board_canvas.inferred_visible_tile_image_cache = {}
        board_canvas.current_ui_scale = ui_scale
        layout_tuning_settings = _current_layout_tuning(board_canvas)
        _ensure_discard_tint_base_prewarm(
            board_canvas,
            ui_scale * float(layout_tuning_settings.discard_tile_scale),
        )
        board_canvas.image_table = active_image_table
        _append_phase_timing(redraw_phase_timings, "ui_scale_setup", phase_started_at)
        phase_started_at = time.perf_counter()
        table_snapshot = table_snapshot_provider() if table_snapshot_provider is not None else None
        dynamic_discard_map = (
            table_snapshot.discard_map if table_snapshot is not None else discard_map
        )
        dynamic_hand_tiles = (
            list(table_snapshot.hand_tiles)
            if table_snapshot is not None
            else (
                list(hand_tiles_provider()) if hand_tiles_provider is not None else current_hand_tiles
            )
        )
        dynamic_hand_draw_tile = (
            table_snapshot.hand_draw_tile
            if table_snapshot is not None
            else (
                hand_draw_tile_provider()
                if hand_draw_tile_provider is not None
                else current_hand_draw_tile
            )
        )
        dynamic_round_identity = (
            table_snapshot.round_identity
            if table_snapshot is not None
            else (
                round_identity_provider()
                if round_identity_provider is not None
                else round_identity
            )
        )
        if table_snapshot is not None:
            board_canvas.bridge_snapshot_source_refresh_token = getattr(
                table_snapshot,
                "refresh_token",
                None,
            )
        if getattr(board_canvas, "current_round_identity", None) != dynamic_round_identity:
            _reset_round_ui_state(board_canvas)
            board_canvas.current_round_identity = dynamic_round_identity
        dynamic_melds_by_player = (
            _normalize_meld_map(table_snapshot.melds_by_player)
            if table_snapshot is not None
            else (
                _normalize_meld_map(melds_by_player_provider())
                if melds_by_player_provider is not None
                else current_melds_by_player
            )
        )
        dynamic_self_melds = list(dynamic_melds_by_player.get(Player.JICHA, ()))
        dynamic_hand_recommendation_request_context = (
            table_snapshot.hand_recommendation_request_context
            if table_snapshot is not None
            else (
                hand_recommendation_request_context_provider()
                if hand_recommendation_request_context_provider is not None
                else hand_recommendation_request_context
            )
        )
        if dynamic_hand_recommendation_request_context is None:
            dynamic_hand_recommendation_request_context = PystyleDisplayContext()
        recommendation_request_tiles = _build_hand_tiles_for_recommendation(
            dynamic_hand_tiles,
            dynamic_hand_draw_tile,
            fallback_tile_37=dynamic_hand_recommendation_request_context.request_fallback_tile_37,
        )
        recommendation_history_tiles = _build_hand_tiles_for_recommendation_history(
            dynamic_hand_tiles,
            dynamic_hand_draw_tile,
            dynamic_self_melds,
        )
        board_canvas.current_hand_tiles_for_response = list(recommendation_request_tiles)
        board_canvas.current_recommendation_request_tiles = tuple(
            int(tile) for tile in recommendation_request_tiles
        )
        board_canvas.current_hand_recommendation_request_context = dynamic_hand_recommendation_request_context
        board_canvas.current_self_melds_for_hand_response = tuple(dynamic_self_melds)
        dynamic_hand_recommendation_panel = (
            hand_recommendation_panel_provider()
            if hand_recommendation_panel_provider is not None
            else current_hand_recommendation_panel
        )
        board_canvas.current_hand_recommendation_panel = dynamic_hand_recommendation_panel
        hand_response_panel_visible = getattr(
            board_canvas,
            "hand_response_panel_state",
            HandResponsePanelState(),
        ).visible
        auto_mode_state = getattr(
            board_canvas,
            "hand_auto_mode_state",
            HandAutoModeState(),
        )
        auto_mode_enabled = auto_mode_state.enabled
        auto_mode_uses_recommendation = (
            auto_mode_enabled
            and str(getattr(auto_mode_state, "mode", HAND_AUTO_MODE_KIND_RECOMMENDATION))
            != HAND_AUTO_MODE_KIND_BETAORI
        )
        dynamic_hand_danger_percentages = (
            [
                _normalize_hand_danger_percentages(percentages)
                for percentages in table_snapshot.hand_danger_percentages
            ]
            if table_snapshot is not None
            else (
                [
                    _normalize_hand_danger_percentages(percentages)
                    for percentages in hand_danger_percentages_provider()
                ]
                if hand_danger_percentages_provider is not None
                else current_hand_danger_percentages
            )
        )
        recommendation_timeout_elapsed = False
        recommendation_error_fallback_active = False
        if hand_response_panel_visible or auto_mode_uses_recommendation:
            current_request_display_key = _hand_recommendation_request_display_key(
                recommendation_request_tiles,
                dynamic_hand_recommendation_request_context,
            )
            previous_requested_hand_key = getattr(
                board_canvas,
                "hand_response_requested_hand_key",
                None,
            )
            previous_request_started_monotonic_s = getattr(
                board_canvas,
                "hand_response_last_request_started_monotonic_s",
                None,
            )
            current_turn_started_monotonic_s = _sync_hand_recommendation_turn_timing(
                board_canvas,
                current_request_display_key,
            )
            recommendation_timeout_elapsed = auto_mode_uses_recommendation and _should_use_pystyle_timeout_fallback(
                recommendation_request_tiles,
                dynamic_hand_recommendation_panel,
                dynamic_hand_recommendation_request_context,
                current_request_display_key,
                previous_requested_hand_key,
                current_turn_started_monotonic_s,
                timeout_fallback_applied_turn_key=getattr(
                    board_canvas,
                    "hand_response_timeout_fallback_applied_turn_key",
                    None,
                ),
            )
            recommendation_error_fallback_active = (
                auto_mode_uses_recommendation
                and not recommendation_timeout_elapsed
                and _should_use_pystyle_error_fallback(
                    recommendation_request_tiles,
                    dynamic_hand_recommendation_panel,
                    dynamic_hand_recommendation_request_context,
                    current_request_display_key,
                    previous_requested_hand_key,
                    previous_request_started_monotonic_s,
                )
            )
            _restart_hand_recommendation_request_after_timeout(
                board_canvas,
                recommendation_request_tiles,
                dynamic_hand_recommendation_request_context,
                current_request_display_key,
                auto_mode_enabled=auto_mode_uses_recommendation,
                recommendation_timeout_elapsed=recommendation_timeout_elapsed,
            )
            _restart_hand_recommendation_request_after_error(
                board_canvas,
                recommendation_request_tiles,
                dynamic_hand_recommendation_request_context,
                current_request_display_key,
                auto_mode_enabled=auto_mode_uses_recommendation,
                recommendation_error_fallback_active=recommendation_error_fallback_active,
            )
            # The `AI TOP3` panel is toggle-driven. While hidden we do not issue new POST
            # requests; while visible or while Auto mode is enabled we request only when the
            # effective 14-tile hand actually changes. Post-discard fallback states reuse the
            # already-fetched pre-discard result.
            if _can_reuse_existing_hand_recommendation(
                recommendation_request_tiles,
                dynamic_hand_recommendation_panel,
                dynamic_hand_recommendation_request_context,
            ):
                board_canvas.hand_response_requested_hand_key = current_request_display_key
            elif (
                previous_requested_hand_key
                != current_request_display_key
                or _should_retry_hand_recommendation_for_auto(
                    recommendation_request_tiles,
                    dynamic_hand_recommendation_panel,
                    dynamic_hand_recommendation_request_context,
                    current_request_display_key,
                    previous_requested_hand_key,
                    previous_request_started_monotonic_s,
                    auto_mode_enabled=auto_mode_uses_recommendation,
                )
            ):
                request_action = getattr(board_canvas, "hand_recommendation_request_action", None)
                if request_action is not None and not (
                    recommendation_timeout_elapsed or recommendation_error_fallback_active
                ):
                    board_canvas.hand_response_requested_hand_key = current_request_display_key
                    board_canvas.hand_response_last_request_started_monotonic_s = time.monotonic()
                    request_action(
                        recommendation_request_tiles,
                        dynamic_hand_recommendation_request_context,
                    )
        _maybe_start_hand_auto_discard(
            board_canvas,
            recommendation_request_tiles,
            dynamic_hand_recommendation_panel,
            dynamic_hand_recommendation_request_context,
            dynamic_hand_danger_percentages,
            dynamic_self_melds,
            recommendation_timeout_elapsed=(
                recommendation_timeout_elapsed if (hand_response_panel_visible or auto_mode_uses_recommendation) else False
            ),
            recommendation_error_fallback_active=(
                recommendation_error_fallback_active
                if (hand_response_panel_visible or auto_mode_uses_recommendation)
                else False
            ),
        )
        if hand_response_panel_visible:
            history_action = getattr(board_canvas, "hand_recommendation_history_action", None)
            if history_action is not None and dynamic_hand_recommendation_panel.items:
                history_action(
                    recommendation_history_tiles,
                    dynamic_hand_recommendation_panel,
                    dynamic_hand_recommendation_request_context,
                )
        dynamic_opponent_suji_panel_summaries = (
            _normalize_opponent_suji_panel_summaries(table_snapshot.opponent_suji_panel_summaries)
            if table_snapshot is not None
            else (
                _normalize_opponent_suji_panel_summaries(opponent_suji_panel_summaries_provider())
                if opponent_suji_panel_summaries_provider is not None
                else current_opponent_suji_panel_summaries
            )
        )
        raw_player_push_alert_percentages = (
            _normalize_player_push_alert_percentages(table_snapshot.player_push_alert_percentages)
            if table_snapshot is not None
            else current_player_push_alert_percentages
        )
        latest_global_discard_index = _latest_global_discard_index_from_discard_map(
            dynamic_discard_map
        )
        push_marker_alert_percentages = _push_marker_alerts_for_render(
            raw_player_push_alert_percentages,
            getattr(board_canvas, "player_push_marker_latches_by_seat", {}),
            latest_global_discard_index,
        )
        board_canvas.player_push_marker_latches_by_seat = push_marker_alert_percentages
        dynamic_player_push_alert_percentages = _persist_player_push_alerts(
            raw_player_push_alert_percentages,
            getattr(board_canvas, "player_push_alert_latches_by_seat", {}),
            latest_global_discard_index,
        )
        board_canvas.player_push_alert_latches_by_seat = dynamic_player_push_alert_percentages
        dynamic_player_alert_indicators_by_seat = (
            _normalize_player_alert_indicators_by_seat(
                getattr(table_snapshot, "player_alert_indicators_by_seat", None)
            )
            if table_snapshot is not None
            else current_player_alert_indicators_by_seat
        )
        if (
            not dynamic_player_alert_indicators_by_seat
            or dynamic_player_push_alert_percentages != raw_player_push_alert_percentages
        ):
            dynamic_player_alert_indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
                dynamic_opponent_suji_panel_summaries,
                dynamic_player_push_alert_percentages,
            )
        dynamic_player_score_diffs_by_seat = (
            _normalize_player_score_diffs_by_seat(table_snapshot.player_score_diffs_by_seat)
            if table_snapshot is not None
            else current_player_score_diffs_by_seat
        )
        dynamic_discard_red_tint_indices_by_seat = (
            _normalize_discard_red_tint_indices_by_seat(
                table_snapshot.discard_red_tint_indices_by_seat
            )
            if table_snapshot is not None
            else current_discard_red_tint_indices_by_seat
        )
        dynamic_player_names_by_seat = (
            _normalize_player_names_by_seat(table_snapshot.player_names_by_seat)
            if table_snapshot is not None
            else (
                _normalize_player_names_by_seat(player_names_by_seat_provider())
                if player_names_by_seat_provider is not None
                else current_player_names_by_seat
            )
        )
        _request_player_memo_presence_prefetch(
            board_canvas,
            dynamic_player_names_by_seat.values(),
        )
        dynamic_meld_tiles = (
            list(table_snapshot.meld_tiles)
            if table_snapshot is not None
            else (list(meld_tiles_provider()) if meld_tiles_provider is not None else current_meld_tiles)
        )
        dynamic_dora_indicator_tiles = (
            list(table_snapshot.dora_indicator_tiles)
            if table_snapshot is not None
            else (
                list(dora_indicator_tiles_provider())
                if dora_indicator_tiles_provider is not None
                else current_dora_indicator_tiles
            )
        )
        dynamic_round_info_panel = (
            table_snapshot.round_info_panel
            if table_snapshot is not None
            else (
                round_info_panel_provider()
                if round_info_panel_provider is not None
                else current_round_info_panel
            )
        )
        dynamic_round_events = (
            list(getattr(table_snapshot, "round_events", ()))
            if table_snapshot is not None and AWASEUCHI_MARKERS_ENABLED
            else []
        )
        dynamic_visible_summary = (
            table_snapshot.visible_summary
            if table_snapshot is not None
            else (
                visible_summary_provider()
                if visible_summary_provider is not None
                else visible_summary
            )
        )
        dynamic_self_hand_value_alert = _build_self_hand_value_alert_state(
            dynamic_hand_recommendation_panel,
            recommendation_request_tiles,
            dynamic_round_identity,
            dynamic_self_melds,
        )
        _append_phase_timing(redraw_phase_timings, "state_prepare", phase_started_at)
        phase_started_at = time.perf_counter()
        if _should_evaluate_alert_audio_for_refresh_token(
            board_canvas,
            getattr(board_canvas, "current_refresh_token", None),
        ):
            _play_self_hand_value_alert_sound_if_needed(
                board_canvas,
                dynamic_self_hand_value_alert,
            )
            _play_player_panel_alert_sound_if_needed(
                board_canvas,
                dynamic_opponent_suji_panel_summaries,
                dynamic_player_push_alert_percentages,
                alert_indicators_by_seat=dynamic_player_alert_indicators_by_seat,
            )
        _append_phase_timing(redraw_phase_timings, "alert_audio", phase_started_at)
        phase_started_at = time.perf_counter()
        board_canvas.current_player_names_by_seat = dynamic_player_names_by_seat
        board_canvas.current_player_alert_indicators_by_seat = dynamic_player_alert_indicators_by_seat
        _refresh_hand_auto_mode_button_widget(board_canvas)
        current_layout_signature = _build_layout_signature(
            board_canvas,
            ui_scale=ui_scale,
            layout_tuning=layout_tuning_settings,
        )
        detail_content_rect: tuple[float, float, float, float]
        reused_cached_layout = False
        full_redraw_reason = _cached_layout_skip_reason(
            board_canvas,
            current_layout_signature,
        )
        if full_redraw_reason is None:
            reused_cached_layout, detail_content_rect = _render_table_using_cached_layout_if_possible(
                board_canvas,
                active_image_table,
                dynamic_discard_map,
                dynamic_hand_tiles,
                dynamic_hand_draw_tile,
                dynamic_hand_recommendation_panel,
                dynamic_hand_danger_percentages,
                dynamic_opponent_suji_panel_summaries,
                dynamic_player_push_alert_percentages,
                push_marker_alert_percentages,
                dynamic_player_alert_indicators_by_seat,
                dynamic_player_score_diffs_by_seat,
                dynamic_discard_red_tint_indices_by_seat,
                dynamic_player_names_by_seat,
                dynamic_meld_tiles,
                dynamic_dora_indicator_tiles,
                dynamic_round_events,
                dynamic_round_info_panel,
                dynamic_melds_by_player,
                dynamic_visible_summary,
                dynamic_self_hand_value_alert,
            )
            if not reused_cached_layout:
                full_redraw_reason = (
                    _cached_layout_runtime_guard_reason(board_canvas)
                    or _cached_layout_skip_reason(board_canvas, current_layout_signature)
                    or "cached_layout_reuse_failed_after_precheck"
                )
        if not reused_cached_layout:
            _log_full_redraw_reason(board_canvas, str(full_redraw_reason or "unknown"))
            # 現在の牌状態を使って盤面全体を描き直す。
            detail_content_rect = _render_table(
                board_canvas,
                active_image_table,
                dynamic_discard_map,
                dynamic_hand_tiles,
                dynamic_hand_draw_tile,
                dynamic_hand_recommendation_panel,
                dynamic_hand_danger_percentages,
                dynamic_opponent_suji_panel_summaries,
                dynamic_player_push_alert_percentages,
                push_marker_alert_percentages,
                dynamic_player_alert_indicators_by_seat,
                dynamic_player_score_diffs_by_seat,
                dynamic_discard_red_tint_indices_by_seat,
                dynamic_player_names_by_seat,
                dynamic_meld_tiles,
                dynamic_dora_indicator_tiles,
                dynamic_round_events,
                dynamic_round_info_panel,
                dynamic_melds_by_player,
                dynamic_visible_summary,
                dynamic_self_hand_value_alert,
                ui_scale=ui_scale,
                layout_tuning=layout_tuning_settings,
            )
        _append_phase_timing(redraw_phase_timings, "render_table", phase_started_at)
        phase_started_at = time.perf_counter()
        _draw_thread_activity_notice(board_canvas)
        _update_detail_overlay(board_canvas, detail_content_rect)
        _place_inferred_visible_tile_panel_button(board_canvas)
        _place_bridge_toggle_controls_frame(board_canvas)
        _place_bridge_action_controls_frame(board_canvas)
        _append_phase_timing(redraw_phase_timings, "overlay", phase_started_at)
        live_async_layout = getattr(board_canvas, "last_render_layout", None)
        if isinstance(live_async_layout, dict):
            board_canvas.live_async_render_state = LiveAsyncRenderState(
                layout=live_async_layout,
                discard_map={
                    player: list(dynamic_discard_map.get(player, ()))
                    for player in Player
                },
                melds_by_player={
                    player: list(dynamic_melds_by_player.get(player, ()))
                    for player in Player
                },
                dora_indicator_tiles=tuple(int(tile) for tile in dynamic_dora_indicator_tiles),
                visible_summary=dynamic_visible_summary,
                hand_tiles=tuple(int(tile) for tile in dynamic_hand_tiles),
                hand_draw_tile=(
                    int(dynamic_hand_draw_tile)
                    if dynamic_hand_draw_tile is not None
                    else None
                ),
                hand_recommendation_panel=dynamic_hand_recommendation_panel,
                player_score_diffs_by_seat=dict(dynamic_player_score_diffs_by_seat),
                player_names_by_seat=dict(dynamic_player_names_by_seat),
                round_events=tuple(dynamic_round_events),
                self_hand_value_alert=dynamic_self_hand_value_alert,
            )
        board_canvas.last_redraw_phase_timings = tuple(redraw_phase_timings)

    def _run_redraw_safely() -> None:
        redraw_started_at = time.perf_counter()
        redraw_started_monotonic_s = time.monotonic()
        board_canvas.redraw_request_pending = False
        board_canvas.redraw_in_progress = True
        board_canvas.last_redraw_started_monotonic_s = redraw_started_monotonic_s
        try:
            redraw()
            board_canvas.last_redraw_error_text = None
        except Exception as exc:  # noqa: BLE001 - UI refresh must keep rescheduling on transient failures.
            error_text = f"{type(exc).__name__}: {exc}"
            if getattr(board_canvas, "last_redraw_error_text", None) != error_text:
                print(f"UI redraw skipped: {error_text}")
                board_canvas.last_redraw_error_text = error_text
        else:
            elapsed_ms = (time.perf_counter() - redraw_started_at) * 1000.0
            current_refresh_token = getattr(board_canvas, "current_refresh_token", None)
            _mark_ui_refresh_completed(
                board_canvas,
                refresh_token=current_refresh_token,
                completed_monotonic_s=time.monotonic(),
            )
            if (
                elapsed_ms >= SLOW_REDRAW_LOG_THRESHOLD_MS
                and getattr(board_canvas, "last_slow_redraw_refresh_token", None) != current_refresh_token
            ):
                board_canvas.last_slow_redraw_refresh_token = current_refresh_token
                redraw_breakdown = _format_phase_timing_breakdown(
                    getattr(board_canvas, "last_redraw_phase_timings", ()),
                )
                render_breakdown = _format_phase_timing_breakdown(
                    getattr(board_canvas, "last_render_table_phase_timings", ()),
                )
                print(
                    "UI redraw slow: "
                    f"{elapsed_ms:.1f}ms refresh_token={current_refresh_token}"
                    + (f" redraw=[{redraw_breakdown}]" if redraw_breakdown else "")
                    + (f" render=[{render_breakdown}]" if render_breakdown else "")
                )
        finally:
            board_canvas.last_redraw_finished_monotonic_s = time.monotonic()
            board_canvas.redraw_in_progress = False

    def request_redraw(*, delay_ms: int = 0, replace_pending: bool = False) -> None:
        nonlocal redraw_job
        if not board_canvas.winfo_exists():
            return
        if redraw_job is not None:
            if not replace_pending:
                return
            try:
                board_canvas.after_cancel(redraw_job)
            except tkinter.TclError:
                redraw_job = None
            else:
                redraw_job = None
            board_canvas.redraw_request_pending = False

        def _run_requested_redraw() -> None:
            nonlocal redraw_job
            redraw_job = None
            board_canvas.redraw_request_pending = False
            if not board_canvas.winfo_exists():
                return
            if bool(getattr(board_canvas, "redraw_in_progress", False)):
                request_redraw(delay_ms=16)
                return
            _run_redraw_safely()

        try:
            if int(delay_ms) > 0:
                redraw_job = board_canvas.after(int(delay_ms), _run_requested_redraw)
            else:
                redraw_job = board_canvas.after_idle(_run_requested_redraw)
            board_canvas.redraw_request_pending = True
            board_canvas.last_redraw_request_monotonic_s = time.monotonic()
        except tkinter.TclError:
            redraw_job = None
            board_canvas.redraw_request_pending = False

    def schedule_redraw(_event: tkinter.Event) -> None:
        nonlocal resize_job
        # 直前の再描画予約があればキャンセルし、最後のイベントだけ反映する。
        if resize_job is not None:
            try:
                board_canvas.after_cancel(resize_job)
            except tkinter.TclError:
                pass

        def _flush_resize_redraw() -> None:
            nonlocal resize_job
            resize_job = None
            request_redraw(replace_pending=True)

        resize_job = board_canvas.after(16, _flush_resize_redraw)

    def schedule_auto_refresh() -> None:
        nonlocal refresh_job
        request_redraw()
        if auto_refresh_ms is not None:
            refresh_job = board_canvas.after(auto_refresh_ms, schedule_auto_refresh)

    def watch_refresh_token() -> None:
        nonlocal watch_job
        watch_job = None
        schedule_refresh_watch()
        now_monotonic = time.monotonic()
        queue_changed = _drain_hand_auto_mode_result_queue(board_canvas)
        queue_changed = (
            _drain_redraw_watchdog_result_queue(
                board_canvas,
                now_monotonic=now_monotonic,
                request_redraw=request_redraw,
                table_snapshot_reinit_action=table_snapshot_reinit_action,
            )
            or queue_changed
        )
        if _inferred_visible_runtime_enabled(board_canvas):
            queue_changed = _drain_inferred_visible_background_result_queue(board_canvas) or queue_changed
        if AWASEUCHI_MARKERS_ENABLED:
            queue_changed = _drain_same_jun_match_background_result_queue(board_canvas) or queue_changed
        if refresh_token_provider is not None:
            try:
                next_refresh_token = refresh_token_provider()
            except Exception as exc:  # noqa: BLE001 - token polling must survive transient provider failures.
                error_text = f"{type(exc).__name__}: {exc}"
                if getattr(board_canvas, "last_redraw_error_text", None) != error_text:
                    print(f"UI refresh-token poll skipped: {error_text}")
                    board_canvas.last_redraw_error_text = error_text
            else:
                previous_refresh_token = getattr(board_canvas, "current_refresh_token", None)
                if previous_refresh_token != next_refresh_token:
                    board_canvas.current_refresh_token = next_refresh_token
                    board_canvas.last_refresh_token_change_monotonic_s = now_monotonic
                    if (
                        _should_use_hand_response_only_refresh(
                            previous_refresh_token,
                            next_refresh_token,
                        )
                        and _redraw_hand_response_controls_if_possible(board_canvas)
                    ):
                        _mark_ui_refresh_completed(
                            board_canvas,
                            refresh_token=next_refresh_token,
                            completed_monotonic_s=now_monotonic,
                        )
                    elif (
                        _should_use_live_async_only_refresh(
                            previous_refresh_token,
                            next_refresh_token,
                        )
                        and table_snapshot_provider is not None
                    ):
                        try:
                            partial_snapshot = table_snapshot_provider()
                        except Exception as exc:  # noqa: BLE001 - partial refresh should fall back to full redraw.
                            error_text = f"{type(exc).__name__}: {exc}"
                            if getattr(board_canvas, "last_redraw_error_text", None) != error_text:
                                print(f"UI live-async partial refresh skipped: {error_text}")
                                board_canvas.last_redraw_error_text = error_text
                            request_redraw()
                            queue_changed = False
                            return
                        dynamic_hand_danger_percentages = [
                            _normalize_hand_danger_percentages(percentages)
                            for percentages in getattr(partial_snapshot, "hand_danger_percentages", ())
                        ]
                        dynamic_opponent_suji_panel_summaries = _normalize_opponent_suji_panel_summaries(
                            getattr(partial_snapshot, "opponent_suji_panel_summaries", {})
                        )
                        raw_player_push_alert_percentages = _normalize_player_push_alert_percentages(
                            getattr(partial_snapshot, "player_push_alert_percentages", {})
                        )
                        latest_global_discard_index = _latest_global_discard_index_from_discard_map(
                            getattr(partial_snapshot, "discard_map", {})
                        )
                        push_marker_alert_percentages = _push_marker_alerts_for_render(
                            raw_player_push_alert_percentages,
                            getattr(board_canvas, "player_push_marker_latches_by_seat", {}),
                            latest_global_discard_index,
                        )
                        board_canvas.player_push_marker_latches_by_seat = (
                            push_marker_alert_percentages
                        )
                        dynamic_player_push_alert_percentages = _persist_player_push_alerts(
                            raw_player_push_alert_percentages,
                            getattr(board_canvas, "player_push_alert_latches_by_seat", {}),
                            latest_global_discard_index,
                        )
                        board_canvas.player_push_alert_latches_by_seat = (
                            dynamic_player_push_alert_percentages
                        )
                        dynamic_player_alert_indicators_by_seat = _normalize_player_alert_indicators_by_seat(
                            getattr(partial_snapshot, "player_alert_indicators_by_seat", {})
                        )
                        if (
                            not dynamic_player_alert_indicators_by_seat
                            or dynamic_player_push_alert_percentages
                            != raw_player_push_alert_percentages
                        ):
                            dynamic_player_alert_indicators_by_seat = (
                                _build_player_panel_alert_indicators_by_seat(
                                    dynamic_opponent_suji_panel_summaries,
                                    dynamic_player_push_alert_percentages,
                                )
                            )
                        if _should_evaluate_alert_audio_for_refresh_token(
                            board_canvas,
                            next_refresh_token,
                        ):
                            _play_player_panel_alert_sound_if_needed(
                                board_canvas,
                                dynamic_opponent_suji_panel_summaries,
                                dynamic_player_push_alert_percentages,
                                alert_indicators_by_seat=dynamic_player_alert_indicators_by_seat,
                            )
                        if not _redraw_live_async_regions_if_possible(
                            board_canvas,
                            hand_danger_percentages=dynamic_hand_danger_percentages,
                            opponent_suji_panel_summaries=dynamic_opponent_suji_panel_summaries,
                            player_push_alert_percentages=dynamic_player_push_alert_percentages,
                            push_marker_alert_percentages=push_marker_alert_percentages,
                            player_alert_indicators_by_seat=dynamic_player_alert_indicators_by_seat,
                            discard_red_tint_indices_by_seat=_normalize_discard_red_tint_indices_by_seat(
                                getattr(partial_snapshot, "discard_red_tint_indices_by_seat", {})
                            ),
                        ):
                            request_redraw()
                        else:
                            _mark_ui_refresh_completed(
                                board_canvas,
                                refresh_token=next_refresh_token,
                                completed_monotonic_s=now_monotonic,
                            )
                    else:
                        request_redraw()
                    queue_changed = False
        auto_reinit_reason = _maybe_auto_force_ui_reinit(
            board_canvas,
            now_monotonic=now_monotonic,
            request_redraw=request_redraw,
            table_snapshot_reinit_action=table_snapshot_reinit_action,
        )
        if auto_reinit_reason is not None:
            queue_changed = False
        if queue_changed:
            _refresh_hand_auto_mode_button_widget(board_canvas)
            request_redraw()

    def handle_canvas_press(event: tkinter.Event) -> None:
        if getattr(board_canvas, "layout_drag_enabled", False) and _start_layout_component_drag(
            board_canvas,
            event.x,
            event.y,
        ):
            request_redraw()
            return
        if (
            _handle_lag_marker_reference_button_click(board_canvas, event.x, event.y)
            or _handle_table_situation_cell_click(board_canvas, event.x, event.y)
            or _handle_inferred_visible_manual_count_button_click(board_canvas, event.x, event.y)
            or _handle_inferred_visible_tile_count_click(board_canvas, event.x, event.y)
            or _handle_selected_inferred_visible_delete_button_click(board_canvas, event.x, event.y)
            or _handle_inferred_visible_delete_button_click(board_canvas, event.x, event.y)
            or _handle_inferred_visible_candidate_button_click(board_canvas, event.x, event.y)
            or _handle_player_panel_button_click(board_canvas, event.x, event.y)
            or _handle_hand_response_button_click(board_canvas, event.x, event.y)
            or _handle_hand_betaori_response_button_click(board_canvas, event.x, event.y)
            or _handle_self_hand_bridge_click(board_canvas, event.x, event.y)
            or _handle_discard_tile_selection_click(board_canvas, event.x, event.y)
        ):
            request_redraw()
            return

    def handle_global_primary_press(event: tkinter.Event) -> None:
        _close_inferred_visible_tile_selector_window_for_external_click(
            board_canvas,
            getattr(event, "widget", None),
        )

    def handle_canvas_double_press(event: tkinter.Event) -> None:
        if _handle_inferred_visible_candidate_button_double_click(board_canvas, event.x, event.y):
            request_redraw()
            return

    def handle_canvas_secondary_press(event: tkinter.Event) -> None:
        if _handle_table_situation_cell_secondary_click(board_canvas, event.x, event.y):
            request_redraw()
            return
        if _handle_bridge_secondary_click(board_canvas):
            request_redraw()
            return

    def handle_canvas_drag(event: tkinter.Event) -> None:
        if _update_layout_component_drag(board_canvas, event.x, event.y):
            request_redraw()

    def handle_canvas_release(_event: tkinter.Event) -> None:
        if _finish_layout_component_drag(board_canvas):
            request_redraw()

    def handle_window_close() -> None:
        nonlocal resize_job, refresh_job, watch_job, redraw_job
        global _THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS
        _save_detail_memo_if_needed(board_canvas)
        board_canvas.refresh_watch_closed = True
        board_canvas.bridge_status_tick_closed = True
        redraw_watchdog_stop_event = getattr(board_canvas, "redraw_watchdog_stop_event", None)
        if isinstance(redraw_watchdog_stop_event, threading.Event):
            redraw_watchdog_stop_event.set()
        if resize_job is not None:
            board_canvas.after_cancel(resize_job)
            resize_job = None
        if refresh_job is not None:
            board_canvas.after_cancel(refresh_job)
            refresh_job = None
        if watch_job is not None:
            board_canvas.after_cancel(watch_job)
            watch_job = None
        if redraw_job is not None:
            board_canvas.after_cancel(redraw_job)
            redraw_job = None
        memo_background_poll_job = getattr(board_canvas, "memo_background_poll_job", None)
        if memo_background_poll_job is not None:
            board_canvas.after_cancel(memo_background_poll_job)
            board_canvas.memo_background_poll_job = None
        bridge_status_tick_job = getattr(board_canvas, "bridge_status_tick_job", None)
        if bridge_status_tick_job is not None:
            board_canvas.after_cancel(bridge_status_tick_job)
            board_canvas.bridge_status_tick_job = None
        inferred_visible_tile_selector_window = getattr(
            board_canvas,
            "inferred_visible_tile_selector_window",
            None,
        )
        if inferred_visible_tile_selector_window is not None and inferred_visible_tile_selector_window.winfo_exists():
            inferred_visible_tile_selector_window.destroy()
            board_canvas.inferred_visible_tile_selector_window = None
        inferred_visible_request_queue = getattr(board_canvas, "inferred_visible_async_request_queue", None)
        if inferred_visible_request_queue is not None:
            try:
                inferred_visible_request_queue.put_nowait(_INFERRED_VISIBLE_WORKER_STOP)
            except Exception:
                pass
        tuning_window = getattr(board_canvas, "layout_tuning_window", None)
        if tuning_window is not None and tuning_window.winfo_exists():
            tuning_window.destroy()
        tenhou_ui_bridge_server = getattr(root, "tenhou_ui_bridge_server", None)
        if tenhou_ui_bridge_server is not None:
            try:
                tenhou_ui_bridge_server.close()
            except Exception:
                pass
        if _THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS is board_canvas:
            _THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS = None
        root.destroy()

    def handle_layout_window_open(_event: tkinter.Event | None = None) -> str:
        open_layout_tuning_window(root, board_canvas, request_redraw)
        return "break"

    def _set_hand_auto_mode(next_enabled: bool, next_mode: str) -> None:
        board_canvas.hand_auto_mode_state = HandAutoModeState(
            enabled=next_enabled,
            mode=next_mode,
        )
        board_canvas.hand_response_panel_state = _resolve_hand_response_panel_state_for_auto_mode(
            getattr(board_canvas, "hand_response_panel_state", None),
            auto_mode_enabled=next_enabled,
            auto_mode=next_mode,
        )
        board_canvas.hand_response_requested_hand_key = None
        board_canvas.hand_response_last_request_started_monotonic_s = None
        _refresh_hand_auto_mode_button_widget(board_canvas)
        request_redraw()

    def handle_pystyle_auto_mode_toggle() -> None:
        current_state = getattr(board_canvas, "hand_auto_mode_state", HandAutoModeState())
        is_current = bool(current_state.enabled) and (
            str(getattr(current_state, "mode", HAND_AUTO_MODE_KIND_RECOMMENDATION))
            == HAND_AUTO_MODE_KIND_RECOMMENDATION
        )
        _set_hand_auto_mode(not is_current, HAND_AUTO_MODE_KIND_RECOMMENDATION)

    def handle_betaori_auto_mode_toggle() -> None:
        current_state = getattr(board_canvas, "hand_auto_mode_state", HandAutoModeState())
        is_current = bool(current_state.enabled) and (
            str(getattr(current_state, "mode", HAND_AUTO_MODE_KIND_RECOMMENDATION))
            == HAND_AUTO_MODE_KIND_BETAORI
        )
        _set_hand_auto_mode(not is_current, HAND_AUTO_MODE_KIND_BETAORI)

    def handle_inferred_visible_tile_panel_toggle() -> None:
        if not _inferred_visible_runtime_enabled(board_canvas):
            return
        _toggle_inferred_visible_tile_selector_window(root, board_canvas)

    def handle_table_situation_visibility_toggle() -> None:
        if not TABLE_SITUATION_ENABLED:
            return
        board_canvas.table_situation_panels_visible = not bool(
            getattr(board_canvas, "table_situation_panels_visible", True)
        )
        _refresh_table_situation_visibility_button_widget(board_canvas)
        request_redraw()

    def handle_force_capture_reinit() -> None:
        reason = _force_manual_ui_reinit(
            board_canvas,
            request_redraw=request_redraw,
            table_snapshot_reinit_action=table_snapshot_reinit_action,
        )
        _log_manual_ui_reinit(board_canvas, reason)

    # ウィンドウサイズ変更に追従してレイアウトを引き直す。
    board_canvas.redraw_action = request_redraw
    board_canvas.bind("<Configure>", schedule_redraw)
    board_canvas.bind("<Button-1>", handle_canvas_press)
    board_canvas.bind("<Double-Button-1>", handle_canvas_double_press)
    board_canvas.bind("<Button-3>", handle_canvas_secondary_press)
    board_canvas.bind("<B1-Motion>", handle_canvas_drag)
    board_canvas.bind("<ButtonRelease-1>", handle_canvas_release)
    root.bind_all("<Button-1>", handle_global_primary_press, add="+")
    layout_button = tkinter.Button(
        root,
        text="LAYOUT",
        command=handle_layout_window_open,
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
    )
    layout_button.place(x=LAYOUT_BUTTON_X, y=LAYOUT_BUTTON_Y)
    board_canvas.layout_button = layout_button
    if TABLE_SITUATION_ENABLED:
        table_situation_visibility_button = tkinter.Button(
            root,
            text="場況 ON",
            command=handle_table_situation_visibility_toggle,
            relief=tkinter.FLAT,
            bd=1,
            bg=HAND_AUTO_BUTTON_ON_FILL,
            fg=HAND_AUTO_BUTTON_TEXT,
            activebackground=HAND_AUTO_BUTTON_ON_FILL,
            activeforeground=HAND_AUTO_BUTTON_TEXT,
            font=("Consolas", 8, "bold"),
            padx=8,
            pady=2,
            highlightthickness=0,
            width=9,
        )
        table_situation_visibility_button.place(
            x=TABLE_SITUATION_VISIBILITY_BUTTON_X,
            y=TABLE_SITUATION_VISIBILITY_BUTTON_Y,
        )
        board_canvas.table_situation_visibility_button = table_situation_visibility_button
    else:
        board_canvas.table_situation_visibility_button = None
    if table_snapshot_reinit_action is not None:
        force_capture_reinit_button = tkinter.Button(
            root,
            text="REINIT",
            command=handle_force_capture_reinit,
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
            width=9,
        )
        force_capture_reinit_button.place(
            x=FORCE_CAPTURE_REINIT_BUTTON_X,
            y=FORCE_CAPTURE_REINIT_BUTTON_Y,
        )
        board_canvas.force_capture_reinit_button = force_capture_reinit_button
    else:
        board_canvas.force_capture_reinit_button = None
    pystyle_auto_mode_button = tkinter.Button(
        root,
        text="pystyle OFF",
        command=handle_pystyle_auto_mode_toggle,
        relief=tkinter.FLAT,
        bd=1,
        bg=HAND_AUTO_BUTTON_OFF_FILL,
        fg=HAND_AUTO_BUTTON_TEXT,
        activebackground=HAND_AUTO_BUTTON_OFF_FILL,
        activeforeground=HAND_AUTO_BUTTON_TEXT,
        font=("Consolas", 8, "bold"),
        padx=8,
        pady=2,
        highlightthickness=0,
        width=10,
    )
    pystyle_auto_mode_button.place(x=PYSTYLE_AUTO_BUTTON_X, y=PYSTYLE_AUTO_BUTTON_Y)
    betaori_auto_mode_button = tkinter.Button(
        root,
        text="ベタオリ OFF",
        command=handle_betaori_auto_mode_toggle,
        relief=tkinter.FLAT,
        bd=1,
        bg=HAND_AUTO_BUTTON_OFF_FILL,
        fg=HAND_AUTO_BUTTON_TEXT,
        activebackground=HAND_AUTO_BUTTON_OFF_FILL,
        activeforeground=HAND_AUTO_BUTTON_TEXT,
        font=("Consolas", 8, "bold"),
        padx=8,
        pady=2,
        highlightthickness=0,
        width=10,
    )
    betaori_auto_mode_button.place(x=BETAORI_AUTO_BUTTON_X, y=BETAORI_AUTO_BUTTON_Y)
    board_canvas.hand_pystyle_auto_mode_button = pystyle_auto_mode_button
    board_canvas.hand_betaori_auto_mode_button = betaori_auto_mode_button
    _refresh_hand_auto_mode_button_widget(board_canvas)
    _refresh_table_situation_visibility_button_widget(board_canvas)
    if _inferred_visible_runtime_enabled(board_canvas):
        inferred_visible_tile_panel_button = tkinter.Button(
            root,
            text="牌パネル",
            command=handle_inferred_visible_tile_panel_toggle,
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
        inferred_visible_tile_panel_button.place_forget()
        board_canvas.inferred_visible_tile_panel_button = inferred_visible_tile_panel_button
    else:
        board_canvas.inferred_visible_tile_panel_button = None
    bridge_frame = tkinter.Frame(root, bg="#0f1722", highlightthickness=0, bd=0)
    bridge_frame.place(x=PYSTYLE_AUTO_BUTTON_X + 106, y=6)
    bridge_status_label = tkinter.Label(
        bridge_frame,
        text="Bridge N/A",
        bg="#3a4250",
        fg="#9aa4b5",
        font=("Consolas", 8, "bold"),
        padx=8,
        pady=3,
        anchor=tkinter.W,
    )
    bridge_status_label.pack(side=tkinter.TOP, anchor="w")
    bridge_actions_row = tkinter.Frame(bridge_frame, bg="#0f1722", highlightthickness=0, bd=0)
    bridge_actions_row.pack(side=tkinter.TOP, anchor="w", pady=(4, 0))
    bridge_refresh_button = tkinter.Button(
        bridge_actions_row,
        text="SYNC",
        command=lambda: _request_bridge_ui_snapshot(board_canvas, force=True),
        relief=tkinter.FLAT,
        bd=1,
        bg="#16202c",
        fg="#d7deea",
        activebackground="#29415d",
        activeforeground="#f8fafc",
        disabledforeground="#6b7280",
        font=("Consolas", 7, "bold"),
        padx=6,
        pady=1,
        highlightthickness=0,
    )
    bridge_refresh_button.pack(side=tkinter.LEFT, padx=(0, 6))
    bridge_map_button = tkinter.Button(
        bridge_actions_row,
        text="MAP",
        command=lambda: _request_bridge_table_snapshot(board_canvas),
        relief=tkinter.FLAT,
        bd=1,
        bg="#16202c",
        fg="#d7deea",
        activebackground="#29415d",
        activeforeground="#f8fafc",
        disabledforeground="#6b7280",
        font=("Consolas", 7, "bold"),
        padx=6,
        pady=1,
        highlightthickness=0,
    )
    bridge_map_button.pack(side=tkinter.LEFT)
    bridge_action_controls_frame = tkinter.Frame(root, bg="#0f1722", highlightthickness=0, bd=0)
    bridge_toggle_controls_frame = tkinter.Frame(root, bg="#0f1722", highlightthickness=0, bd=0)
    bridge_controls_frame = tkinter.Frame(bridge_frame, bg="#0f1722", highlightthickness=0, bd=0)
    bridge_controls_frame.pack(side=tkinter.TOP, anchor="w", pady=(4, 0))
    bridge_controls_empty_label = tkinter.Label(
        bridge_controls_frame,
        text="No controls",
        bg="#0f1722",
        fg="#8ea0b6",
        font=("Consolas", 7),
        padx=2,
        pady=1,
        anchor=tkinter.W,
    )
    board_canvas.bridge_frame = bridge_frame
    board_canvas.bridge_status_label_widget = bridge_status_label
    board_canvas.bridge_refresh_button = bridge_refresh_button
    board_canvas.bridge_map_button = bridge_map_button
    board_canvas.bridge_toggle_controls_frame = bridge_toggle_controls_frame
    board_canvas.bridge_action_controls_frame = bridge_action_controls_frame
    board_canvas.bridge_controls_frame = bridge_controls_frame
    board_canvas.bridge_controls_empty_label = bridge_controls_empty_label
    _place_bridge_toggle_controls_frame(board_canvas)
    _refresh_bridge_widgets(board_canvas)
    if (
        callable(getattr(board_canvas, "bridge_status_provider", None))
        or callable(getattr(board_canvas, "bridge_ui_snapshot_action", None))
        or callable(getattr(board_canvas, "bridge_table_snapshot_action", None))
    ):
        _schedule_bridge_status_tick(board_canvas)
    root.bind_all("<Control-Shift-L>", handle_layout_window_open)
    root.bind_all("<Control-Shift-l>", handle_layout_window_open)
    root.protocol("WM_DELETE_WINDOW", handle_window_close)
    if _inferred_visible_runtime_enabled(board_canvas):
        _ensure_inferred_visible_background_worker(board_canvas)
    if table_snapshot_reinit_action is not None:
        _start_redraw_watchdog_thread(board_canvas)
    _run_redraw_safely()
    if auto_refresh_ms is not None:
        refresh_job = board_canvas.after(auto_refresh_ms, schedule_auto_refresh)
    if refresh_token_provider is not None and refresh_watch_ms > 0:
        schedule_refresh_watch()
    root.mainloop()


def _format_layout_tuning_value(field_name: str, value: int | float) -> str:
    """Format one tuning value for the slider-side value label."""

    control = LAYOUT_TUNING_CONTROL_BY_FIELD[field_name]
    if control.resolution >= 1:
        return str(int(round(float(value))))
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def open_layout_tuning_window(
    root: tkinter.Tk,
    canvas: tkinter.Canvas,
    redraw: Callable[[], None],
) -> None:
    """Open or focus the shared non-modal layout tuning window."""

    existing_window = getattr(canvas, "layout_tuning_window", None)
    if existing_window is not None and existing_window.winfo_exists():
        canvas.layout_drag_enabled = True
        existing_window.deiconify()
        existing_window.lift()
        existing_window.focus_force()
        redraw()
        return

    window = tkinter.Toplevel(root)
    window.title("Layout Tuning")
    window.configure(bg=BOARD_OUTER)
    window.resizable(True, True)
    canvas.layout_tuning_window = window
    canvas.layout_drag_enabled = True

    container = tkinter.Frame(window, bg=BOARD_OUTER, padx=12, pady=12)
    container.pack(fill=tkinter.BOTH, expand=True)

    description = tkinter.Label(
        container,
        text=(
            "Adjust the main table rectangles here. Slider changes redraw immediately. "
            "While this window is open, you can also drag PANEL / DISCARD / MELD rectangles and the AI TOP3 button directly on the table."
        ),
        anchor=tkinter.W,
        justify=tkinter.LEFT,
        bg=BOARD_OUTER,
        fg=TEXT_SECONDARY,
        font=("Yu Gothic UI", 9),
    )
    description.pack(fill=tkinter.X, pady=(0, 10))

    controls_frame = tkinter.Frame(container, bg=BOARD_OUTER)
    controls_frame.pack(fill=tkinter.BOTH, expand=True)
    for column in range(LAYOUT_TUNING_WINDOW_COLUMN_COUNT):
        controls_frame.grid_columnconfigure(column, weight=1)

    slider_vars: dict[str, tkinter.DoubleVar] = {}
    value_labels: dict[str, tkinter.Label] = {}
    canvas.layout_tuning_slider_vars = slider_vars
    canvas.layout_tuning_value_labels = value_labels
    defaults = LayoutTuningSettings()
    sync_state = {"active": False}

    def _set_status(text: str, color: str) -> None:
        _set_layout_tuning_status(canvas, text, color)

    def _refresh_value_labels(settings: LayoutTuningSettings) -> None:
        for field_name, label in value_labels.items():
            if label.winfo_exists():
                label.configure(
                    text=_format_layout_tuning_value(field_name, getattr(settings, field_name))
                )

    def _apply_settings(
        settings: LayoutTuningSettings | Mapping[str, object],
        *,
        redraw_table: bool,
        status_text: str,
        status_color: str,
    ) -> None:
        normalized_settings = _normalize_layout_tuning_settings(settings)
        canvas.layout_tuning_settings = normalized_settings
        sync_state["active"] = True
        try:
            for field_name, variable in slider_vars.items():
                variable.set(getattr(normalized_settings, field_name))
        finally:
            sync_state["active"] = False
        _refresh_value_labels(normalized_settings)
        _set_status(status_text, status_color)
        if redraw_table:
            redraw()

    def _handle_slider_change(field_name: str, _raw_value: str | None = None) -> None:
        if sync_state["active"]:
            return
        current_settings = _current_layout_tuning(canvas)
        updated_settings = replace(
            current_settings,
            **{
                field_name: slider_vars[field_name].get()
                if isinstance(getattr(defaults, field_name), float)
                else int(round(slider_vars[field_name].get()))
            },
        )
        _apply_settings(
            updated_settings,
            redraw_table=True,
            status_text="Preview only",
            status_color="#facc15",
        )

    controls_per_column = max(
        1,
        (len(LAYOUT_TUNING_CONTROLS) + LAYOUT_TUNING_WINDOW_COLUMN_COUNT - 1)
        // LAYOUT_TUNING_WINDOW_COLUMN_COUNT,
    )
    for index, control in enumerate(LAYOUT_TUNING_CONTROLS):
        column = index // controls_per_column
        row = index % controls_per_column
        row_frame = tkinter.Frame(controls_frame, bg=BOARD_OUTER)
        row_frame.grid(row=row, column=column, sticky="ew", padx=(0, 12) if column == 0 else (12, 0), pady=2)
        row_frame.grid_columnconfigure(1, weight=1)

        label = tkinter.Label(
            row_frame,
            text=control.label,
            anchor=tkinter.W,
            bg=BOARD_OUTER,
            fg=TEXT_PRIMARY,
            font=("Yu Gothic UI", 8),
        )
        label.grid(row=0, column=0, sticky="w", padx=(0, 8))

        variable = tkinter.DoubleVar(value=float(getattr(_current_layout_tuning(canvas), control.field_name)))
        slider = tkinter.Scale(
            row_frame,
            orient=tkinter.HORIZONTAL,
            from_=control.min_value,
            to=control.max_value,
            resolution=control.resolution,
            showvalue=False,
            variable=variable,
            command=lambda raw_value, field_name=control.field_name: _handle_slider_change(
                field_name,
                raw_value,
            ),
            bg=BOARD_OUTER,
            fg=TEXT_PRIMARY,
            troughcolor="#223f6c",
            activebackground="#36506f",
            highlightthickness=0,
            bd=0,
            sliderrelief=tkinter.FLAT,
            length=210,
        )
        slider.grid(row=0, column=1, sticky="ew")

        value_label = tkinter.Label(
            row_frame,
            text="",
            anchor=tkinter.E,
            width=5,
            bg=BOARD_OUTER,
            fg=TEXT_SECONDARY,
            font=("Consolas", 8, "bold"),
        )
        value_label.grid(row=0, column=2, sticky="e", padx=(8, 0))
        slider_vars[control.field_name] = variable
        value_labels[control.field_name] = value_label

    action_row = tkinter.Frame(container, bg=BOARD_OUTER)
    action_row.pack(fill=tkinter.X, pady=(10, 0))
    action_row.grid_columnconfigure(3, weight=1)

    def _handle_save() -> None:
        _finish_layout_component_drag(canvas)
        persisted_settings = _current_layout_tuning(canvas)
        canvas.layout_tuning_settings = persisted_settings
        try:
            _save_layout_tuning_settings(persisted_settings)
        except OSError as exc:
            _set_status(f"Save failed: {exc}", "#fca5a5")
            return
        _set_status("Saved to csv_db/ui_layout_tuning.json", "#86efac")

    def _handle_reset() -> None:
        _apply_settings(
            LayoutTuningSettings(),
            redraw_table=True,
            status_text="Reset to defaults",
            status_color=TEXT_SECONDARY,
        )

    def _handle_close(_event: tkinter.Event | None = None) -> str:
        canvas.layout_drag_enabled = False
        canvas.layout_drag_state = None
        canvas.layout_tuning_window = None
        canvas.layout_tuning_status_label = None
        if window.winfo_exists():
            window.destroy()
        redraw()
        return "break"

    save_button = tkinter.Button(
        action_row,
        text="Save",
        command=_handle_save,
        relief=tkinter.FLAT,
        bd=1,
        bg="#1c2735",
        fg="#d7deea",
        activebackground="#29415d",
        activeforeground="#f8fafc",
        font=("Yu Gothic UI", 8, "bold"),
        padx=10,
        pady=2,
    )
    save_button.grid(row=0, column=0, sticky="w")

    reset_button = tkinter.Button(
        action_row,
        text="Reset",
        command=_handle_reset,
        relief=tkinter.FLAT,
        bd=1,
        bg="#1c2735",
        fg="#d7deea",
        activebackground="#29415d",
        activeforeground="#f8fafc",
        font=("Yu Gothic UI", 8, "bold"),
        padx=10,
        pady=2,
    )
    reset_button.grid(row=0, column=1, sticky="w", padx=(8, 0))

    close_button = tkinter.Button(
        action_row,
        text="Close",
        command=_handle_close,
        relief=tkinter.FLAT,
        bd=1,
        bg="#1c2735",
        fg="#d7deea",
        activebackground="#29415d",
        activeforeground="#f8fafc",
        font=("Yu Gothic UI", 8, "bold"),
        padx=10,
        pady=2,
    )
    close_button.grid(row=0, column=2, sticky="w", padx=(8, 0))

    status_label = tkinter.Label(
        action_row,
        text="Preview stays active until the app closes or you reset it.",
        anchor=tkinter.W,
        bg=BOARD_OUTER,
        fg=TEXT_SECONDARY,
        font=("Yu Gothic UI", 8),
    )
    status_label.grid(row=0, column=3, sticky="ew", padx=(12, 0))
    canvas.layout_tuning_status_label = status_label

    window.bind("<Escape>", _handle_close)
    window.protocol("WM_DELETE_WINDOW", _handle_close)
    window.update_idletasks()
    window.geometry(f"+{root.winfo_rootx() + 48}+{root.winfo_rooty() + 48}")
    _apply_settings(
        _current_layout_tuning(canvas),
        redraw_table=False,
        status_text="Preview stays active until the app closes or you reset it. Drag any cyan outline on the table.",
        status_color=TEXT_SECONDARY,
    )
    redraw()


def _normalize_meld_map(melds_by_player: SeatMeldMap | None) -> dict[Player, list[Meld]]:
    """欠けたキーを補いながら鳴き一覧を Player キーへ正規化する。"""

    if melds_by_player is None:
        return {player: [] for player in Player}
    return {
        player: list(melds_by_player.get(player, []))
        for player in Player
    }


def _normalize_hand_danger_percentages(
    percentages: HandDangerPercentages | None,
) -> dict[int, dict[str, float | int]]:
    """Clamp one tile's opponent danger percentages into the UI's 0..100 range."""

    normalized = {
        seat: {
            "percentage": 0,
            "numerator_count": 0.0,
            "denominator_count": 0.0,
        }
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    if percentages is None:
        return normalized
    for seat in HAND_DANGER_BAR_SEAT_ORDER:
        raw_value = percentages.get(seat, 0)
        raw_percentage = raw_value
        raw_numerator_count = 0.0
        raw_denominator_count = 0.0
        if isinstance(raw_value, dict):
            raw_percentage = raw_value.get("percentage", 0)
            raw_numerator_count = raw_value.get("numerator_count", 0.0)
            raw_denominator_count = raw_value.get(
                "denominator_count",
                raw_value.get("remaining_count", 0.0),
            )
        else:
            raw_percentage = getattr(raw_value, "percentage", raw_value)
            raw_numerator_count = getattr(raw_value, "numerator_count", 0.0)
            raw_denominator_count = getattr(
                raw_value,
                "denominator_count",
                getattr(raw_value, "remaining_count", 0.0),
            )
        try:
            normalized[seat]["percentage"] = max(0, min(100, int(raw_percentage)))
        except (TypeError, ValueError):
            normalized[seat]["percentage"] = 0
        try:
            normalized[seat]["numerator_count"] = max(0.0, float(raw_numerator_count))
        except (TypeError, ValueError):
            normalized[seat]["numerator_count"] = 0.0
        try:
            normalized[seat]["denominator_count"] = max(0.0, float(raw_denominator_count))
        except (TypeError, ValueError):
            normalized[seat]["denominator_count"] = 0.0
    return normalized


def _normalize_player_panel_line_summary_entries(
    raw_entries: object,
    *,
    fallback_labels: object = (),
) -> tuple[dict[str, str], ...]:
    """Normalize structured or legacy `Line` payloads into one renderer-side shape."""

    normalized_entries: list[dict[str, str]] = []
    if isinstance(raw_entries, (list, tuple)):
        for raw_entry in raw_entries[:3]:
            if isinstance(raw_entry, Mapping):
                raw_rank_text = raw_entry.get("rank_text", "")
                raw_left_tile_label = raw_entry.get("left_tile_label", "")
                raw_right_tile_label = raw_entry.get("right_tile_label", "")
                raw_suit_label = raw_entry.get("suit_label", "")
                raw_line_weight_text = raw_entry.get("line_weight_text", "")
                raw_percent_text = raw_entry.get("percent_text", "")
                raw_suit_remaining_count_text = raw_entry.get("suit_remaining_count_text", "")
            else:
                raw_rank_text = getattr(raw_entry, "rank_text", "")
                raw_left_tile_label = getattr(raw_entry, "left_tile_label", "")
                raw_right_tile_label = getattr(raw_entry, "right_tile_label", "")
                raw_suit_label = getattr(raw_entry, "suit_label", "")
                raw_line_weight_text = getattr(raw_entry, "line_weight_text", "")
                raw_percent_text = getattr(raw_entry, "percent_text", "")
                raw_suit_remaining_count_text = getattr(
                    raw_entry,
                    "suit_remaining_count_text",
                    "",
                )
            normalized_entries.append(
                {
                    "rank_text": str(raw_rank_text or "").strip(),
                    "left_tile_label": str(raw_left_tile_label or "").strip(),
                    "right_tile_label": str(raw_right_tile_label or "").strip(),
                    "suit_label": str(raw_suit_label or "").strip(),
                    "line_weight_text": str(raw_line_weight_text or "").strip(),
                    "percent_text": str(raw_percent_text or "").strip(),
                    "suit_remaining_count_text": str(raw_suit_remaining_count_text or "").strip(),
                }
            )
    if normalized_entries:
        return tuple(normalized_entries[:3])

    if not isinstance(fallback_labels, (list, tuple)):
        return ()
    for row_index, raw_label in enumerate(fallback_labels[:3], start=1):
        normalized_label = str(raw_label or "").strip()
        parts = normalized_label.split()
        line_label = parts[0] if parts else ""
        if len(line_label) < 4 or "-" not in line_label:
            normalized_entries.append(
                {
                    "rank_text": f"{row_index}.",
                    "left_tile_label": "",
                    "right_tile_label": "",
                    "suit_label": "",
                    "line_weight_text": "",
                    "percent_text": normalized_label,
                    "suit_remaining_count_text": "",
                }
            )
            continue
        suit_label = line_label[-1]
        left_right = line_label[:-1].split("-", 1)
        if len(left_right) != 2:
            continue
        left_number, right_number = left_right
        line_weight_text = ""
        percent_text = ""
        suit_remaining_count_text = ""
        for token in parts[1:]:
            normalized_token = str(token or "").strip()
            if not normalized_token:
                continue
            if not percent_text and normalized_token.endswith("%"):
                percent_text = normalized_token
                continue
            if (
                not suit_remaining_count_text
                and normalized_token.startswith(suit_label)
                and len(normalized_token) >= 2
            ):
                suit_remaining_count_text = normalized_token[1:]
                continue
            if not line_weight_text:
                line_weight_text = normalized_token
        normalized_entries.append(
            {
                "rank_text": f"{row_index}.",
                "left_tile_label": f"{left_number}{suit_label}",
                "right_tile_label": f"{right_number}{suit_label}",
                "suit_label": suit_label,
                "line_weight_text": line_weight_text.strip(),
                "percent_text": percent_text.strip(),
                "suit_remaining_count_text": suit_remaining_count_text.strip(),
            }
        )
    return tuple(normalized_entries[:3])


def _normalize_opponent_suji_panel_summaries(
    summaries: OpponentSujiPanelSummaries | None,
) -> dict[int, dict[str, object]]:
    """Normalize per-opponent player-panel summary data for the UI."""

    normalized = {
        seat: {
            "denominator_count": 0.0,
            "denominator_count_without_temporary_safe": None,
            "menzen_alert_score": 0,
            "hand_pattern_alert_level": 0,
            "suit_bias_alert": False,
            "ryanmen_chi_central_tedashi_alert": False,
            "tedashi_thinking_rise_alert": False,
            "tenpai_probability": 0.0,
            "is_riichi": False,
            "is_loading": False,
            "top_line_labels": (),
            "top_line_summaries": (),
            "top_safe_hand_labels": (),
            "top_tile_rank_labels": (),
        }
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    if summaries is None:
        return normalized
    for seat in HAND_DANGER_BAR_SEAT_ORDER:
        raw_value = summaries.get(seat)
        if raw_value is None:
            continue
        # Accept both dataclass-like objects from the logic layer and plain dicts from tests/mocks
        # so renderer-side code can stay shape-stable.
        if isinstance(raw_value, dict):
            raw_denominator = raw_value.get("denominator_count", 0.0)
            raw_denominator_without_temporary_safe = raw_value.get(
                "denominator_count_without_temporary_safe"
            )
            raw_menzen_alert_score = raw_value.get("menzen_alert_score", 0)
            raw_hand_pattern_alert_level = raw_value.get("hand_pattern_alert_level", 0)
            raw_suit_bias_alert = raw_value.get("suit_bias_alert", False)
            raw_ryanmen_chi_central_tedashi_alert = raw_value.get(
                "ryanmen_chi_central_tedashi_alert",
                False,
            )
            raw_tedashi_thinking_rise_alert = raw_value.get("tedashi_thinking_rise_alert", False)
            raw_tenpai_probability = raw_value.get("tenpai_probability", 0.0)
            raw_is_riichi = raw_value.get("is_riichi", False)
            raw_is_loading = raw_value.get("is_loading", False)
            raw_top_lines = raw_value.get("top_line_labels", ())
            raw_top_line_summaries = raw_value.get("top_line_summaries", ())
            raw_top_safe_hand = raw_value.get("top_safe_hand_labels", ())
            raw_top_tiles = raw_value.get("top_tile_rank_labels", ())
        else:
            raw_denominator = getattr(raw_value, "denominator_count", 0.0)
            raw_denominator_without_temporary_safe = getattr(
                raw_value,
                "denominator_count_without_temporary_safe",
                None,
            )
            raw_menzen_alert_score = getattr(raw_value, "menzen_alert_score", 0)
            raw_hand_pattern_alert_level = getattr(raw_value, "hand_pattern_alert_level", 0)
            raw_suit_bias_alert = getattr(raw_value, "suit_bias_alert", False)
            raw_ryanmen_chi_central_tedashi_alert = getattr(
                raw_value,
                "ryanmen_chi_central_tedashi_alert",
                False,
            )
            raw_tedashi_thinking_rise_alert = getattr(
                raw_value,
                "tedashi_thinking_rise_alert",
                False,
            )
            raw_tenpai_probability = getattr(raw_value, "tenpai_probability", 0.0)
            raw_is_riichi = getattr(raw_value, "is_riichi", False)
            raw_is_loading = getattr(raw_value, "is_loading", False)
            raw_top_lines = getattr(raw_value, "top_line_labels", ())
            raw_top_line_summaries = getattr(raw_value, "top_line_summaries", ())
            raw_top_safe_hand = getattr(raw_value, "top_safe_hand_labels", ())
            raw_top_tiles = getattr(raw_value, "top_tile_rank_labels", ())
        try:
            normalized[seat]["denominator_count"] = max(0.0, float(raw_denominator))
        except (TypeError, ValueError):
            normalized[seat]["denominator_count"] = 0.0
        try:
            normalized[seat]["denominator_count_without_temporary_safe"] = (
                None
                if raw_denominator_without_temporary_safe is None
                else max(0.0, float(raw_denominator_without_temporary_safe))
            )
        except (TypeError, ValueError):
            normalized[seat]["denominator_count_without_temporary_safe"] = None
        try:
            normalized[seat]["menzen_alert_score"] = max(0, int(raw_menzen_alert_score))
        except (TypeError, ValueError):
            normalized[seat]["menzen_alert_score"] = 0
        try:
            normalized[seat]["hand_pattern_alert_level"] = max(
                0,
                int(raw_hand_pattern_alert_level),
            )
        except (TypeError, ValueError):
            normalized[seat]["hand_pattern_alert_level"] = 0
        normalized[seat]["suit_bias_alert"] = bool(raw_suit_bias_alert)
        normalized[seat]["ryanmen_chi_central_tedashi_alert"] = bool(
            raw_ryanmen_chi_central_tedashi_alert
        )
        normalized[seat]["tedashi_thinking_rise_alert"] = bool(raw_tedashi_thinking_rise_alert)
        try:
            normalized[seat]["tenpai_probability"] = max(0.0, min(100.0, float(raw_tenpai_probability)))
        except (TypeError, ValueError):
            normalized[seat]["tenpai_probability"] = 0.0
        normalized[seat]["is_riichi"] = bool(raw_is_riichi)
        normalized[seat]["is_loading"] = bool(raw_is_loading)
        if isinstance(raw_top_lines, (list, tuple)):
            normalized[seat]["top_line_labels"] = tuple(str(value) for value in raw_top_lines[:3])
        else:
            normalized[seat]["top_line_labels"] = ()
        normalized[seat]["top_line_summaries"] = _normalize_player_panel_line_summary_entries(
            raw_top_line_summaries,
            fallback_labels=normalized[seat]["top_line_labels"],
        )
        if isinstance(raw_top_safe_hand, (list, tuple)):
            normalized[seat]["top_safe_hand_labels"] = tuple(str(value) for value in raw_top_safe_hand[:3])
        else:
            normalized[seat]["top_safe_hand_labels"] = ()
        if isinstance(raw_top_tiles, (list, tuple)):
            normalized[seat]["top_tile_rank_labels"] = tuple(
                str(value) for value in raw_top_tiles[:3]
            )
        else:
            normalized[seat]["top_tile_rank_labels"] = ()
    return normalized


def _normalize_player_push_alert_percentages(
    alert_percentages: PlayerPushAlertPercentages | None,
) -> dict[int, dict[str, object]]:
    """Normalize per-seat push-alert payloads into a stable renderer-side shape."""

    normalized = {
        seat: _empty_player_push_alert_payload(seat)
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    if alert_percentages is None:
        return normalized
    if not isinstance(alert_percentages, Mapping):
        return normalized
    for fallback_seat, raw_value in alert_percentages.items():
        if isinstance(raw_value, dict):
            raw_seat = raw_value.get("seat", fallback_seat)
            raw_percentage = raw_value.get("percentage", 0.0)
            raw_threshold_percent = raw_value.get("threshold_percent", 9.0)
            raw_tile_label = raw_value.get("tile_label", "")
            raw_discard_index = raw_value.get("discard_index")
            raw_is_current = raw_value.get("is_current", False)
            raw_kind = raw_value.get("kind")
            raw_target_seats = raw_value.get("target_seats", ())
            raw_exact_safe_target_seats = raw_value.get("exact_safe_target_seats", ())
        else:
            raw_seat = getattr(raw_value, "seat", fallback_seat)
            raw_percentage = getattr(raw_value, "percentage", raw_value)
            raw_threshold_percent = getattr(raw_value, "threshold_percent", 9.0)
            raw_tile_label = getattr(raw_value, "tile_label", "")
            raw_discard_index = getattr(raw_value, "discard_index", None)
            raw_is_current = getattr(raw_value, "is_current", False)
            raw_kind = getattr(raw_value, "kind", None)
            raw_target_seats = getattr(raw_value, "target_seats", ())
            raw_exact_safe_target_seats = getattr(raw_value, "exact_safe_target_seats", ())
        try:
            normalized_seat = int(raw_seat)
        except (TypeError, ValueError):
            try:
                normalized_seat = int(fallback_seat)
            except (TypeError, ValueError):
                continue
        target_seat = normalized_seat if normalized_seat in normalized else None
        if target_seat is None:
            continue
        try:
            normalized[target_seat]["percentage"] = max(0.0, float(raw_percentage))
        except (TypeError, ValueError):
            normalized[target_seat]["percentage"] = 0.0
        try:
            normalized[target_seat]["threshold_percent"] = (
                float(raw_threshold_percent)
                if float(raw_threshold_percent) > 0.0
                else 9.0
            )
        except (TypeError, ValueError):
            normalized[target_seat]["threshold_percent"] = 9.0
        normalized[target_seat]["seat"] = normalized_seat
        normalized[target_seat]["tile_label"] = str(raw_tile_label or "").strip()
        try:
            normalized[target_seat]["discard_index"] = int(raw_discard_index)
        except (TypeError, ValueError):
            normalized[target_seat]["discard_index"] = None
        normalized[target_seat]["is_current"] = bool(raw_is_current)
        normalized[target_seat]["kind"] = str(raw_kind or "").strip().lower()
        if not normalized[target_seat]["kind"]:
            normalized[target_seat]["kind"] = (
                "push"
                if normalized[target_seat]["percentage"]
                >= normalized[target_seat]["threshold_percent"]
                else "none"
            )
        normalized[target_seat]["target_seats"] = _normalize_alert_seat_tuple(raw_target_seats)
        normalized[target_seat]["exact_safe_target_seats"] = _normalize_alert_seat_tuple(
            raw_exact_safe_target_seats
        )
    return normalized


def _push_marker_alerts_for_render(
    latest_push_alerts_by_seat: PlayerPushAlertPercentages | None,
    previous_marker_indices_by_seat: Mapping[int, object] | None = None,
    latest_global_discard_index: int | None = None,
) -> dict[int, frozenset[int]]:
    """Return round-latched river `P` marker indexes.

    Panel-side `Push` rows are short-lived, but the river marker remains for the round once
    a qualifying push discard appears.
    """

    current_marker_indices_by_seat = _push_discard_marker_indices_by_seat(
        _normalize_player_push_alert_percentages(latest_push_alerts_by_seat)
    )
    if latest_global_discard_index is None:
        return current_marker_indices_by_seat

    previous_marker_indices = _normalize_push_marker_indices_by_seat(
        previous_marker_indices_by_seat
    )
    latched_indices: dict[int, frozenset[int]] = {}
    for seat in HAND_DANGER_BAR_SEAT_ORDER:
        retained_previous_indices = {
            discard_index
            for discard_index in previous_marker_indices.get(seat, frozenset())
            if discard_index <= latest_global_discard_index
        }
        merged_indices = frozenset(
            retained_previous_indices
            | set(current_marker_indices_by_seat.get(seat, frozenset()))
        )
        if not merged_indices:
            continue
        latched_indices[seat] = merged_indices
    return latched_indices


def _normalize_player_score_diffs_by_seat(
    score_diffs_by_seat: PlayerScoreDiffs | None,
) -> dict[int, int]:
    """Normalize per-opponent score-gap payloads into stable renderer-side ints."""

    normalized = {
        seat: 0
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    if not isinstance(score_diffs_by_seat, Mapping):
        return normalized
    for fallback_seat, raw_value in score_diffs_by_seat.items():
        try:
            seat = int(fallback_seat)
        except (TypeError, ValueError):
            continue
        if seat not in normalized:
            continue
        try:
            normalized[seat] = int(raw_value)
        except (TypeError, ValueError):
            normalized[seat] = 0
    return normalized


def _normalize_discard_red_tint_indices_by_seat(
    highlighted_indices_by_seat: DiscardRedTintIndicesBySeat | None,
) -> dict[int, frozenset[int]]:
    """Normalize per-seat discard-index highlight payloads for river tile tinting."""

    normalized = {int(player): frozenset() for player in Player}
    if not isinstance(highlighted_indices_by_seat, Mapping):
        return normalized
    for fallback_seat, raw_indices in highlighted_indices_by_seat.items():
        try:
            seat = int(fallback_seat)
        except (TypeError, ValueError):
            continue
        if seat not in normalized:
            continue
        if not isinstance(raw_indices, (list, tuple, set, frozenset)):
            continue
        valid_indices: set[int] = set()
        for raw_index in raw_indices:
            try:
                discard_index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if discard_index < 0:
                continue
            valid_indices.add(discard_index)
        normalized[seat] = frozenset(valid_indices)
    return normalized


def _empty_player_push_alert_payload(seat: int) -> dict[str, object]:
    """Return the renderer's zero-value push-alert payload for one seat."""

    return {
        "seat": seat,
        "percentage": 0.0,
        "threshold_percent": 9.0,
        "tile_label": "",
        "discard_index": None,
        "is_current": False,
        "kind": "none",
        "target_seats": (),
        "exact_safe_target_seats": (),
    }


def _empty_player_push_marker_indices_by_seat() -> dict[int, frozenset[int]]:
    """Return the renderer's zero-value river push-marker index map."""

    return {seat: frozenset() for seat in HAND_DANGER_BAR_SEAT_ORDER}


def _normalize_push_marker_indices_by_seat(
    marker_indices_by_seat: Mapping[int, object] | None,
) -> dict[int, frozenset[int]]:
    """Normalize per-seat river push-marker indexes into immutable index sets."""

    normalized = _empty_player_push_marker_indices_by_seat()
    if not isinstance(marker_indices_by_seat, Mapping):
        return normalized
    for fallback_seat, raw_indices in marker_indices_by_seat.items():
        try:
            seat = int(fallback_seat)
        except (TypeError, ValueError):
            continue
        if seat not in normalized:
            continue
        if isinstance(raw_indices, Mapping):
            raw_index_values = raw_indices.get("discard_indices")
            if raw_index_values is None:
                raw_index_values = raw_indices.get("discard_index")
        else:
            raw_index_values = raw_indices
        if isinstance(raw_index_values, (str, bytes)):
            raw_iterable = (raw_index_values,)
        elif isinstance(raw_index_values, Iterable):
            raw_iterable = raw_index_values
        else:
            raw_iterable = (raw_index_values,)
        valid_indices: set[int] = set()
        for raw_index in raw_iterable:
            try:
                discard_index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if discard_index >= 0:
                valid_indices.add(discard_index)
        normalized[seat] = frozenset(valid_indices)
    return normalized


def _normalize_alert_seat_tuple(raw_values: object) -> tuple[int, ...]:
    """Return one deduplicated sorted seat tuple from mixed raw payload values."""

    if not isinstance(raw_values, (list, tuple, set)):
        return ()
    normalized_values: set[int] = set()
    for raw_value in raw_values:
        try:
            normalized_values.add(int(raw_value))
        except (TypeError, ValueError):
            continue
    return tuple(sorted(normalized_values))


def _player_push_alert_threshold_percent(
    alert_data: Mapping[str, object],
    *,
    default: float = 9.0,
) -> float:
    """Return the effective push threshold carried by one renderer payload."""

    try:
        threshold_percent = float(alert_data.get("threshold_percent", default))
    except (TypeError, ValueError):
        return default
    return threshold_percent if threshold_percent > 0.0 else default


def _latest_global_discard_index_from_discard_map(
    discard_map: Mapping[object, Iterable[object]],
) -> int | None:
    """Return the current round's latest global discard index from the renderer discard map."""

    discard_count = 0
    for discards in discard_map.values():
        if isinstance(discards, Sequence):
            discard_count += len(discards)
            continue
        discard_count += sum(1 for _ in discards)
    if discard_count <= 0:
        return None
    return discard_count - 1


def _push_alert_is_latchable(
    alert_data: Mapping[str, object],
    *,
    seat: int,
) -> bool:
    """Return whether one current push alert should start or refresh the persistence window."""

    try:
        alert_seat = int(alert_data.get("seat", seat))
    except (TypeError, ValueError):
        alert_seat = seat
    if alert_seat != seat:
        return False
    try:
        alert_percent = max(0.0, float(alert_data.get("percentage", 0.0)))
    except (TypeError, ValueError):
        return False
    threshold_percent = _player_push_alert_threshold_percent(alert_data)
    try:
        int(alert_data.get("discard_index"))
    except (TypeError, ValueError):
        return False
    # panel の Push 起点条件は河の `P` と揃え、各席の最新打牌ベースで見る。
    # `is_current` は卓全体の現打牌ゲートではなく、Push解除 判定側だけで使う。
    return alert_percent >= threshold_percent


def _push_release_payload(
    current_alert: Mapping[str, object],
    previous_alert: Mapping[str, object],
    *,
    seat: int,
) -> dict[str, object] | None:
    """Return one `Push解除` payload when a latched push is followed by tedashi genbutsu."""

    if str(previous_alert.get("kind", "") or "").strip().lower() != "push":
        return None
    try:
        current_seat = int(current_alert.get("seat", seat))
    except (TypeError, ValueError):
        current_seat = seat
    if current_seat != seat or not bool(current_alert.get("is_current", False)):
        return None
    try:
        current_discard_index = int(current_alert.get("discard_index"))
    except (TypeError, ValueError):
        return None
    previous_target_seats = set(_normalize_alert_seat_tuple(previous_alert.get("target_seats", ())))
    current_exact_safe_target_seats = set(
        _normalize_alert_seat_tuple(current_alert.get("exact_safe_target_seats", ()))
    )
    resolved_target_seats = tuple(
        sorted(previous_target_seats & current_exact_safe_target_seats)
    )
    if not resolved_target_seats:
        return None
    return {
        "seat": seat,
        "percentage": 0.0,
        "threshold_percent": _player_push_alert_threshold_percent(previous_alert),
        "tile_label": str(current_alert.get("tile_label", "") or "").strip(),
        "discard_index": current_discard_index,
        "is_current": True,
        "kind": "release",
        "target_seats": resolved_target_seats,
        "exact_safe_target_seats": (),
    }


def _persist_player_push_alerts(
    current_push_alerts_by_seat: Mapping[int, Mapping[str, object]],
    previous_push_alerts_by_seat: Mapping[int, Mapping[str, object]],
    latest_global_discard_index: int | None,
) -> dict[int, dict[str, object]]:
    """Keep push alerts visible for a few turns after first appearance."""

    persisted_alerts: dict[int, dict[str, object]] = {}
    for seat in HAND_DANGER_BAR_SEAT_ORDER:
        current_alert = dict(
            current_push_alerts_by_seat.get(seat, _empty_player_push_alert_payload(seat))
        )
        if _push_alert_is_latchable(current_alert, seat=seat):
            current_alert["kind"] = "push"
            persisted_alerts[seat] = current_alert
            continue

        previous_alert = dict(
            previous_push_alerts_by_seat.get(seat, _empty_player_push_alert_payload(seat))
        )
        release_alert = _push_release_payload(current_alert, previous_alert, seat=seat)
        if release_alert is not None:
            persisted_alerts[seat] = release_alert
            continue
        try:
            previous_percent = max(0.0, float(previous_alert.get("percentage", 0.0)))
        except (TypeError, ValueError):
            previous_percent = 0.0
        previous_threshold_percent = _player_push_alert_threshold_percent(previous_alert)
        try:
            previous_discard_index = int(previous_alert.get("discard_index"))
        except (TypeError, ValueError):
            previous_discard_index = None
        previous_kind = str(previous_alert.get("kind", "") or "").strip().lower()
        if not previous_kind and previous_percent >= previous_threshold_percent:
            previous_kind = "push"

        if (
            previous_kind in {"push", "release"}
            and (
                previous_kind == "release"
                or previous_percent >= previous_threshold_percent
            )
            and previous_discard_index is not None
            and latest_global_discard_index is not None
            and latest_global_discard_index - previous_discard_index
            <= PLAYER_PUSH_ALERT_PERSIST_DISCARD_WINDOW
        ):
            previous_alert["is_current"] = False
            persisted_alerts[seat] = previous_alert
            continue

        persisted_alerts[seat] = _empty_player_push_alert_payload(seat)
    return persisted_alerts


def _normalize_player_names_by_seat(
    player_names_by_seat: PlayerNamesBySeat | None,
) -> dict[int, str]:
    """Normalize relative-seat player names for the panel UI."""

    normalized = {
        int(Player.JICHA): "YOU",
        int(Player.SHIMOCHA): "",
        int(Player.TOIMEN): "",
        int(Player.KAMICHA): "",
    }
    if player_names_by_seat is None:
        return normalized
    if not isinstance(player_names_by_seat, Mapping):
        return normalized
    for seat in range(4):
        raw_name = player_names_by_seat.get(seat)
        if raw_name is None:
            continue
        player_name = str(raw_name).strip()
        if player_name:
            normalized[seat] = player_name
    return normalized


def _tile37_to_compact_label(tile_37: int) -> str:
    """Convert one UI tile id into compact `1m` / `5p` / `7z` text with red fives collapsed."""

    if tile_37 == 10:
        return "5m"
    if 1 <= tile_37 <= 9:
        return f"{tile_37}m"
    if tile_37 == 20:
        return "5p"
    if 11 <= tile_37 <= 19:
        return f"{tile_37 - 9}p"
    if tile_37 == 30:
        return "5s"
    if 21 <= tile_37 <= 29:
        return f"{tile_37 - 20}s"
    if 31 <= tile_37 <= 37:
        return f"{tile_37 - 30}z"
    return str(tile_37)


def _player_panel_display_name(seat: int, player_name: str) -> str:
    """Return the panel-visible player name, hiding fallback opponent seat labels."""

    normalized_name = str(player_name or "").strip()
    fallback_name = str(PLAYER_PANEL_FALLBACK_NAME_BY_SEAT.get(int(seat), "") or "").strip()
    if (
        int(seat) != int(Player.JICHA)
        and normalized_name
        and fallback_name
        and normalized_name.upper() == fallback_name.upper()
    ):
        return ""
    return normalized_name


def _dora_tile34_index_from_indicator_tile37(tile_37: int) -> int | None:
    """Return the canonical 34-index dora tile for one UI-facing indicator tile id."""

    indicator_tile_34 = tile37_to_tile34_index(int(tile_37))
    if indicator_tile_34 is None:
        return None
    if 0 <= indicator_tile_34 <= 7:
        return indicator_tile_34 + 1
    if indicator_tile_34 == 8:
        return 0
    if 9 <= indicator_tile_34 <= 16:
        return indicator_tile_34 + 1
    if indicator_tile_34 == 17:
        return 9
    if 18 <= indicator_tile_34 <= 25:
        return indicator_tile_34 + 1
    if indicator_tile_34 == 26:
        return 18
    if 27 <= indicator_tile_34 <= 29:
        return indicator_tile_34 + 1
    if indicator_tile_34 == 30:
        return 27
    if 31 <= indicator_tile_34 <= 32:
        return indicator_tile_34 + 1
    if indicator_tile_34 == 33:
        return 31
    return None


def _visible_dora_tile_count(
    dora_indicator_tiles: Sequence[int],
    visible_summary: VisibleTileSummary | None,
) -> int:
    """Return visible dora count including red dora seen on the table."""

    if visible_summary is None:
        return 0
    try:
        visible_red_dora_count = max(0, int(getattr(visible_summary, "visible_red_dora_count", 0)))
    except (TypeError, ValueError):
        visible_red_dora_count = 0
    visible_counts_34_index = tuple(
        int(count) for count in getattr(visible_summary, "visible_counts_34_index", ())
    )
    if not visible_counts_34_index:
        return visible_red_dora_count
    dora_tile34_indices = {
        dora_tile_34
        for dora_tile_34 in (
            _dora_tile34_index_from_indicator_tile37(int(tile_37))
            for tile_37 in dora_indicator_tiles
        )
        if dora_tile_34 is not None
    }
    return visible_red_dora_count + sum(
        _effective_visible_dora_count_for_alert(
            dora_tile_34,
            visible_counts_34_index[dora_tile_34],
        )
        for dora_tile_34 in dora_tile34_indices
        if 0 <= dora_tile_34 < len(visible_counts_34_index)
    )


def _effective_visible_dora_count_for_alert(
    dora_tile34_index: int,
    visible_count: int,
) -> int:
    """Return the alert-side visible dora count for one dora kind.

    字牌ドラは 3 見えでも実戦上ほぼ枯れ扱いとして見たいので、EV 横の `ドラ◯` 表示だけは
    4 見え相当に切り上げる。数牌や赤ドラの見え枚数はそのまま使う。
    """

    normalized_visible_count = max(0, int(visible_count))
    if 27 <= int(dora_tile34_index) <= 33 and normalized_visible_count >= 3:
        return 4
    return normalized_visible_count


def _format_visible_dora_tile_count_label(visible_dora_tile_count: int) -> str:
    """Format the compact self-alert-side visible dora count label."""

    normalized_count = str(max(0, int(visible_dora_tile_count)))
    fullwidth_count = normalized_count.translate(str.maketrans("0123456789", "０１２３４５６７８９"))
    return f"ドラ{fullwidth_count}"


def _self_hand_visible_dora_alert_colors(
    visible_dora_tile_count: int,
) -> tuple[str, str, str]:
    """Return the fill/outline/text colors for the self-side visible-dora status pill."""

    normalized_count = max(0, int(visible_dora_tile_count))
    if normalized_count <= 0:
        return (
            HAND_SELF_ALERT_ACTIVE_FILL,
            HAND_SELF_ALERT_ACTIVE_OUTLINE,
            HAND_SELF_ALERT_ACTIVE_TEXT,
        )
    if normalized_count == 1:
        return (
            HAND_SELF_ALERT_WARNING_FILL,
            HAND_SELF_ALERT_WARNING_OUTLINE,
            HAND_SELF_ALERT_WARNING_TEXT,
        )
    if normalized_count >= 3:
        return (
            HAND_SELF_ALERT_HIGH_FILL,
            HAND_SELF_ALERT_HIGH_OUTLINE,
            HAND_SELF_ALERT_HIGH_TEXT,
        )
    return (
        HAND_SELF_ALERT_FILL,
        HAND_SELF_ALERT_OUTLINE,
        HAND_SELF_ALERT_MUTED_TEXT,
    )


def _self_hand_visible_dora_alert_dot_color(visible_dora_tile_count: int) -> str | None:
    """Return the optional alert dot color for the self-side visible-dora pill."""

    normalized_count = max(0, int(visible_dora_tile_count))
    if normalized_count <= 0:
        return PLAYER_ALERT_RED
    if normalized_count == 1:
        return PLAYER_ALERT_YELLOW
    if normalized_count >= 3:
        return PLAYER_ALERT_GREEN
    return None


def _build_current_hand_safe_rank_labels(
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    *,
    seat: int,
    limit: int,
) -> tuple[str, ...]:
    """Build one seat's safest current-hand tile ranking from the displayed self hand."""

    display_hand_tiles = _build_hand_tiles_for_recommendation(hand_tiles, hand_draw_tile)
    unique_tiles: dict[str, tuple[int, float]] = {}
    for index, tile_id in enumerate(display_hand_tiles):
        tile_label = _tile37_to_compact_label(int(tile_id))
        tile_metrics = (
            hand_danger_percentages[index]
            if index < len(hand_danger_percentages)
            else _normalize_hand_danger_percentages(None)
        )
        try:
            percentage = max(0.0, float(tile_metrics.get(seat, {}).get("percentage", 0)))
        except (TypeError, ValueError):
            percentage = 0.0
        try:
            sort_tile_id = int(tile_id)
        except (TypeError, ValueError):
            sort_tile_id = 99
        existing = unique_tiles.get(tile_label)
        if existing is None or percentage < existing[1] or (
            percentage == existing[1] and sort_tile_id < existing[0]
        ):
            unique_tiles[tile_label] = (sort_tile_id, percentage)
    ranked_tiles = sorted(
        (
            (tile_label, tile_id, round(percentage, 1))
            for tile_label, (tile_id, percentage) in unique_tiles.items()
        ),
        key=lambda item: (item[2], item[1]),
    )
    grouped_labels: list[str] = []
    last_percent: float | None = None
    current_tiles: list[str] = []
    current_rank = 0

    def flush_group() -> None:
        nonlocal current_rank, current_tiles, last_percent
        if not current_tiles or last_percent is None or current_rank >= limit:
            return
        current_rank += 1
        percent_text = f"{max(0.0, float(last_percent)):.1f}".rstrip("0").rstrip(".") + "%"
        grouped_labels.append(f"{current_rank}. {' '.join(current_tiles[:5])} {percent_text}")

    for tile_label, _tile_id, total_percent in ranked_tiles:
        if last_percent is None:
            last_percent = total_percent
            current_tiles = [tile_label]
            continue
        if total_percent == last_percent:
            if len(current_tiles) < 5:
                current_tiles.append(tile_label)
            continue
        flush_group()
        if current_rank >= limit:
            break
        last_percent = total_percent
        current_tiles = [tile_label]
    flush_group()
    return tuple(grouped_labels[:limit])


def _fit_text_to_width(
    canvas: tkinter.Canvas,
    text: str,
    font_spec: object,
    max_width: float,
) -> str:
    """Clamp one-line text to the available width with `...`."""

    normalized_text = str(text or "")
    if max_width <= 0:
        return ""
    font = tkfont.Font(root=canvas, font=font_spec)
    if font.measure(normalized_text) <= max_width:
        return normalized_text
    ellipsis = "..."
    if font.measure(ellipsis) > max_width:
        return ""
    fitted = normalized_text
    while fitted and font.measure(f"{fitted}{ellipsis}") > max_width:
        fitted = fitted[:-1]
    return f"{fitted}{ellipsis}" if fitted else ellipsis


def _quantize_ui_scale(raw_scale: float) -> float:
    """Round the responsive scale so image-table caching stays stable."""

    clamped = max(RESPONSIVE_MIN_SCALE, min(1.0, raw_scale))
    return round(clamped / RESPONSIVE_SCALE_STEP) * RESPONSIVE_SCALE_STEP


def _compute_ui_scale(width: float, screen_width: float) -> float:
    """Return a smaller UI scale only when the window is narrowed to about half width."""

    trigger_width = max(
        float(WINDOW_MIN_WIDTH),
        float(screen_width) * RESPONSIVE_TRIGGER_SCREEN_WIDTH_RATIO,
    ) if screen_width > 0 else RESPONSIVE_FALLBACK_TRIGGER_WIDTH
    if width >= trigger_width:
        return 1.0
    width_scale = width / trigger_width if trigger_width > 0 else 1.0
    return _quantize_ui_scale(min(width_scale, 1.0))


def _scaled_length(value: float, ui_scale: float, *, minimum: float | None = None) -> float:
    """Scale one layout constant while respecting an optional minimum."""

    scaled_value = float(value) * ui_scale
    if minimum is not None:
        return max(float(minimum), scaled_value)
    return scaled_value


def _save_detail_memo_if_needed(canvas: tkinter.Canvas) -> bool:
    """Persist the currently open memo editor if it has unsaved changes."""

    text_widget = getattr(canvas, "detail_memo_text_widget", None)
    player_name = getattr(canvas, "detail_memo_player_name", "")
    loaded_text = getattr(canvas, "detail_memo_loaded_text", "")
    if text_widget is None or not player_name:
        return True
    if str(text_widget.cget("state")) == tkinter.DISABLED:
        return True
    current_text = text_widget.get("1.0", "end-1c")
    if current_text == loaded_text:
        return True
    try:
        save_player_profile_user_memo(player_name, current_text)
    except Exception as exc:
        status_label = getattr(canvas, "detail_memo_status_label", None)
        if status_label is not None:
            status_label.configure(text=f"Save failed: {exc}", fg="#fca5a5")
        return False
    memo_presence_cache = dict(getattr(canvas, "player_memo_presence_cache", {}))
    memo_presence_cache[player_name] = bool(current_text.strip())
    canvas.player_memo_presence_cache = memo_presence_cache
    canvas.detail_memo_loaded_text = current_text
    status_label = getattr(canvas, "detail_memo_status_label", None)
    if status_label is not None:
        status_label.configure(text="Saved", fg="#86efac")
    return True


def _save_detail_memo_in_background(canvas: tkinter.Canvas) -> bool:
    """Save the open memo without blocking Tk redraws."""

    text_widget = getattr(canvas, "detail_memo_text_widget", None)
    player_name = getattr(canvas, "detail_memo_player_name", "")
    loaded_text = getattr(canvas, "detail_memo_loaded_text", "")
    status_label = getattr(canvas, "detail_memo_status_label", None)
    save_button = getattr(canvas, "detail_memo_save_button", None)
    if text_widget is None or not player_name:
        return True
    if str(text_widget.cget("state")) == tkinter.DISABLED:
        return True
    current_text = text_widget.get("1.0", "end-1c")
    if current_text == loaded_text:
        return True

    request_id = int(getattr(canvas, "detail_memo_save_request_id", 0)) + 1
    canvas.detail_memo_save_request_id = request_id
    pending_request_ids = set(getattr(canvas, "detail_memo_pending_request_ids", set()))
    pending_request_ids.add(request_id)
    canvas.detail_memo_pending_request_ids = pending_request_ids
    if save_button is not None:
        save_button.configure(state=tkinter.DISABLED)
    if status_label is not None:
        status_label.configure(text="Saving...", fg="#7dd3fc")
    memo_presence_cache = dict(getattr(canvas, "player_memo_presence_cache", {}))
    memo_presence_cache[player_name] = bool(current_text.strip())
    canvas.player_memo_presence_cache = memo_presence_cache
    _ensure_memo_background_poll(canvas)
    redraw_action = getattr(canvas, "redraw_action", None)
    if callable(redraw_action):
        redraw_action()

    def _worker() -> None:
        save_error_text: str | None = None
        try:
            save_player_profile_user_memo(player_name, current_text)
        except Exception as exc:  # noqa: BLE001 - UI recovery path should handle any failure.
            save_error_text = str(exc)
        task_queue = getattr(canvas, "memo_background_task_queue", None)
        if task_queue is not None:
            task_queue.put(
                ("save", request_id, player_name, current_text, save_error_text)
            )

    _start_tracked_background_thread(
        label="memo save",
        name="detail-memo-save",
        target=_worker,
    )
    return True


def _handle_detail_memo_save_shortcut(
    canvas: tkinter.Canvas,
    _event: tkinter.Event | None = None,
) -> str:
    """Handle Ctrl+S inside the memo editor without letting Tk propagate the keypress."""

    _save_detail_memo_in_background(canvas)
    return "break"


def _request_player_memo_presence_prefetch(
    canvas: tkinter.Canvas,
    player_names: Iterable[object],
) -> None:
    """Load memo-presence flags in the background so redraw never touches disk."""

    normalized_names = tuple(
        dict.fromkeys(
            name
            for name in (
                str(raw_name).strip()
                for raw_name in player_names
            )
            if name
        )
    )
    if not normalized_names:
        return
    memo_presence_cache = dict(getattr(canvas, "player_memo_presence_cache", {}))
    pending_names = set(getattr(canvas, "player_memo_presence_pending_names", set()))
    request_names = tuple(
        name
        for name in normalized_names
        if name not in memo_presence_cache and name not in pending_names
    )
    if not request_names:
        return
    canvas.player_memo_presence_pending_names = pending_names.union(request_names)
    _ensure_memo_background_poll(canvas)

    def _worker() -> None:
        loaded_presence: dict[str, bool] = {}
        for player_name in request_names:
            try:
                profile = load_player_profile(player_name)
            except Exception:
                loaded_presence[player_name] = False
            else:
                loaded_presence[player_name] = bool(str(profile.get("user_memo", "")).strip())
        task_queue = getattr(canvas, "memo_background_task_queue", None)
        if task_queue is not None:
            task_queue.put(("presence", request_names, loaded_presence))

    _start_tracked_background_thread(
        label="memo presence",
        name="player-memo-presence",
        target=_worker,
    )


def _drain_memo_background_tasks(canvas: tkinter.Canvas) -> bool:
    """Apply queued background memo results on the Tk main thread."""

    task_queue = getattr(canvas, "memo_background_task_queue", None)
    if task_queue is None:
        return False
    changed = False
    while True:
        try:
            task = task_queue.get_nowait()
        except queue.Empty:
            break
        task_kind = task[0]
        if task_kind == "presence":
            request_names = task[1]
            loaded_presence = task[2]
            current_pending = set(getattr(canvas, "player_memo_presence_pending_names", set()))
            current_pending.difference_update(request_names)
            canvas.player_memo_presence_pending_names = current_pending
            current_cache = dict(getattr(canvas, "player_memo_presence_cache", {}))
            for player_name, has_memo in loaded_presence.items():
                if current_cache.get(player_name) == has_memo:
                    continue
                current_cache[player_name] = has_memo
                changed = True
            canvas.player_memo_presence_cache = current_cache
            continue
        if task_kind != "save":
            continue
        request_id = int(task[1])
        player_name = str(task[2])
        saved_text = str(task[3])
        save_error_text = task[4]
        pending_request_ids = set(getattr(canvas, "detail_memo_pending_request_ids", set()))
        pending_request_ids.discard(request_id)
        canvas.detail_memo_pending_request_ids = pending_request_ids
        active_player_name = getattr(canvas, "detail_memo_player_name", "")
        save_button_widget = getattr(canvas, "detail_memo_save_button", None)
        status_label_widget = getattr(canvas, "detail_memo_status_label", None)
        if save_error_text is None:
            if active_player_name == player_name and request_id == int(
                getattr(canvas, "detail_memo_save_request_id", 0)
            ):
                canvas.detail_memo_loaded_text = saved_text
                if status_label_widget is not None:
                    status_label_widget.configure(text="Saved", fg="#86efac")
            changed = True
        else:
            memo_cache = dict(getattr(canvas, "player_memo_presence_cache", {}))
            if active_player_name == player_name:
                memo_cache[player_name] = bool(getattr(canvas, "detail_memo_loaded_text", "").strip())
                if status_label_widget is not None:
                    status_label_widget.configure(text=f"Save failed: {save_error_text}", fg="#fca5a5")
            else:
                memo_cache.pop(player_name, None)
            canvas.player_memo_presence_cache = memo_cache
            changed = True
        if save_button_widget is not None and not pending_request_ids:
            save_button_widget.configure(state=tkinter.NORMAL)
    return changed


def _ensure_memo_background_poll(canvas: tkinter.Canvas) -> None:
    """Poll background memo tasks from the Tk thread until all pending work completes."""

    if getattr(canvas, "memo_background_poll_job", None) is not None:
        return

    def _poll() -> None:
        canvas.memo_background_poll_job = None
        changed = _drain_memo_background_tasks(canvas)
        if changed:
            redraw_action = getattr(canvas, "redraw_action", None)
            if callable(redraw_action):
                redraw_action()
        if (
            getattr(canvas, "player_memo_presence_pending_names", set())
            or getattr(canvas, "detail_memo_pending_request_ids", set())
        ):
            try:
                canvas.memo_background_poll_job = canvas.after(50, _poll)
            except tkinter.TclError:
                return

    try:
        canvas.memo_background_poll_job = canvas.after(50, _poll)
    except tkinter.TclError:
        return


def _hide_detail_memo_editor(canvas: tkinter.Canvas) -> None:
    """Hide the shared detail memo editor overlay."""

    memo_frame = getattr(canvas, "detail_memo_frame", None)
    if memo_frame is not None:
        memo_frame.place_forget()
    canvas.detail_memo_active_key = None


def _reset_round_ui_state(canvas: tkinter.Canvas) -> None:
    """Reset transient UI state when a new INIT creates a different round."""

    _save_detail_memo_if_needed(canvas)
    canvas.detail_panel_state = DetailPanelState()
    current_auto_mode_state = getattr(canvas, "hand_auto_mode_state", HandAutoModeState())
    # New rounds should not keep stale recommendation popups unless recommendation auto
    # mode is active, in which case `pystyle ON` should keep the panel visible.
    canvas.hand_response_panel_state = _resolve_hand_response_panel_state_for_auto_mode(
        None,
        auto_mode_enabled=bool(getattr(current_auto_mode_state, "enabled", False)),
        auto_mode=str(
            getattr(current_auto_mode_state, "mode", HAND_AUTO_MODE_KIND_RECOMMENDATION)
        ),
    )
    canvas.hand_response_button_spec = None
    canvas.hand_betaori_response_button_spec = None
    canvas.hand_response_render_state = None
    _reset_hand_auto_mode_volatile_state(canvas)
    canvas.last_self_hand_value_alert_kind = HAND_SELF_ALERT_KIND_NONE
    canvas.last_self_low_ev_sound_round_token = ""
    canvas.last_self_hand_alert_sound_monotonic_s = 0.0
    canvas.last_player_panel_alert_keys_by_seat = {
        seat: tuple() for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    canvas.last_player_panel_remain_sound_level_by_seat = {
        seat: 0 for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    canvas.last_player_panel_alert_sound_monotonic_s = 0.0
    canvas.same_jun_match_cache_key = None
    canvas.same_jun_match_cache_value = {}
    canvas.same_jun_public_event_source_state = None
    canvas.same_jun_match_candidate_cache_key = None
    canvas.same_jun_match_candidate_cache_value = {}
    canvas.same_jun_match_candidate_event_stream = ()
    canvas.same_jun_match_candidate_recent_public_events = ()
    canvas.same_jun_match_confirmed_cache_key = None
    canvas.same_jun_match_confirmed_cache_value = {}
    canvas.same_jun_match_async_result_queue = queue.Queue()
    canvas.same_jun_match_async_in_flight = False
    canvas.same_jun_match_async_pending_key = None
    _clear_background_queue(getattr(canvas, "inferred_visible_async_request_queue", None))
    _clear_background_queue(getattr(canvas, "inferred_visible_async_result_queue", None))
    canvas.inferred_visible_entry_excluded_seats = {}
    canvas.inferred_visible_deleted_entry_keys = set()
    canvas.inferred_visible_manual_counts_by_tile34 = {}
    canvas.inferred_visible_entries = []
    canvas.current_visible_tile_inference_summary = VisibleTileInferenceSummary()
    canvas.table_situation_scores_by_seat = {
        seat: _empty_table_situation_scores()
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    canvas.selected_inferred_visible_disabled_seats_by_tile34 = {}
    canvas.lag_marker_reference_kinds_by_entry = {}
    canvas.selected_inferred_visible_delete_button_specs = []
    canvas.selected_inferred_visible_tile_34_index = None
    canvas.selected_inferred_visible_tile_37 = None
    canvas.inferred_visible_async_in_flight = False
    canvas.inferred_visible_async_pending_key = None
    canvas.inferred_visible_async_requested_key = None
    canvas.inferred_visible_async_completed_cache_key = None
    canvas.player_push_alert_latches_by_seat = {
        seat: _empty_player_push_alert_payload(seat)
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    canvas.player_push_marker_latches_by_seat = _empty_player_push_marker_indices_by_seat()
    _hide_detail_memo_editor(canvas)


def _resolve_hand_auto_mode_button_presentation(
    auto_mode_state: HandAutoModeState,
    *,
    target_mode: str,
    label_prefix: str,
    action_available: bool,
) -> tuple[str, str, str, str]:
    """Return one `(label, bg, fg, state)` tuple for one specific auto-mode button."""

    if not action_available:
        return (
            f"{label_prefix} N/A",
            HAND_AUTO_BUTTON_DISABLED_FILL,
            HAND_AUTO_BUTTON_DISABLED_TEXT,
            tkinter.DISABLED,
        )
    is_active_mode = bool(auto_mode_state.enabled) and (
        str(getattr(auto_mode_state, "mode", HAND_AUTO_MODE_KIND_RECOMMENDATION)) == str(target_mode)
    )
    if is_active_mode and auto_mode_state.in_flight:
        return (f"{label_prefix} RUN", HAND_AUTO_BUTTON_RUN_FILL, HAND_AUTO_BUTTON_TEXT, tkinter.NORMAL)
    if is_active_mode and auto_mode_state.last_error:
        return (f"{label_prefix} ERR", HAND_AUTO_BUTTON_ERROR_FILL, HAND_AUTO_BUTTON_TEXT, tkinter.NORMAL)
    if is_active_mode:
        return (f"{label_prefix} ON", HAND_AUTO_BUTTON_ON_FILL, HAND_AUTO_BUTTON_TEXT, tkinter.NORMAL)
    return (f"{label_prefix} OFF", HAND_AUTO_BUTTON_OFF_FILL, HAND_AUTO_BUTTON_TEXT, tkinter.NORMAL)


def _refresh_hand_auto_mode_button_widget(canvas: tkinter.Canvas) -> None:
    """Refresh the external pystyle/betaori auto buttons to match current state."""

    auto_mode_state = getattr(canvas, "hand_auto_mode_state", HandAutoModeState())
    shared_action_available = (
        callable(getattr(canvas, "hand_auto_discard_action", None))
        or callable(getattr(canvas, "hand_bridge_discard_by_index_action", None))
    )
    button_specs = (
        (
            getattr(canvas, "hand_pystyle_auto_mode_button", None),
            HAND_AUTO_MODE_KIND_RECOMMENDATION,
            "pystyle",
        ),
        (
            getattr(canvas, "hand_betaori_auto_mode_button", None),
            HAND_AUTO_MODE_KIND_BETAORI,
            "ベタオリ",
        ),
    )
    for button_widget, target_mode, label_prefix in button_specs:
        if button_widget is None:
            continue
        label, background, foreground, button_state = _resolve_hand_auto_mode_button_presentation(
            auto_mode_state,
            target_mode=target_mode,
            label_prefix=label_prefix,
            action_available=shared_action_available,
        )
        button_widget.configure(
            text=label,
            state=button_state,
            bg=background,
            fg=foreground,
            activebackground=background,
            activeforeground=foreground,
            disabledforeground=foreground,
        )


def _refresh_table_situation_visibility_button_widget(canvas: tkinter.Canvas) -> None:
    """Refresh the external situation-panel visibility button to match current state."""

    button_widget = getattr(canvas, "table_situation_visibility_button", None)
    if button_widget is None:
        return
    if not TABLE_SITUATION_ENABLED:
        try:
            button_widget.place_forget()
        except Exception:
            pass
        return
    is_visible = bool(getattr(canvas, "table_situation_panels_visible", True))
    label = "場況 ON" if is_visible else "場況 OFF"
    background = HAND_AUTO_BUTTON_ON_FILL if is_visible else HAND_AUTO_BUTTON_OFF_FILL
    foreground = HAND_AUTO_BUTTON_TEXT
    button_widget.configure(
        text=label,
        state=tkinter.NORMAL,
        bg=background,
        fg=foreground,
        activebackground=background,
        activeforeground=foreground,
        disabledforeground=foreground,
    )


def _extract_hand_auto_discard_error(result_payload: Mapping[str, object] | None) -> str:
    """Return an error string when one bridge-side auto-discard result is not successful."""

    if not isinstance(result_payload, Mapping):
        return "AUTO_DISCARD_NO_RESULT"
    nested_result = result_payload.get("result")
    if isinstance(nested_result, Mapping):
        if bool(nested_result.get("ok", False)):
            return ""
        return str(nested_result.get("error", "AUTO_DISCARD_FAILED"))
    if bool(result_payload.get("ok", False)):
        return ""
    return str(result_payload.get("error", "AUTO_DISCARD_FAILED"))


def _resolve_hand_auto_discard_delay_s(
    auto_mode: str,
    *,
    has_usable_pystyle_response: bool = False,
    recommendation_timeout_elapsed: bool = False,
    rng: Any = None,
) -> float:
    """Return the pre-discard wait for one auto mode."""

    normalized_mode = str(auto_mode or HAND_AUTO_MODE_KIND_RECOMMENDATION)
    if normalized_mode == HAND_AUTO_MODE_KIND_RECOMMENDATION:
        if recommendation_timeout_elapsed:
            return HAND_PYSTYLE_TIMEOUT_FALLBACK_DELAY_S
        base_delay_s = HAND_PYSTYLE_AUTO_THINK_DELAY_S
        if has_usable_pystyle_response:
            base_delay_s += HAND_PYSTYLE_RESPONSE_EXTRA_THINK_DELAY_S
        return base_delay_s
    if normalized_mode != HAND_AUTO_MODE_KIND_BETAORI:
        return 0.0
    random_source = rng if rng is not None else random
    try:
        swing_s = float(
            random_source.uniform(
                -HAND_BETAORI_AUTO_THINK_SWING_S,
                HAND_BETAORI_AUTO_THINK_SWING_S,
            )
        )
    except Exception:
        swing_s = 0.0
    return max(0.0, HAND_BETAORI_AUTO_THINK_BASE_S + swing_s)


def _bridge_status_snapshot_for_worker(canvas: tkinter.Canvas) -> TenhouUiBridgeStatus | None:
    """Read bridge status from a worker thread without mutating UI feedback state."""

    provider = getattr(canvas, "bridge_status_provider", None)
    if not callable(provider):
        return None
    try:
        status = provider()
    except Exception:
        return None
    if not isinstance(status, TenhouUiBridgeStatus):
        return None
    return status


def _build_pystyle_auto_discard_action_with_riichi_guard(
    canvas: tkinter.Canvas,
    discard_action: Callable[[int], Mapping[str, object] | None],
    *,
    allow_riichi: bool,
) -> Callable[[int], Mapping[str, object] | None]:
    """Return one delayed pystyle action that still upgrades into riichi when it appears."""

    def _action(tile_37: int) -> Mapping[str, object] | None:
        if allow_riichi:
            bridge_status = _bridge_status_snapshot_for_worker(canvas)
            bridge_click_control_action = getattr(canvas, "bridge_click_control_action", None)
            riichi_control_id = _select_visible_bridge_control_id(
                bridge_status,
                BRIDGE_RIICHI_CONTROL_IDS,
                text_hints=("リーチ", "riichi", "reach"),
            )
            if riichi_control_id is not None and callable(bridge_click_control_action):
                return bridge_click_control_action(int(riichi_control_id))
        return discard_action(int(tile_37))

    return _action


def _select_visible_bridge_control_id(
    status: TenhouUiBridgeStatus | None,
    control_ids: Collection[int],
    *,
    text_hints: Sequence[str] = (),
) -> int | None:
    """Return the first currently visible bridge control id that matches one known id or text hint."""

    normalized_control_ids = {int(control_id) for control_id in control_ids}
    normalized_text_hints = tuple(str(hint).strip().lower() for hint in text_hints if str(hint).strip())
    for control in tuple(getattr(status, "visible_controls", ()) if status is not None else ()):
        control_id = int(getattr(control, "control_id", 0) or 0)
        if control_id in normalized_control_ids:
            return control_id
        label_text = str(getattr(control, "text", "") or getattr(control, "label", "") or "").strip().lower()
        if label_text and any(hint in label_text for hint in normalized_text_hints):
            return control_id
    return None


def _lookup_bridge_toggle_control(
    status: TenhouUiBridgeStatus | None,
    control_id: int,
) -> object | None:
    """Return one toggle-control snapshot by id when it exists."""

    target_control_id = int(control_id)
    for toggle_control in tuple(getattr(status, "toggle_controls", ()) if status is not None else ()):
        if int(getattr(toggle_control, "control_id", 0) or 0) == target_control_id:
            return toggle_control
    return None


def _has_open_self_meld(self_melds: Sequence[Meld]) -> bool:
    """Return whether the current self hand is open for riichi eligibility purposes."""

    return any(bool(getattr(meld, "is_open", False)) for meld in self_melds)


def _reset_hand_auto_mode_volatile_state(
    canvas: tkinter.Canvas,
    *,
    clear_turn_timing: bool = True,
) -> None:
    """Clear transient AUTO retry/dedupe state while preserving the selected mode."""

    current_auto_mode_state = getattr(canvas, "hand_auto_mode_state", HandAutoModeState())
    canvas.hand_auto_mode_state = HandAutoModeState(
        enabled=bool(getattr(current_auto_mode_state, "enabled", False)),
        mode=str(getattr(current_auto_mode_state, "mode", HAND_AUTO_MODE_KIND_RECOMMENDATION)),
    )
    canvas.hand_response_requested_hand_key = None
    canvas.hand_response_last_request_started_monotonic_s = None
    if clear_turn_timing:
        canvas.hand_response_turn_started_monotonic_s = None
        canvas.hand_response_turn_display_key = None
        canvas.hand_response_timeout_fallback_applied_turn_key = None
    reset_action = getattr(canvas, "hand_recommendation_reset_action", None)
    if callable(reset_action):
        reset_action()


def _pause_hand_auto_mode_for_bridge_drop(canvas: tkinter.Canvas) -> None:
    """Stop in-flight AUTO work after a bridge drop while preserving per-hand dedupe."""

    current_auto_mode_state = getattr(canvas, "hand_auto_mode_state", HandAutoModeState())
    canvas.hand_auto_mode_state = replace(
        current_auto_mode_state,
        in_flight=False,
        last_error="Bridge not ready",
    )
    canvas.hand_response_requested_hand_key = None
    canvas.hand_response_last_request_started_monotonic_s = None
    canvas.hand_response_turn_started_monotonic_s = None
    canvas.hand_response_turn_display_key = None
    canvas.hand_response_timeout_fallback_applied_turn_key = None
    reset_action = getattr(canvas, "hand_recommendation_reset_action", None)
    if callable(reset_action):
        reset_action()


def _restart_hand_recommendation_request_after_timeout(
    canvas: tkinter.Canvas,
    request_hand_tiles: Sequence[int],
    display_context: PystyleDisplayContext | None,
    current_request_display_key: tuple[object, ...],
    *,
    auto_mode_enabled: bool,
    recommendation_timeout_elapsed: bool,
) -> bool:
    """Reset and immediately re-request pystyle after one AUTO timeout fallback."""

    if not auto_mode_enabled or not recommendation_timeout_elapsed:
        return False
    _reset_hand_auto_mode_volatile_state(canvas, clear_turn_timing=False)
    request_action = getattr(canvas, "hand_recommendation_request_action", None)
    if not callable(request_action):
        return False
    restart_started_monotonic_s = time.monotonic()
    canvas.hand_response_requested_hand_key = current_request_display_key
    canvas.hand_response_last_request_started_monotonic_s = restart_started_monotonic_s
    canvas.hand_response_timeout_fallback_applied_turn_key = current_request_display_key
    request_action(request_hand_tiles, display_context)
    return True


def _restart_hand_recommendation_request_after_error(
    canvas: tkinter.Canvas,
    request_hand_tiles: Sequence[int],
    display_context: PystyleDisplayContext | None,
    current_request_display_key: tuple[object, ...],
    *,
    auto_mode_enabled: bool,
    recommendation_error_fallback_active: bool,
) -> bool:
    """Reset and immediately re-request pystyle after one AUTO error fallback."""

    if not auto_mode_enabled or not recommendation_error_fallback_active:
        return False
    request_action = getattr(canvas, "hand_recommendation_request_action", None)
    _reset_hand_auto_mode_volatile_state(canvas, clear_turn_timing=False)
    if not callable(request_action):
        return False
    restart_started_monotonic_s = time.monotonic()
    canvas.hand_response_requested_hand_key = current_request_display_key
    canvas.hand_response_last_request_started_monotonic_s = restart_started_monotonic_s
    request_action(request_hand_tiles, display_context)
    return True


def _drain_hand_auto_mode_result_queue(canvas: tkinter.Canvas) -> bool:
    """Apply background auto-discard worker results to the canvas-side state."""

    result_queue = getattr(canvas, "hand_auto_mode_result_queue", None)
    if result_queue is None:
        return False
    changed = False
    while True:
        try:
            result_payload = result_queue.get_nowait()
        except queue.Empty:
            break
        if not isinstance(result_payload, Mapping):
            continue
        auto_mode_state = getattr(canvas, "hand_auto_mode_state", HandAutoModeState())
        attempt_key = result_payload.get("attempt_key")
        if attempt_key != auto_mode_state.last_attempt_key:
            continue
        normalized_attempt_key = (
            tuple(attempt_key)
            if isinstance(attempt_key, tuple)
            else tuple(attempt_key or ())
        )
        last_error = _extract_hand_auto_discard_error(result_payload.get("result_payload"))
        if last_error and len(normalized_attempt_key) >= 2:
            attempt_prefix = str(normalized_attempt_key[0] or "")
            if attempt_prefix in {"auto_auto_agari_on", "auto_naki_disabled_on"}:
                try:
                    failed_control_id = int(normalized_attempt_key[1])
                except (TypeError, ValueError):
                    failed_control_id = 0
                if failed_control_id > 0:
                    _set_bridge_toggle_override(canvas, failed_control_id, None)
        canvas.hand_auto_mode_state = replace(
            auto_mode_state,
            in_flight=False,
            last_error=last_error,
        )
        changed = True
    return changed


def _queue_bridge_background_action(
    canvas: tkinter.Canvas,
    *,
    kind: str,
    action: Callable[..., Mapping[str, object] | None],
    args: Sequence[object] = (),
    meta: Mapping[str, object] | None = None,
) -> bool:
    """Run one bridge command in the background and report the outcome back to Tk."""

    if not callable(action):
        return False
    result_queue = getattr(canvas, "bridge_background_result_queue", None)
    if result_queue is None:
        result_queue = queue.Queue()
        canvas.bridge_background_result_queue = result_queue

    def _worker() -> None:
        try:
            result_payload = action(*args)
            result_queue.put(
                {
                    "kind": kind,
                    "meta": dict(meta or {}),
                    "ok": True,
                    "result_payload": result_payload,
                }
            )
        except Exception as exc:  # noqa: BLE001 - bridge failures must surface in the local UI.
            result_queue.put(
                {
                    "kind": kind,
                    "meta": dict(meta or {}),
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    _start_tracked_background_thread(
        label=f"bridge {kind}",
        name=f"bridge-{kind}",
        target=_worker,
    )
    return True


def _set_bridge_feedback(
    canvas: tkinter.Canvas,
    text: str,
    *,
    is_error: bool,
) -> None:
    """Store one short bridge status message for the external bridge widget."""

    canvas.bridge_feedback_text = str(text or "").strip()
    canvas.bridge_feedback_is_error = bool(is_error)
    canvas.bridge_feedback_expires_monotonic_s = time.monotonic() + (
        BRIDGE_STATUS_ERROR_TTL_S if is_error else BRIDGE_STATUS_SUCCESS_TTL_S
    )


def _clear_bridge_feedback_if_expired(canvas: tkinter.Canvas) -> None:
    """Clear the transient bridge status message after its TTL passes."""

    expires_at = float(getattr(canvas, "bridge_feedback_expires_monotonic_s", 0.0) or 0.0)
    if expires_at <= 0.0 or time.monotonic() < expires_at:
        return
    canvas.bridge_feedback_text = ""
    canvas.bridge_feedback_is_error = False
    canvas.bridge_feedback_expires_monotonic_s = 0.0


def show_thread_activity_notice(label: str) -> None:
    """Show one short top-right notice describing one background thread start."""

    _update_thread_activity_notice(label)


def begin_thread_activity_notice(label: str) -> None:
    """Mark one background thread label as newly active and refresh the top-right notice."""

    _update_thread_activity_notice(label, active_delta=1)


def finish_thread_activity_notice(label: str) -> None:
    """Mark one background thread label as finished and refresh the top-right notice."""

    _update_thread_activity_notice(label, active_delta=-1)


def _update_thread_activity_notice(label: str, active_delta: int | None = None) -> None:
    """Update one notice entry, optionally changing the currently active thread count."""

    text = str(label or "").strip()
    if not text:
        return
    canvas = _THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS
    if canvas is None:
        return

    def _apply() -> None:
        if not canvas.winfo_exists():
            return
        now_monotonic_s = time.monotonic()
        expires_monotonic_s = now_monotonic_s + THREAD_ACTIVITY_NOTICE_TTL_S
        active_entries = [
            dict(entry)
            for entry in tuple(getattr(canvas, "thread_activity_notice_entries", ()))
            if (
                int(entry.get("active_count", 0) or 0) > 0
                or float(entry.get("expires_monotonic_s", 0.0) or 0.0) > now_monotonic_s
            )
        ]
        existing_entry: dict[str, object] | None = None
        remaining_entries: list[dict[str, object]] = []
        for entry in active_entries:
            if str(entry.get("text", "") or "").strip() == text and existing_entry is None:
                existing_entry = entry
                continue
            remaining_entries.append(entry)
        current_active_count = int(existing_entry.get("active_count", 0) or 0) if existing_entry else 0
        if active_delta is None:
            next_active_count = current_active_count
        else:
            next_active_count = max(0, current_active_count + int(active_delta))
        if existing_entry is None and active_delta is not None and active_delta < 0:
            return
        updated_entry = {
            "text": text,
            "count": max(1, next_active_count),
            "active_count": next_active_count,
            "expires_monotonic_s": expires_monotonic_s,
        }
        active_entries = [updated_entry, *remaining_entries]
        canvas.thread_activity_notice_entries = active_entries
        first_entry = active_entries[0] if active_entries else {}
        canvas.thread_activity_notice_text = str(first_entry.get("text", "") or "")
        canvas.thread_activity_notice_expires_monotonic_s = float(
            first_entry.get("expires_monotonic_s", 0.0) or 0.0
        )
        last_redraw_monotonic_s = float(
            getattr(canvas, "last_thread_activity_notice_redraw_monotonic_s", 0.0) or 0.0
        )
        should_redraw = (
            now_monotonic_s - last_redraw_monotonic_s >= THREAD_ACTIVITY_NOTICE_REDRAW_MIN_INTERVAL_S
        )
        if not bool(getattr(canvas, "redraw_in_progress", False)) and should_redraw:
            canvas.last_thread_activity_notice_redraw_monotonic_s = now_monotonic_s
            redraw_action = getattr(canvas, "redraw_action", None)
            if callable(redraw_action):
                redraw_action()

    if threading.current_thread() is threading.main_thread():
        _apply()
        return
    try:
        canvas.after(0, _apply)
    except tkinter.TclError:
        return


def _start_tracked_background_thread(
    *,
    label: str,
    name: str,
    target: Callable[..., object],
    args: Sequence[object] = (),
    kwargs: Mapping[str, object] | None = None,
) -> threading.Thread:
    """Start one short-lived background thread and keep the active-count notice in sync."""

    begin_thread_activity_notice(label)

    def _wrapped_target() -> None:
        try:
            target(*args, **dict(kwargs or {}))
        finally:
            finish_thread_activity_notice(label)

    worker_thread = threading.Thread(
        target=_wrapped_target,
        name=name,
        daemon=True,
    )
    worker_thread.start()
    return worker_thread


def _clear_thread_activity_notice_if_expired(canvas: tkinter.Canvas) -> None:
    """Drop expired top-right thread activity notices once their TTL elapsed."""

    now_monotonic_s = time.monotonic()
    active_entries = [
        dict(entry)
        for entry in tuple(getattr(canvas, "thread_activity_notice_entries", ()))
        if (
            int(entry.get("active_count", 0) or 0) > 0
            or float(entry.get("expires_monotonic_s", 0.0) or 0.0) > now_monotonic_s
        )
    ]
    canvas.thread_activity_notice_entries = active_entries
    first_entry = active_entries[0] if active_entries else {}
    canvas.thread_activity_notice_text = str(first_entry.get("text", "") or "")
    canvas.thread_activity_notice_expires_monotonic_s = float(
        first_entry.get("expires_monotonic_s", 0.0) or 0.0
    )


def _clear_background_queue(task_queue: queue.Queue | None) -> None:
    """Best-effort drain of one background-task queue without blocking."""

    if task_queue is None:
        return
    while True:
        try:
            task_queue.get_nowait()
        except queue.Empty:
            break


def _draw_thread_activity_notice(canvas: tkinter.Canvas) -> None:
    """Draw current short-lived background-thread notices near the top-right corner."""

    _delete_canvas_items_by_tags(canvas, _THREAD_ACTIVITY_NOTICE_TAG)
    _clear_thread_activity_notice_if_expired(canvas)
    notice_entries = tuple(getattr(canvas, "thread_activity_notice_entries", ()))
    if not notice_entries:
        return
    previous_item_ids = _capture_canvas_item_ids(canvas)
    right = max(canvas.winfo_width(), WINDOW_MIN_WIDTH) - 12
    top = 12
    for entry in notice_entries:
        notice_text = str(entry.get("text", "") or "").strip()
        if not notice_text:
            continue
        count = int(entry.get("count", 1) or 1)
        suffix = f" x{count}"
        text_id = canvas.create_text(
            right,
            top,
            text=f"BG {notice_text}{suffix}",
            fill=THREAD_ACTIVITY_NOTICE_TEXT,
            font=("Consolas", 8, "bold"),
            anchor=tkinter.NE,
        )
        bbox = canvas.bbox(text_id)
        if bbox is None:
            continue
        left, top_edge, right_edge, bottom = bbox
        rect_id = canvas.create_rectangle(
            left - 6,
            top_edge - 4,
            right_edge + 6,
            bottom + 4,
            fill=THREAD_ACTIVITY_NOTICE_FILL,
            outline=THREAD_ACTIVITY_NOTICE_OUTLINE,
            width=1,
        )
        canvas.tag_raise(text_id, rect_id)
        top = bottom + 10
    _tag_new_canvas_items(
        canvas,
        tag=_THREAD_ACTIVITY_NOTICE_TAG,
        previous_item_ids=previous_item_ids,
    )


def _bridge_status_snapshot(canvas: tkinter.Canvas) -> TenhouUiBridgeStatus | None:
    """Read the latest bridge status snapshot through the injected provider when available."""

    provider = getattr(canvas, "bridge_status_provider", None)
    if not callable(provider):
        return None
    try:
        status = provider()
    except Exception as exc:  # noqa: BLE001 - keep the UI alive even if debug status fails once.
        _set_bridge_feedback(canvas, f"Bridge status failed: {exc}", is_error=True)
        return None
    if not isinstance(status, TenhouUiBridgeStatus):
        return None
    return status


def _bridge_ui_snapshot_result(status: TenhouUiBridgeStatus | None) -> Mapping[str, object] | None:
    """Return the last `ui_snapshot_result.result` payload when one exists."""

    if status is None:
        return None
    last_result = status.last_result
    if not isinstance(last_result, Mapping):
        return None
    if str(last_result.get("type", "")) != "ui_snapshot_result":
        return None
    result = last_result.get("result")
    if not isinstance(result, Mapping):
        return None
    return result


def _should_request_bridge_ui_snapshot_on_tick(
    canvas: tkinter.Canvas,
    status: TenhouUiBridgeStatus | None,
) -> bool:
    """Return whether one bridge tick should trigger a fresh `ui_snapshot` request."""

    if status is None:
        return False
    if not bool(status.listening and status.connected and status.extension_ready):
        return False
    if str(getattr(status, "last_event", "") or "") in {"client_connected", "extension_ready"}:
        return True
    if _bridge_ui_snapshot_result(status) is None:
        return True
    current_source_refresh_token = getattr(
        canvas,
        "bridge_snapshot_source_refresh_token",
        None,
    )
    last_requested_source_refresh_token = getattr(
        canvas,
        "bridge_last_requested_source_refresh_token",
        None,
    )
    return current_source_refresh_token != last_requested_source_refresh_token


def _is_bridge_ready_for_hand_auto(status: TenhouUiBridgeStatus | None) -> bool:
    """Return whether the current bridge snapshot is actionable for AUTO discard replay."""

    if status is None:
        return False
    if not (status.listening and status.connected and status.extension_ready):
        return False
    snapshot_result = _bridge_ui_snapshot_result(status)
    if not isinstance(snapshot_result, Mapping):
        return False
    if not bool(snapshot_result.get("ok", False)):
        return False
    return bool(snapshot_result.get("tenhouReady", False))


def _sync_hand_auto_mode_bridge_readiness(
    canvas: tkinter.Canvas,
    status: TenhouUiBridgeStatus | None = None,
) -> bool:
    """Rearm AUTO after bridge/page reloads so the same hand can POST/discard again."""

    ready_now = _is_bridge_ready_for_hand_auto(
        status if status is not None else _bridge_status_snapshot(canvas)
    )
    previous_ready = getattr(canvas, "bridge_hand_auto_ready", None)
    rearm_pending = bool(getattr(canvas, "bridge_hand_auto_rearm_pending", False))
    if previous_ready is None:
        canvas.bridge_hand_auto_ready = ready_now
        canvas.bridge_hand_auto_rearm_pending = not ready_now
        if not ready_now:
            _pause_hand_auto_mode_for_bridge_drop(canvas)
        return False
    if not ready_now:
        canvas.bridge_hand_auto_ready = False
        canvas.bridge_hand_auto_rearm_pending = True
        if bool(previous_ready) or not rearm_pending:
            _pause_hand_auto_mode_for_bridge_drop(canvas)
            return True
        return False
    canvas.bridge_hand_auto_ready = True
    if rearm_pending or not bool(previous_ready):
        canvas.bridge_hand_auto_rearm_pending = False
        return True
    canvas.bridge_hand_auto_rearm_pending = False
    return False


def _bridge_status_presentation(
    canvas: tkinter.Canvas,
) -> tuple[str, str, str]:
    """Return one compact `(text, bg, fg)` tuple for the bridge status label."""

    _clear_bridge_feedback_if_expired(canvas)
    feedback_text = str(getattr(canvas, "bridge_feedback_text", "") or "").strip()
    if feedback_text:
        if bool(getattr(canvas, "bridge_feedback_is_error", False)):
            return feedback_text, "#5b1e28", "#fecaca"
        return feedback_text, "#1f5136", "#d1fae5"

    status = _bridge_status_snapshot(canvas)
    if status is None:
        return "Bridge N/A", "#3a4250", "#9aa4b5"
    if not status.listening:
        return "Bridge OFF", "#3a4250", "#9aa4b5"
    if not status.connected:
        return "Bridge WS wait", "#4c3b1f", "#fde68a"
    if not status.extension_ready:
        return "Bridge EXT wait", "#4c3b1f", "#fde68a"

    snapshot_result = _bridge_ui_snapshot_result(status)
    if snapshot_result is not None:
        if bool(snapshot_result.get("ok", False)):
            if bool(snapshot_result.get("tenhouReady", False)):
                layout_mode = str(snapshot_result.get("layoutMode", "ready") or "ready")
                visible_controls = getattr(status, "visible_controls", ())
                return (
                    f"Bridge {layout_mode} ctrls={len(tuple(visible_controls))}",
                    "#1f5136",
                    "#d1fae5",
                )
            return "Bridge tab not ready", "#4c3b1f", "#fde68a"
        error_text = str(snapshot_result.get("error", "ui_snapshot failed") or "ui_snapshot failed")
        return f"Bridge ERR {error_text}", "#5b1e28", "#fecaca"

    if status.last_error:
        return f"Bridge ERR {status.last_error}", "#5b1e28", "#fecaca"
    return "Bridge connected", "#1d4f91", "#dbeafe"


def _bridge_control_button_label(control_id: int, raw_text: str) -> str:
    """Return one compact label for one visible bridge control button."""

    normalized_text = str(raw_text or "").strip()
    if normalized_text:
        return normalized_text
    return f"control:{int(control_id)}"


def _bridge_toggle_button_label(toggle_control: object, *, active: bool | None = None) -> str:
    """Return one compact app-side label for one persistent bridge toggle button."""

    label_text = str(getattr(toggle_control, "label", "") or getattr(toggle_control, "text", "") or "").strip()
    if not label_text:
        label_text = f"toggle:{int(getattr(toggle_control, 'control_id', 0) or 0)}"
    resolved_active = bool(getattr(toggle_control, "active", False)) if active is None else bool(active)
    state_text = "ON" if resolved_active else "OFF"
    return f"{label_text} {state_text}"


def _format_bridge_point_text(point_payload: Mapping[str, object] | None) -> str:
    """Return one compact `@x,y` string from one bridge point payload when present."""

    if not isinstance(point_payload, Mapping):
        return ""
    try:
        point_x = float(point_payload.get("x", 0.0))
        point_y = float(point_payload.get("y", 0.0))
    except (TypeError, ValueError):
        return ""
    return f" @{point_x:.0f},{point_y:.0f}"


def _format_bridge_success_feedback(kind: str, nested_result: Mapping[str, object]) -> str:
    """Return one short success string that exposes where the bridge click was sent."""

    point_text = _format_bridge_point_text(
        nested_result.get("point") if isinstance(nested_result.get("point"), Mapping) else None
    )
    layout_mode = str(nested_result.get("layoutMode", "") or "").strip()
    slot_strategy = str(nested_result.get("slotStrategy", "") or "").strip()
    try:
        detected_slot_count = int(nested_result.get("detectedHandSlotCount", 0) or 0)
    except (TypeError, ValueError):
        detected_slot_count = 0
    target_text = str(
        nested_result.get("dispatchTarget", nested_result.get("text", nested_result.get("controlId", ""))) or ""
    ).strip()
    hit_target_text = str(nested_result.get("hitTarget", "") or "").strip()
    if kind == "discard":
        slot_text = str(nested_result.get("handIndex", "?") or "?")
        parts = [f"Discard slot {slot_text}"]
        if layout_mode:
            parts.append(layout_mode)
        if detected_slot_count > 0:
            parts.append(f"slots={detected_slot_count}")
        if slot_strategy:
            parts.append(slot_strategy)
        if target_text:
            parts.append(target_text)
        if hit_target_text and hit_target_text != target_text:
            parts.append(f"hit={hit_target_text}")
        message = " ".join(parts)
        return f"{message}{point_text}"
    if kind == "control":
        label_text = str(nested_result.get("text", nested_result.get("controlId", "?")) or "?")
        if target_text and target_text != label_text:
            return f"Control {label_text} {target_text}{point_text}"
        return f"Control {label_text}{point_text}"
    if kind == "map":
        try:
            mapped_hand_tile_count = int(nested_result.get("mappedHandTileCount", 0) or 0)
        except (TypeError, ValueError):
            mapped_hand_tile_count = 0
        try:
            mapped_discard_count_total = int(nested_result.get("mappedDiscardCountTotal", 0) or 0)
        except (TypeError, ValueError):
            mapped_discard_count_total = 0
        try:
            mapped_riichi_seat_count = int(nested_result.get("mappedRiichiSeatCount", 0) or 0)
        except (TypeError, ValueError):
            mapped_riichi_seat_count = 0
        parts = ["Mapped browser table"]
        if mapped_hand_tile_count > 0:
            parts.append(f"hand={mapped_hand_tile_count}")
        if mapped_discard_count_total > 0:
            parts.append(f"discards={mapped_discard_count_total}")
        if mapped_riichi_seat_count > 0:
            parts.append(f"riichi={mapped_riichi_seat_count}")
        return " ".join(parts)
    return f"Bridge action sent{point_text}"


def _dispatch_bridge_control_click(
    canvas: tkinter.Canvas,
    control_id: int,
    *,
    feedback_text: str | None = None,
) -> bool:
    """Queue one bridge control click and show immediate feedback in the bridge widget."""

    action = getattr(canvas, "bridge_click_control_action", None)
    if not callable(action):
        _set_bridge_feedback(canvas, "Bridge control unavailable", is_error=True)
        _refresh_bridge_widgets(canvas)
        return False
    status = _bridge_status_snapshot(canvas)
    for toggle_control in tuple(getattr(status, "toggle_controls", ()) if status is not None else ()):
        if int(getattr(toggle_control, "control_id", 0) or 0) != int(control_id):
            continue
        toggle_overrides = dict(getattr(canvas, "bridge_toggle_active_overrides", {}))
        current_active = bool(
            toggle_overrides.get(
                int(control_id),
                bool(getattr(toggle_control, "active", False)),
            )
        )
        toggle_overrides[int(control_id)] = not current_active
        canvas.bridge_toggle_active_overrides = toggle_overrides
        break
    _set_bridge_feedback(
        canvas,
        str(feedback_text or f"Bridge control {int(control_id)}..."),
        is_error=False,
    )
    _refresh_bridge_widgets(canvas)
    return _queue_bridge_background_action(
        canvas,
        kind="control",
        action=action,
        args=(int(control_id),),
        meta={"control_id": int(control_id)},
    )


def _dispatch_bridge_discard_by_index(
    canvas: tkinter.Canvas,
    hand_index: int,
    *,
    feedback_text: str | None = None,
) -> bool:
    """Queue one bridge discard-by-index action and show immediate feedback in the bridge widget."""

    action = getattr(canvas, "hand_bridge_discard_by_index_action", None)
    if not callable(action):
        _set_bridge_feedback(canvas, "Bridge discard unavailable", is_error=True)
        _refresh_bridge_widgets(canvas)
        return False
    _set_bridge_feedback(
        canvas,
        str(feedback_text or f"Discard slot {int(hand_index)}..."),
        is_error=False,
    )
    _refresh_bridge_widgets(canvas)
    return _queue_bridge_background_action(
        canvas,
        kind="discard",
        action=action,
        args=(int(hand_index),),
    )


def _select_bridge_skip_control_id(status: TenhouUiBridgeStatus | None) -> int | None:
    """Return the best visible pass/skip control id for one right-click action when available."""

    if status is None:
        return None
    visible_controls = tuple(getattr(status, "visible_controls", ()) or ())
    visible_control_ids = {
        int(getattr(control, "control_id", 0) or 0)
        for control in visible_controls
    }
    if BRIDGE_SKIP_CONTROL_ID in visible_control_ids:
        return BRIDGE_SKIP_CONTROL_ID
    for control in visible_controls:
        control_id = int(getattr(control, "control_id", 0) or 0)
        label_text = str(
            getattr(control, "text", "") or getattr(control, "label", "") or ""
        ).strip().lower()
        if not label_text:
            continue
        if any(hint in label_text for hint in BRIDGE_SKIP_CONTROL_LABEL_HINTS):
            return control_id
    return None


def _resolve_self_hand_tsumogiri_index(
    click_specs: Sequence[SelfHandBridgeClickSpec],
) -> int | None:
    """Return the currently displayed rightmost self-hand slot used for tsumogiri."""

    if not click_specs:
        return None
    sorted_indexes = sorted({int(click_spec.hand_index) for click_spec in click_specs})
    if not sorted_indexes:
        return None
    max_index = sorted_indexes[-1]
    visible_slot_count = max_index + 1
    if (
        visible_slot_count <= 13
        and visible_slot_count % 3 == 1
        and sorted_indexes == list(range(visible_slot_count))
    ):
        # When live capture is one draw behind, the local UI can briefly show only the concealed
        # tiles. In that case, tsumogiri should target the next slot that exists on the page.
        return visible_slot_count
    return max_index


def _resolve_bridge_toggle_active_state(
    reported_active: bool,
    override_active: bool | None,
) -> tuple[bool, bool]:
    """Return `(display_active, clear_override)` for one toggle button."""

    if override_active is None:
        return bool(reported_active), False
    normalized_override_active = bool(override_active)
    normalized_reported_active = bool(reported_active)
    if normalized_reported_active == normalized_override_active:
        return normalized_reported_active, True
    return normalized_override_active, False


def _set_bridge_toggle_override(
    canvas: tkinter.Canvas,
    control_id: int,
    active: bool | None,
) -> None:
    """Set or clear one optimistic toggle-state override until the next snapshot confirms it."""

    toggle_overrides = dict(getattr(canvas, "bridge_toggle_active_overrides", {}))
    normalized_control_id = int(control_id)
    if active is None:
        toggle_overrides.pop(normalized_control_id, None)
    else:
        toggle_overrides[normalized_control_id] = bool(active)
    canvas.bridge_toggle_active_overrides = toggle_overrides


def _bridge_control_action_kind(control: object) -> str | None:
    """Classify one visible bridge control into a dedicated action-button kind when possible."""

    control_id = int(getattr(control, "control_id", 0) or 0)
    label_text = str(getattr(control, "text", "") or getattr(control, "label", "") or "").strip().lower()
    if "ツモ" in label_text or "tsumo" in label_text:
        return "tsumo"
    if "ロン" in label_text or "ron" in label_text or "和了" in label_text or "agari" in label_text:
        return "ron"
    if "ポン" in label_text or "pon" in label_text:
        return "pon"
    if "チー" in label_text or "chi" in label_text:
        return "chi"
    if "カン" in label_text or "槓" in label_text or "kan" in label_text:
        return "kan"
    if "リーチ" in label_text or "riichi" in label_text or "reach" in label_text:
        return "riichi"
    if "鳴き" in label_text or "naki" in label_text or "call" in label_text:
        return "naki"
    if control_id in BRIDGE_RIICHI_CONTROL_IDS:
        return "riichi"
    if control_id in BRIDGE_NAKI_CONTROL_IDS:
        return "naki"
    if control_id in BRIDGE_CHI_CONTROL_IDS:
        return "chi"
    if control_id in BRIDGE_PON_CONTROL_IDS:
        return "pon"
    if control_id in BRIDGE_KAN_CONTROL_IDS:
        return "kan"
    if control_id in BRIDGE_AGARI_CONTROL_IDS:
        return "ron"
    return None


def _bridge_action_button_label(kind: str, index: int, total: int) -> str:
    """Return one compact label for one dedicated app-side action button."""

    base_label = BRIDGE_ACTION_KIND_LABELS.get(str(kind), str(kind).upper())
    if int(total) <= 1:
        return base_label
    return f"{base_label}{int(index) + 1}"


def _set_inferred_visible_tile_panel_button_open_state(
    button_widget: tkinter.Button | None,
    is_open: bool,
) -> None:
    """Update the external tile-panel button so the user can tell whether the selector is open."""

    if button_widget is None:
        return
    background = "#29415d" if is_open else "#16202c"
    foreground = "#f8fafc" if is_open else "#d7deea"
    button_widget.configure(
        bg=background,
        fg=foreground,
        activebackground=background,
        activeforeground=foreground,
    )


def _get_inferred_visible_tile_selector_image_table(canvas: tkinter.Canvas) -> TileImageTable:
    """Return the cached small tile-image table used by the 37-kind selector popup."""

    cache = dict(getattr(canvas, "inferred_visible_tile_selector_image_tables", {}))
    cache_key = round(float(INFERRED_VISIBLE_TILE_PANEL_SELECTOR_TILE_SCALE), 3)
    image_table = cache.get(cache_key)
    if image_table is None:
        master = canvas.winfo_toplevel() if callable(getattr(canvas, "winfo_toplevel", None)) else canvas
        image_table = initialize_image(master, tile_scale=float(cache_key))
        cache[cache_key] = image_table
        canvas.inferred_visible_tile_selector_image_tables = cache
    return image_table


def _refresh_inferred_visible_tile_selector_window(canvas: tkinter.Canvas) -> None:
    """Refresh selector-button highlight state to match the currently focused tile kind."""

    selected_tile_37 = getattr(canvas, "selected_inferred_visible_tile_37", None)
    buttons_by_tile37 = dict(getattr(canvas, "inferred_visible_tile_selector_buttons_by_tile37", {}))
    for tile_37, button_widget in buttons_by_tile37.items():
        if not button_widget.winfo_exists():
            continue
        is_selected = int(tile_37) == int(selected_tile_37) if selected_tile_37 is not None else False
        button_widget.configure(
            relief=tkinter.SUNKEN if is_selected else tkinter.FLAT,
            bd=2 if is_selected else 1,
            bg="#29415d" if is_selected else "#0f1722",
            activebackground="#29415d" if is_selected else "#1a2635",
        )


def _position_inferred_visible_tile_selector_window(canvas: tkinter.Canvas) -> None:
    """Keep the selector popup near the current self-hand strip when the window resizes."""

    selector_window = getattr(canvas, "inferred_visible_tile_selector_window", None)
    if selector_window is None or not selector_window.winfo_exists():
        return
    hand_rect = getattr(canvas, "current_hand_rect", None)
    if not isinstance(hand_rect, tuple) or len(hand_rect) != 4:
        return
    selector_window.update_idletasks()
    left, top, _right, _bottom = (float(value) for value in hand_rect)
    root = canvas.winfo_toplevel()
    place_x = int(root.winfo_rootx() + max(8.0, left - selector_window.winfo_reqwidth() - INFERRED_VISIBLE_TILE_PANEL_SELECTOR_WINDOW_GAP))
    place_y = int(root.winfo_rooty() + max(8.0, top - selector_window.winfo_reqheight() - INFERRED_VISIBLE_TILE_PANEL_SELECTOR_WINDOW_GAP))
    selector_window.geometry(f"+{place_x}+{place_y}")


def _close_inferred_visible_tile_selector_window(canvas: tkinter.Canvas) -> None:
    """Close the external 37-kind selector popup if it is currently open."""

    existing_window = getattr(canvas, "inferred_visible_tile_selector_window", None)
    button_widget = getattr(canvas, "inferred_visible_tile_panel_button", None)
    if existing_window is None or not existing_window.winfo_exists():
        canvas.inferred_visible_tile_selector_window = None
        canvas.inferred_visible_tile_selector_buttons_by_tile37 = {}
        _set_inferred_visible_tile_panel_button_open_state(button_widget, False)
        return
    existing_window.destroy()
    canvas.inferred_visible_tile_selector_window = None
    canvas.inferred_visible_tile_selector_buttons_by_tile37 = {}
    _set_inferred_visible_tile_panel_button_open_state(button_widget, False)


def _widget_is_same_or_descendant(widget: object, ancestor: object) -> bool:
    """Return whether one Tk widget is the same as, or a descendant of, another widget."""

    current_widget = widget
    while current_widget is not None:
        if current_widget is ancestor:
            return True
        current_widget = getattr(current_widget, "master", None)
    return False


def _close_inferred_visible_tile_selector_window_for_external_click(
    canvas: tkinter.Canvas,
    widget: object | None,
) -> None:
    """Close the selector popup when the user clicks outside both the popup and its launcher."""

    selector_window = getattr(canvas, "inferred_visible_tile_selector_window", None)
    if selector_window is None or not selector_window.winfo_exists():
        return
    button_widget = getattr(canvas, "inferred_visible_tile_panel_button", None)
    if widget is not None and (
        _widget_is_same_or_descendant(widget, selector_window)
        or _widget_is_same_or_descendant(widget, button_widget)
    ):
        return
    _close_inferred_visible_tile_selector_window(canvas)


def _toggle_inferred_visible_tile_selector_window(
    root: tkinter.Tk,
    canvas: tkinter.Canvas,
) -> None:
    """Toggle the external 37-kind tile selector used to open inferred-visible popups."""

    if not _inferred_visible_runtime_enabled(canvas):
        return

    existing_window = getattr(canvas, "inferred_visible_tile_selector_window", None)
    if existing_window is not None and existing_window.winfo_exists():
        _close_inferred_visible_tile_selector_window(canvas)
        return

    selector_window = tkinter.Toplevel(root)
    selector_window.title("推測見え牌パネル")
    selector_window.configure(bg="#0f1722")
    selector_window.resizable(False, False)
    selector_window.transient(root)

    def _handle_close() -> None:
        _close_inferred_visible_tile_selector_window(canvas)

    selector_window.protocol("WM_DELETE_WINDOW", _handle_close)
    body = tkinter.Frame(selector_window, bg="#0f1722", padx=6, pady=6)
    body.pack(fill=tkinter.BOTH, expand=True)
    tile_image_table = _get_inferred_visible_tile_selector_image_table(canvas)
    buttons_by_tile37: dict[int, tkinter.Button] = {}

    def _handle_tile_select(tile_37: int) -> None:
        if not _select_inferred_visible_tile(canvas, tile_37):
            return
        _refresh_inferred_visible_tile_selector_window(canvas)
        redraw_action = getattr(canvas, "redraw_action", None)
        if callable(redraw_action):
            redraw_action()

    for tile_37 in range(1, N_TILES + 1):
        button_widget_for_tile = tkinter.Button(
            body,
            image=tile_image_table[Player.JICHA][DrawType.TEDASHI][tile_37],
            command=lambda selected_tile_37=tile_37: _handle_tile_select(int(selected_tile_37)),
            relief=tkinter.FLAT,
            bd=1,
            bg="#0f1722",
            activebackground="#1a2635",
            highlightthickness=0,
            padx=1,
            pady=1,
        )
        row_index = (tile_37 - 1) // INFERRED_VISIBLE_TILE_PANEL_SELECTOR_COLUMNS
        column_index = (tile_37 - 1) % INFERRED_VISIBLE_TILE_PANEL_SELECTOR_COLUMNS
        button_widget_for_tile.grid(row=row_index, column=column_index, padx=1, pady=1)
        buttons_by_tile37[int(tile_37)] = button_widget_for_tile

    canvas.inferred_visible_tile_selector_window = selector_window
    canvas.inferred_visible_tile_selector_buttons_by_tile37 = buttons_by_tile37
    _refresh_inferred_visible_tile_selector_window(canvas)
    _set_inferred_visible_tile_panel_button_open_state(
        getattr(canvas, "inferred_visible_tile_panel_button", None),
        True,
    )
    _position_inferred_visible_tile_selector_window(canvas)


def _place_inferred_visible_tile_panel_button(canvas: tkinter.Canvas) -> None:
    """Place the external `牌パネル` button slightly above the self hand."""

    button_widget = getattr(canvas, "inferred_visible_tile_panel_button", None)
    if button_widget is None or not button_widget.winfo_exists():
        return
    if not _inferred_visible_runtime_enabled(canvas):
        button_widget.place_forget()
        return
    hand_rect = getattr(canvas, "current_hand_rect", None)
    if not isinstance(hand_rect, tuple) or len(hand_rect) != 4:
        button_widget.place_forget()
        return
    left, top, _right, _bottom = (float(value) for value in hand_rect)
    place_x = max(button_widget.winfo_reqwidth() + 6, left - 6)
    place_y = max(
        button_widget.winfo_reqheight() + 4,
        top - INFERRED_VISIBLE_TILE_PANEL_BUTTON_MARGIN_ABOVE_HAND,
    )
    button_widget.place(
        x=place_x,
        y=place_y,
        anchor=tkinter.SE,
    )
    _refresh_inferred_visible_tile_selector_window(canvas)
    _set_inferred_visible_tile_panel_button_open_state(
        button_widget,
        bool(
            getattr(canvas, "inferred_visible_tile_selector_window", None) is not None
            and getattr(canvas, "inferred_visible_tile_selector_window").winfo_exists()
        ),
    )
    _position_inferred_visible_tile_selector_window(canvas)


def _place_bridge_toggle_controls_frame(canvas: tkinter.Canvas) -> None:
    """Place the persistent bridge toggle-button row near the lower-right edge of the window."""

    toggle_controls_frame = getattr(canvas, "bridge_toggle_controls_frame", None)
    if toggle_controls_frame is None or not toggle_controls_frame.winfo_exists():
        return
    canvas_width = max(canvas.winfo_width(), WINDOW_MIN_WIDTH)
    canvas_height = max(canvas.winfo_height(), WINDOW_MIN_HEIGHT)
    toggle_controls_frame.place(
        x=canvas_width - BRIDGE_TOGGLE_CONTROLS_MARGIN_RIGHT,
        y=canvas_height - BRIDGE_TOGGLE_CONTROLS_MARGIN_BOTTOM,
        anchor=tkinter.SE,
    )


def _place_bridge_action_controls_frame(canvas: tkinter.Canvas) -> None:
    """Place the transient action-button row slightly above the current self-hand strip."""

    action_controls_frame = getattr(canvas, "bridge_action_controls_frame", None)
    if action_controls_frame is None or not action_controls_frame.winfo_exists():
        return
    if not any(
        bool(str(getattr(child, "winfo_manager", lambda: "")() or "").strip())
        for child in action_controls_frame.winfo_children()
    ):
        action_controls_frame.place_forget()
        return
    hand_rect = getattr(canvas, "current_hand_rect", None)
    if (
        not isinstance(hand_rect, tuple)
        or len(hand_rect) != 4
    ):
        action_controls_frame.place_forget()
        return
    left, top, right, _bottom = (float(value) for value in hand_rect)
    canvas_width = max(canvas.winfo_width(), WINDOW_MIN_WIDTH)
    action_frame_half_width = max(action_controls_frame.winfo_reqwidth() / 2.0, 1.0)
    place_x = min(
        max((left + right) / 2.0, BRIDGE_ACTION_CONTROLS_SIDE_MARGIN + action_frame_half_width),
        canvas_width - BRIDGE_ACTION_CONTROLS_SIDE_MARGIN - action_frame_half_width,
    )
    place_y = max(
        action_controls_frame.winfo_reqheight() + 4,
        top - BRIDGE_ACTION_CONTROLS_MARGIN_ABOVE_HAND,
    )
    action_controls_frame.place(
        x=place_x,
        y=place_y,
        anchor=tkinter.S,
    )


def _build_bridge_action_control_specs(
    visible_controls: Sequence[object],
) -> tuple[BridgeActionControlSpec, ...]:
    """Build dedicated action-button specs from the currently visible bridge controls."""

    grouped_controls: dict[str, list[int]] = {
        kind: []
        for kind in BRIDGE_ACTION_KIND_ORDER
    }
    for control in visible_controls:
        kind = _bridge_control_action_kind(control)
        if kind is None:
            continue
        grouped_controls.setdefault(kind, []).append(int(getattr(control, "control_id", 0) or 0))
    specs: list[BridgeActionControlSpec] = []
    for kind in BRIDGE_ACTION_KIND_ORDER:
        control_ids = grouped_controls.get(kind, [])
        for index, control_id in enumerate(control_ids):
            specs.append(
                BridgeActionControlSpec(
                    control_id=control_id,
                    kind=kind,
                    label=_bridge_action_button_label(kind, index, len(control_ids)),
                )
            )
    return tuple(specs)


def _refresh_bridge_widgets(canvas: tkinter.Canvas) -> None:
    """Refresh the external bridge status label and visible-control buttons."""

    status_label = getattr(canvas, "bridge_status_label_widget", None)
    if status_label is not None:
        text, background, foreground = _bridge_status_presentation(canvas)
        status_label.configure(
            text=text,
            bg=background,
            fg=foreground,
        )
    refresh_button = getattr(canvas, "bridge_refresh_button", None)
    if refresh_button is not None:
        refresh_button.configure(
            state=(
                tkinter.NORMAL
                if callable(getattr(canvas, "bridge_ui_snapshot_action", None))
                else tkinter.DISABLED
            )
        )
    map_button = getattr(canvas, "bridge_map_button", None)
    if map_button is not None:
        map_button.configure(
            state=(
                tkinter.NORMAL
                if callable(getattr(canvas, "bridge_table_snapshot_action", None))
                else tkinter.DISABLED
            )
        )

    controls_frame = getattr(canvas, "bridge_controls_frame", None)
    empty_label = getattr(canvas, "bridge_controls_empty_label", None)
    if controls_frame is None:
        return

    status = _bridge_status_snapshot(canvas)
    toggle_controls_frame = getattr(canvas, "bridge_toggle_controls_frame", None)
    action_controls_frame = getattr(canvas, "bridge_action_controls_frame", None)
    bridge_is_actionable = bool(
        status is not None
        and getattr(status, "listening", False)
        and getattr(status, "connected", False)
        and getattr(status, "extension_ready", False)
        and _bridge_ui_snapshot_result(status) is not None
    )
    toggle_controls = (
        tuple(getattr(status, "toggle_controls", ()))
        if bridge_is_actionable and status is not None
        else ()
    )
    visible_controls = (
        tuple(getattr(status, "visible_controls", ()))
        if bridge_is_actionable and status is not None
        else ()
    )
    action_control_specs = _build_bridge_action_control_specs(visible_controls)
    action_control_ids = {spec.control_id for spec in action_control_specs}
    click_action_available = callable(getattr(canvas, "bridge_click_control_action", None))
    _place_bridge_toggle_controls_frame(canvas)
    if toggle_controls_frame is not None:
        toggle_overrides = dict(getattr(canvas, "bridge_toggle_active_overrides", {}))
        toggle_buttons = dict(getattr(canvas, "bridge_toggle_buttons_by_id", {}))
        current_toggle_ids = set()
        for toggle_control in toggle_controls:
            control_id = int(getattr(toggle_control, "control_id", 0) or 0)
            current_toggle_ids.add(control_id)
            button = toggle_buttons.get(control_id)
            if button is None:
                button = tkinter.Button(
                    toggle_controls_frame,
                    relief=tkinter.FLAT,
                    bd=1,
                    bg="#16202c",
                    fg="#d7deea",
                    activebackground="#29415d",
                    activeforeground="#f8fafc",
                    disabledforeground="#6b7280",
                    font=("Yu Gothic UI", 7, "bold"),
                    padx=6,
                    pady=1,
                    highlightthickness=0,
                    command=lambda selected_control_id=control_id: _handle_bridge_control_button_click(
                        canvas,
                        selected_control_id,
                    ),
                )
                toggle_buttons[control_id] = button
            is_available = bool(getattr(toggle_control, "available", False))
            is_active, clear_override = _resolve_bridge_toggle_active_state(
                bool(getattr(toggle_control, "active", False)),
                toggle_overrides.get(control_id),
            )
            if clear_override:
                toggle_overrides.pop(control_id, None)
            active_fill = "#0f5132" if is_active else "#4b1f2d"
            active_hover_fill = "#12603a" if is_active else "#5b2735"
            button.configure(
                text=_bridge_toggle_button_label(toggle_control, active=is_active),
                state=tkinter.NORMAL if (click_action_available and is_available) else tkinter.DISABLED,
                bg=active_fill,
                activebackground=active_hover_fill,
            )
            button.pack(side=tkinter.LEFT, padx=(0, 4))
        for control_id, button in toggle_buttons.items():
            if control_id in current_toggle_ids:
                continue
            button.pack_forget()
            toggle_overrides.pop(control_id, None)
        canvas.bridge_toggle_active_overrides = toggle_overrides
        canvas.bridge_toggle_buttons_by_id = toggle_buttons

    if action_controls_frame is not None:
        action_buttons = dict(getattr(canvas, "bridge_action_buttons_by_key", {}))
        current_action_keys: set[tuple[str, int]] = set()
        for action_spec in action_control_specs:
            button_key = (str(action_spec.kind), int(action_spec.control_id))
            current_action_keys.add(button_key)
            button = action_buttons.get(button_key)
            if button is None:
                button = tkinter.Button(
                    action_controls_frame,
                    relief=tkinter.FLAT,
                    bd=1,
                    bg="#284a31",
                    fg="#f8fafc",
                    activebackground="#356340",
                    activeforeground="#f8fafc",
                    disabledforeground="#6b7280",
                    font=("Yu Gothic UI", 9, "bold"),
                    padx=12,
                    pady=4,
                    highlightthickness=0,
                    command=lambda selected_control_id=action_spec.control_id: _handle_bridge_control_button_click(
                        canvas,
                        selected_control_id,
                    ),
                )
                action_buttons[button_key] = button
            button.configure(
                text=str(action_spec.label),
                state=tkinter.NORMAL if click_action_available else tkinter.DISABLED,
            )
            button.pack(side=tkinter.LEFT, padx=(0, 6))
        for button_key, button in action_buttons.items():
            if button_key in current_action_keys:
                continue
            button.pack_forget()
        canvas.bridge_action_buttons_by_key = action_buttons
        if action_control_specs:
            _place_bridge_action_controls_frame(canvas)
        else:
            action_controls_frame.place_forget()

    control_buttons = dict(getattr(canvas, "bridge_control_buttons_by_id", {}))
    visible_control_ids = set()

    for control in visible_controls:
        control_id = int(control.control_id)
        if control_id in action_control_ids:
            continue
        visible_control_ids.add(control_id)
        button = control_buttons.get(control_id)
        if button is None:
            button = tkinter.Button(
                controls_frame,
                relief=tkinter.FLAT,
                bd=1,
                bg="#16202c",
                fg="#d7deea",
                activebackground="#29415d",
                activeforeground="#f8fafc",
                disabledforeground="#6b7280",
                font=("Yu Gothic UI", 7, "bold"),
                padx=6,
                pady=1,
                highlightthickness=0,
                command=lambda selected_control_id=control_id: _handle_bridge_control_button_click(
                    canvas,
                    selected_control_id,
                ),
            )
            control_buttons[control_id] = button
        button.configure(
            text=_bridge_control_button_label(control.control_id, getattr(control, "label", "")),
            state=tkinter.NORMAL if click_action_available else tkinter.DISABLED,
        )
        button.pack(side=tkinter.LEFT, padx=(0, 4))

    for control_id, button in control_buttons.items():
        if control_id in visible_control_ids:
            continue
        button.pack_forget()

    canvas.bridge_control_buttons_by_id = control_buttons
    if empty_label is not None:
        if visible_control_ids or action_control_specs:
            empty_label.pack_forget()
        else:
            empty_label.configure(text="No controls")
            empty_label.pack(side=tkinter.LEFT)


def _handle_bridge_control_button_click(canvas: tkinter.Canvas, control_id: int) -> None:
    """Dispatch one visible Tenhou control button click in the background."""

    _dispatch_bridge_control_click(
        canvas,
        int(control_id),
    )


def _request_bridge_ui_snapshot(canvas: tkinter.Canvas, *, force: bool = False) -> bool:
    """Kick one background `ui_snapshot` request when the poll interval allows it."""

    action = getattr(canvas, "bridge_ui_snapshot_action", None)
    if not callable(action):
        return False
    if getattr(canvas, "bridge_snapshot_in_flight", False):
        if force:
            canvas.bridge_snapshot_pending_force = True
            return True
        return False
    now = time.monotonic()
    last_started = float(getattr(canvas, "bridge_last_snapshot_started_monotonic_s", 0.0) or 0.0)
    if not force and last_started > 0.0 and (now - last_started) < BRIDGE_SNAPSHOT_POLL_S:
        return False
    canvas.bridge_snapshot_pending_force = False
    canvas.bridge_snapshot_in_flight = True
    canvas.bridge_last_snapshot_started_monotonic_s = now
    return _queue_bridge_background_action(
        canvas,
        kind="snapshot",
        action=action,
    )


def _request_bridge_table_snapshot(canvas: tkinter.Canvas, *, retry: bool = False) -> bool:
    """Kick one background browser-table import from the bridge widget."""

    action = getattr(canvas, "bridge_table_snapshot_action", None)
    if not callable(action):
        _set_bridge_feedback(canvas, "Bridge map unavailable", is_error=True)
        _refresh_bridge_widgets(canvas)
        return False
    if bool(getattr(canvas, "bridge_table_snapshot_in_flight", False)):
        if not retry:
            _set_bridge_feedback(canvas, "Bridge map already running", is_error=False)
            _refresh_bridge_widgets(canvas)
        return False
    if not retry:
        _cancel_bridge_table_snapshot_retry(canvas)
        canvas.bridge_table_snapshot_retry_count = 0
    _set_bridge_feedback(canvas, "Mapping browser table...", is_error=False)
    _refresh_bridge_widgets(canvas)
    canvas.bridge_table_snapshot_in_flight = True
    queued = _queue_bridge_background_action(
        canvas,
        kind="map",
        action=action,
    )
    if not queued:
        canvas.bridge_table_snapshot_in_flight = False
    return queued


def _flush_pending_bridge_ui_snapshot_request(canvas: tkinter.Canvas) -> bool:
    """Start one deferred forced snapshot after the current in-flight snapshot finishes."""

    if getattr(canvas, "bridge_snapshot_in_flight", False):
        return False
    if not bool(getattr(canvas, "bridge_snapshot_pending_force", False)):
        return False
    canvas.bridge_last_snapshot_started_monotonic_s = 0.0
    return _request_bridge_ui_snapshot(canvas, force=True)


def _schedule_bridge_followup_snapshots(canvas: tkinter.Canvas) -> None:
    """Queue a short burst of forced snapshots after one control click changes Tenhou UI state."""

    existing_jobs = list(getattr(canvas, "bridge_followup_snapshot_jobs", ()))
    for existing_job in existing_jobs:
        try:
            canvas.after_cancel(existing_job)
        except tkinter.TclError:
            continue
    scheduled_jobs: list[str] = []

    def _run_followup_snapshot() -> None:
        canvas.bridge_last_snapshot_started_monotonic_s = 0.0
        _request_bridge_ui_snapshot(canvas, force=True)

    for delay_ms in BRIDGE_CONTROL_FOLLOWUP_SNAPSHOT_DELAYS_MS:
        try:
            job_id = canvas.after(
                int(delay_ms),
                _run_followup_snapshot,
            )
        except tkinter.TclError:
            break
        scheduled_jobs.append(job_id)
    canvas.bridge_followup_snapshot_jobs = scheduled_jobs


def _cancel_bridge_followup_snapshots(canvas: tkinter.Canvas) -> None:
    """Cancel delayed bridge snapshots that were scheduled before a bridge drop."""

    existing_jobs = list(getattr(canvas, "bridge_followup_snapshot_jobs", ()))
    for existing_job in existing_jobs:
        try:
            canvas.after_cancel(existing_job)
        except tkinter.TclError:
            continue
    canvas.bridge_followup_snapshot_jobs = []


def _cancel_bridge_table_snapshot_retry(canvas: tkinter.Canvas) -> None:
    """Cancel one delayed browser table-map retry, if it is still pending."""

    existing_job = getattr(canvas, "bridge_table_snapshot_retry_job", None)
    if existing_job is not None:
        try:
            canvas.after_cancel(existing_job)
        except (AttributeError, tkinter.TclError):
            pass
    canvas.bridge_table_snapshot_retry_job = None


def _is_bridge_table_state_not_ready_error(error_text: object) -> bool:
    """Return True for the transient browser-side table-state bootstrap error."""

    normalized_error = str(error_text or "").strip().upper().replace(" ", "_")
    return "TABLE_STATE_NOT_READY" in normalized_error


def _schedule_bridge_table_snapshot_retry(
    canvas: tkinter.Canvas,
    *,
    error_text: object,
) -> bool:
    """Retry browser table mapping when Tenhou globals have not reappeared yet."""

    if not _is_bridge_table_state_not_ready_error(error_text):
        return False
    try:
        retry_count = int(getattr(canvas, "bridge_table_snapshot_retry_count", 0) or 0)
    except (TypeError, ValueError):
        retry_count = 0
    if retry_count >= BRIDGE_TABLE_SNAPSHOT_READY_RETRY_LIMIT:
        _set_bridge_feedback(
            canvas,
            "Bridge map table state still not ready",
            is_error=True,
        )
        canvas.bridge_table_snapshot_retry_count = 0
        canvas.bridge_table_snapshot_retry_job = None
        return True

    next_retry_count = retry_count + 1
    _cancel_bridge_table_snapshot_retry(canvas)
    canvas.bridge_table_snapshot_retry_count = next_retry_count
    _set_bridge_feedback(
        canvas,
        (
            "Bridge map waiting for table state "
            f"({next_retry_count}/{BRIDGE_TABLE_SNAPSHOT_READY_RETRY_LIMIT})"
        ),
        is_error=False,
    )
    try:
        retry_job = canvas.after(
            BRIDGE_TABLE_SNAPSHOT_READY_RETRY_MS,
            lambda: _run_bridge_table_snapshot_retry(canvas),
        )
    except (AttributeError, tkinter.TclError):
        canvas.bridge_table_snapshot_retry_job = None
        return False
    canvas.bridge_table_snapshot_retry_job = retry_job
    return True


def _run_bridge_table_snapshot_retry(canvas: tkinter.Canvas) -> None:
    """Start one delayed browser table-map retry."""

    canvas.bridge_table_snapshot_retry_job = None
    _request_bridge_table_snapshot(canvas, retry=True)


def _drain_bridge_background_result_queue(canvas: tkinter.Canvas) -> bool:
    """Apply finished bridge poll/command results back on the Tk thread."""

    result_queue = getattr(canvas, "bridge_background_result_queue", None)
    if result_queue is None:
        return False
    changed = False
    while True:
        try:
            payload = result_queue.get_nowait()
        except queue.Empty:
            break
        if not isinstance(payload, Mapping):
            continue
        kind = str(payload.get("kind", "") or "")
        payload_meta = payload.get("meta")
        changed = True
        if kind == "snapshot":
            canvas.bridge_snapshot_in_flight = False
        if kind == "map":
            canvas.bridge_table_snapshot_in_flight = False
        if not bool(payload.get("ok", False)):
            if kind == "control" and isinstance(payload_meta, Mapping):
                try:
                    failed_control_id = int(payload_meta.get("control_id", 0) or 0)
                except (TypeError, ValueError):
                    failed_control_id = 0
                if failed_control_id > 0:
                    toggle_overrides = dict(getattr(canvas, "bridge_toggle_active_overrides", {}))
                    if failed_control_id in toggle_overrides:
                        toggle_overrides.pop(failed_control_id, None)
                        canvas.bridge_toggle_active_overrides = toggle_overrides
            _set_bridge_feedback(
                canvas,
                str(payload.get("error", "Bridge action failed") or "Bridge action failed"),
                is_error=True,
            )
            if kind == "snapshot":
                _flush_pending_bridge_ui_snapshot_request(canvas)
            continue
        result_payload = payload.get("result_payload")
        nested_result = (
            result_payload.get("result")
            if isinstance(result_payload, Mapping)
            and isinstance(result_payload.get("result"), Mapping)
            else None
        )
        if kind == "snapshot":
            if isinstance(nested_result, Mapping) and not bool(nested_result.get("ok", False)):
                _set_bridge_feedback(
                    canvas,
                    str(nested_result.get("error", "ui_snapshot failed") or "ui_snapshot failed"),
                    is_error=True,
                )
            _flush_pending_bridge_ui_snapshot_request(canvas)
            continue
        if isinstance(nested_result, Mapping) and bool(nested_result.get("ok", False)):
            if kind == "discard":
                _set_bridge_feedback(canvas, _format_bridge_success_feedback(kind, nested_result), is_error=False)
            elif kind == "control":
                _set_bridge_feedback(canvas, _format_bridge_success_feedback(kind, nested_result), is_error=False)
            elif kind == "map":
                _cancel_bridge_table_snapshot_retry(canvas)
                canvas.bridge_table_snapshot_retry_count = 0
                _set_bridge_feedback(canvas, _format_bridge_success_feedback(kind, nested_result), is_error=False)
            if kind in {"discard", "control"}:
                canvas.bridge_last_snapshot_started_monotonic_s = 0.0
                _request_bridge_ui_snapshot(canvas, force=True)
            if kind == "control":
                _schedule_bridge_followup_snapshots(canvas)
            continue
        if isinstance(nested_result, Mapping):
            if kind == "control" and isinstance(payload_meta, Mapping):
                try:
                    failed_control_id = int(payload_meta.get("control_id", 0) or 0)
                except (TypeError, ValueError):
                    failed_control_id = 0
                if failed_control_id > 0:
                    toggle_overrides = dict(getattr(canvas, "bridge_toggle_active_overrides", {}))
                    if failed_control_id in toggle_overrides:
                        toggle_overrides.pop(failed_control_id, None)
                        canvas.bridge_toggle_active_overrides = toggle_overrides
            if kind == "map" and _schedule_bridge_table_snapshot_retry(
                canvas,
                error_text=nested_result.get("error", ""),
            ):
                _refresh_bridge_widgets(canvas)
                continue
            _set_bridge_feedback(
                canvas,
                str(nested_result.get("error", "Bridge action failed") or "Bridge action failed"),
                is_error=True,
            )
            continue
        _set_bridge_feedback(canvas, "Bridge action finished", is_error=False)
    return changed


def _schedule_bridge_status_tick(canvas: tkinter.Canvas) -> None:
    """Schedule the next bridge status tick when bridge integration is active."""

    if bool(getattr(canvas, "bridge_status_tick_closed", False)):
        return
    winfo_exists = getattr(canvas, "winfo_exists", None)
    if callable(winfo_exists):
        try:
            if not bool(winfo_exists()):
                return
        except tkinter.TclError:
            return
    if not (
        callable(getattr(canvas, "bridge_status_provider", None))
        or callable(getattr(canvas, "bridge_ui_snapshot_action", None))
        or callable(getattr(canvas, "bridge_table_snapshot_action", None))
    ):
        return
    try:
        canvas.bridge_status_tick_job = canvas.after(
            BRIDGE_STATUS_TICK_MS,
            lambda: _bridge_status_tick(canvas),
        )
    except (AttributeError, tkinter.TclError):
        canvas.bridge_status_tick_job = None


def _bridge_status_tick(canvas: tkinter.Canvas) -> None:
    """Keep bridge status/control widgets fresh without blocking redraw."""

    canvas.bridge_status_tick_job = None
    _schedule_bridge_status_tick(canvas)
    try:
        _drain_bridge_background_result_queue(canvas)
        same_jun_changed = (
            _drain_same_jun_match_background_result_queue(canvas)
            if AWASEUCHI_MARKERS_ENABLED
            else False
        )
        bridge_auto_changed = _sync_hand_auto_mode_bridge_readiness(canvas)
        if bridge_auto_changed:
            _refresh_hand_auto_mode_button_widget(canvas)
        _refresh_bridge_widgets(canvas)
        if bridge_auto_changed or same_jun_changed:
            redraw_action = getattr(canvas, "redraw_action", None)
            if callable(redraw_action):
                redraw_action()
        current_bridge_status = _bridge_status_snapshot(canvas)
        if not (
            current_bridge_status is not None
            and current_bridge_status.listening
            and current_bridge_status.connected
            and current_bridge_status.extension_ready
        ):
            canvas.bridge_snapshot_pending_force = False
            _cancel_bridge_followup_snapshots(canvas)
            _cancel_bridge_table_snapshot_retry(canvas)
            canvas.bridge_table_snapshot_retry_count = 0
        if _should_request_bridge_ui_snapshot_on_tick(canvas, current_bridge_status):
            if _request_bridge_ui_snapshot(canvas):
                canvas.bridge_last_requested_source_refresh_token = getattr(
                    canvas,
                    "bridge_snapshot_source_refresh_token",
                    None,
                )
        canvas.last_bridge_status_tick_error_text = None
    except Exception as exc:  # noqa: BLE001 - status tick must keep polling after transient UI/bridge errors.
        error_text = f"{type(exc).__name__}: {exc}"
        if getattr(canvas, "last_bridge_status_tick_error_text", None) != error_text:
            canvas.last_bridge_status_tick_error_text = error_text
            print(f"Bridge status tick failed: {error_text}")


def _hand_auto_discard_worker(
    action: Callable[[int], Mapping[str, object] | None],
    candidate: HandAutoDiscardCandidate,
    result_queue: queue.Queue[dict[str, object]],
    delay_s: float = 0.0,
) -> None:
    """Execute one bridge-backed auto discard in the background and report the result."""

    try:
        if float(delay_s) > 0.0:
            time.sleep(float(delay_s))
        result_payload = action(int(candidate.tile_37))
    except Exception as exc:  # noqa: BLE001 - bridge execution must surface transport failures.
        result_queue.put(
            {
                "attempt_key": candidate.attempt_key,
                "result_payload": {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            }
        )
        return
    result_queue.put(
        {
            "attempt_key": candidate.attempt_key,
            "result_payload": result_payload,
        }
    )


def _start_hand_auto_mode_action(
    canvas: tkinter.Canvas,
    *,
    current_mode: str,
    attempt_key: tuple[object, ...],
    action: Callable[[int], Mapping[str, object] | None] | None,
    tile_37: int = 0,
    tile_text: str = "",
    delay_s: float = 0.0,
    toggle_override_control_id: int | None = None,
) -> bool:
    """Queue one auto-mode bridge action and latch its dedupe key."""

    if not callable(action):
        return False
    auto_mode_state = getattr(canvas, "hand_auto_mode_state", HandAutoModeState())
    if auto_mode_state.last_attempt_key == attempt_key:
        return False
    result_queue = getattr(canvas, "hand_auto_mode_result_queue", None)
    if result_queue is None:
        result_queue = queue.Queue()
        canvas.hand_auto_mode_result_queue = result_queue
    canvas.hand_auto_mode_state = HandAutoModeState(
        enabled=True,
        mode=current_mode,
        in_flight=True,
        last_attempt_key=attempt_key,
    )
    if toggle_override_control_id is not None:
        _set_bridge_toggle_override(canvas, int(toggle_override_control_id), True)
    _start_tracked_background_thread(
        label="auto discard",
        name="hand-auto-discard",
        target=_hand_auto_discard_worker,
        args=(
            action,
            HandAutoDiscardCandidate(
                attempt_key=attempt_key,
                tile_37=int(tile_37),
                tile_text=str(tile_text or ""),
            ),
            result_queue,
            delay_s,
        ),
    )
    return True


def _maybe_start_hand_auto_discard(
    canvas: tkinter.Canvas,
    request_hand_tiles: Sequence[int],
    hand_recommendation_panel: HandRecommendationPanelData,
    display_context: PystyleDisplayContext | None,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    self_melds: Sequence[Meld] = (),
    *,
    recommendation_timeout_elapsed: bool = False,
    recommendation_error_fallback_active: bool = False,
) -> None:
    """Launch one bridge-backed discard for the active auto mode.

    Recommendation mode uses the current pystyle top discard when available. Timeout/error
    recovery temporarily falls back to honor-first and otherwise betaori while immediately
    restarting the recommendation request for the same hand.
    """

    auto_mode_state = getattr(canvas, "hand_auto_mode_state", HandAutoModeState())
    if not auto_mode_state.enabled or auto_mode_state.in_flight:
        return
    current_mode = str(getattr(auto_mode_state, "mode", HAND_AUTO_MODE_KIND_RECOMMENDATION))
    bridge_status = _bridge_status_snapshot(canvas)
    if not _is_bridge_ready_for_hand_auto(bridge_status):
        return
    bridge_click_control_action = getattr(canvas, "bridge_click_control_action", None)
    if (
        current_mode == HAND_AUTO_MODE_KIND_RECOMMENDATION
        and not _has_open_self_meld(self_melds)
        and display_context is not None
        and display_context.request_fallback_tile_37 is None
    ):
        riichi_control_id = _select_visible_bridge_control_id(
            bridge_status,
            BRIDGE_RIICHI_CONTROL_IDS,
            text_hints=("リーチ", "riichi", "reach"),
        )
        if riichi_control_id is not None:
            attempt_key = (
                "auto_riichi",
                int(riichi_control_id),
                *_hand_recommendation_request_display_key(request_hand_tiles, display_context),
            )
            if auto_mode_state.last_attempt_key == attempt_key:
                return
            _start_hand_auto_mode_action(
                canvas,
                current_mode=current_mode,
                attempt_key=attempt_key,
                action=(
                    (lambda _tile_37, control_id=int(riichi_control_id): bridge_click_control_action(control_id))
                    if callable(bridge_click_control_action)
                    else None
                ),
                tile_text="リーチ",
            )
            return
    if current_mode == HAND_AUTO_MODE_KIND_RECOMMENDATION:
        required_toggle_specs = (
            (BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID, "auto_auto_agari_on", "自動和了"),
            (BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID, "auto_naki_disabled_on", "鳴き無し"),
        )
        for control_id, attempt_prefix, label_text in required_toggle_specs:
            toggle_control = _lookup_bridge_toggle_control(bridge_status, control_id)
            toggle_overrides = dict(getattr(canvas, "bridge_toggle_active_overrides", {}))
            toggle_is_active, _clear_override = _resolve_bridge_toggle_active_state(
                bool(getattr(toggle_control, "active", False)) if toggle_control is not None else False,
                toggle_overrides.get(int(control_id)),
            )
            if (
                toggle_control is None
                or not bool(getattr(toggle_control, "available", False))
                or toggle_is_active
            ):
                continue
            attempt_key = (
                str(attempt_prefix),
                int(control_id),
                *_hand_recommendation_request_display_key(request_hand_tiles, display_context),
            )
            if auto_mode_state.last_attempt_key == attempt_key:
                return
            _start_hand_auto_mode_action(
                canvas,
                current_mode=current_mode,
                attempt_key=attempt_key,
                action=(
                    (lambda _tile_37, toggle_control_id=int(control_id): bridge_click_control_action(toggle_control_id))
                    if callable(bridge_click_control_action)
                    else None
                ),
                tile_text=str(label_text),
                toggle_override_control_id=int(control_id),
            )
            return
    if current_mode == HAND_AUTO_MODE_KIND_BETAORI:
        candidate = _select_hand_betaori_candidate(
            request_hand_tiles,
            hand_danger_percentages,
            display_context,
        )
    elif current_mode == HAND_AUTO_MODE_KIND_RECOMMENDATION:
        if recommendation_timeout_elapsed or recommendation_error_fallback_active:
            candidate = _select_hand_pystyle_honor_fallback_candidate(
                request_hand_tiles,
                hand_danger_percentages,
                display_context,
            )
        else:
            candidate = _select_hand_auto_discard_candidate(
                request_hand_tiles,
                hand_recommendation_panel,
                display_context,
            )
    else:
        candidate = _select_hand_auto_discard_candidate(
            request_hand_tiles,
            hand_recommendation_panel,
            display_context,
        )
    if candidate is None:
        return
    action = getattr(canvas, "hand_auto_discard_action", None)
    bridge_discard_by_index_action = getattr(canvas, "hand_bridge_discard_by_index_action", None)
    allow_late_riichi_guard = (
        current_mode == HAND_AUTO_MODE_KIND_RECOMMENDATION
        and not _has_open_self_meld(self_melds)
        and display_context is not None
        and display_context.request_fallback_tile_37 is None
    )
    if current_mode == HAND_AUTO_MODE_KIND_BETAORI and callable(bridge_discard_by_index_action):
        resolved_hand_index = (
            int(candidate.hand_index)
            if candidate.hand_index is not None
            else _resolve_request_hand_index_by_tile37(
                request_hand_tiles,
                candidate.tile_37,
            )
        )
        if resolved_hand_index is not None:
            action = lambda _tile_37, hand_index=resolved_hand_index: bridge_discard_by_index_action(
                hand_index
            )
    elif not callable(action) and callable(bridge_discard_by_index_action):
        resolved_hand_index = (
            int(candidate.hand_index)
            if candidate.hand_index is not None
            else _resolve_request_hand_index_by_tile37(
                request_hand_tiles,
                candidate.tile_37,
            )
        )
        if resolved_hand_index is not None:
            action = lambda _tile_37, hand_index=resolved_hand_index: bridge_discard_by_index_action(
                hand_index
            )
    if not callable(action):
        return
    if current_mode == HAND_AUTO_MODE_KIND_RECOMMENDATION:
        action = _build_pystyle_auto_discard_action_with_riichi_guard(
            canvas,
            action,
            allow_riichi=allow_late_riichi_guard,
        )
    recommendation_candidate_active = (
        current_mode == HAND_AUTO_MODE_KIND_RECOMMENDATION
        and str(candidate.attempt_key[0] if candidate.attempt_key else "") in {"auto_discard", "auto_discard_relaxed"}
    )
    delay_s = _resolve_hand_auto_discard_delay_s(
        current_mode,
        has_usable_pystyle_response=recommendation_candidate_active,
        recommendation_timeout_elapsed=recommendation_timeout_elapsed,
    )
    _start_hand_auto_mode_action(
        canvas,
        current_mode=current_mode,
        attempt_key=candidate.attempt_key,
        action=action,
        tile_37=int(candidate.tile_37),
        tile_text=str(candidate.tile_text or ""),
        delay_s=delay_s,
    )


def _ensure_detail_memo_widgets(canvas: tkinter.Canvas) -> None:
    """Create the shared detail memo editor widgets on demand."""

    if getattr(canvas, "detail_memo_frame", None) is not None:
        return

    frame = tkinter.Frame(canvas, bg="#121923", highlightthickness=0, bd=0)
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_rowconfigure(2, weight=1)

    title_label = tkinter.Label(
        frame,
        bg="#121923",
        fg="#d7deea",
        font=DETAIL_EDITOR_TITLE_FONT,
        anchor=tkinter.W,
    )
    title_label.grid(row=0, column=0, columnspan=2, sticky="ew")

    subtitle_label = tkinter.Label(
        frame,
        bg="#121923",
        fg="#9fb0c6",
        font=DETAIL_EDITOR_SUBTITLE_FONT,
        anchor=tkinter.W,
    )
    subtitle_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 6))

    text_widget = tkinter.Text(
        frame,
        wrap=tkinter.WORD,
        undo=True,
        relief=tkinter.FLAT,
        bg="#0f1722",
        fg="#f2f4f8",
        insertbackground="#f8fafc",
        font=DETAIL_EDITOR_TEXT_FONT,
        padx=8,
        pady=8,
    )
    text_widget.grid(row=2, column=0, sticky="nsew")

    scrollbar = tkinter.Scrollbar(frame, orient=tkinter.VERTICAL, command=text_widget.yview)
    scrollbar.grid(row=2, column=1, sticky="ns")
    text_widget.configure(yscrollcommand=scrollbar.set)

    action_row = tkinter.Frame(frame, bg="#121923")
    action_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    action_row.grid_columnconfigure(1, weight=1)

    save_button = tkinter.Button(
        action_row,
        text="Save",
        command=lambda: _save_detail_memo_in_background(canvas),
        relief=tkinter.FLAT,
        bd=1,
        bg="#1c2735",
        fg="#d7deea",
        activebackground="#29415d",
        activeforeground="#f8fafc",
        font=("Yu Gothic UI", 8, "bold"),
        padx=10,
        pady=2,
    )
    save_button.grid(row=0, column=0, sticky="w")

    status_label = tkinter.Label(
        action_row,
        bg="#121923",
        fg="#9fb0c6",
        font=DETAIL_EDITOR_STATUS_FONT,
        anchor=tkinter.W,
    )
    status_label.grid(row=0, column=1, sticky="ew", padx=(10, 0))

    def _mark_editing(_event: tkinter.Event) -> None:
        if str(text_widget.cget("state")) != tkinter.DISABLED:
            status_label.configure(text="Editing...", fg="#facc15")

    text_widget.bind("<KeyRelease>", _mark_editing)
    # メモ欄フォーカス中は Ctrl+S で明示保存できるようにする。
    text_widget.bind(
        "<Control-s>",
        lambda event: _handle_detail_memo_save_shortcut(canvas, event),
    )
    text_widget.bind(
        "<Control-S>",
        lambda event: _handle_detail_memo_save_shortcut(canvas, event),
    )

    canvas.detail_memo_frame = frame
    canvas.detail_memo_title_label = title_label
    canvas.detail_memo_subtitle_label = subtitle_label
    canvas.detail_memo_text_widget = text_widget
    canvas.detail_memo_save_button = save_button
    canvas.detail_memo_status_label = status_label
    canvas.detail_memo_player_name = ""
    canvas.detail_memo_loaded_text = ""
    canvas.detail_memo_active_key = None


def _open_detail_memo_editor(canvas: tkinter.Canvas, seat: int) -> None:
    """Load one player's memo into the shared detail editor."""

    _ensure_detail_memo_widgets(canvas)
    player_names_by_seat = getattr(canvas, "current_player_names_by_seat", {})
    player_name = str(player_names_by_seat.get(seat, "")).strip()
    active_key = (seat, player_name)
    if getattr(canvas, "detail_memo_active_key", None) == active_key:
        return

    title_label = canvas.detail_memo_title_label
    subtitle_label = canvas.detail_memo_subtitle_label
    text_widget = canvas.detail_memo_text_widget
    save_button = canvas.detail_memo_save_button
    status_label = canvas.detail_memo_status_label

    title_label.configure(text=f"{PLAYER_PANEL_TITLE_BY_SEAT.get(seat, 'PLAYER')} Memo")
    subtitle_label.configure(text=player_name if player_name else "Player name unavailable")
    text_widget.configure(state=tkinter.NORMAL)
    text_widget.delete("1.0", tkinter.END)

    if not player_name:
        text_widget.insert("1.0", "Player name is not available yet.")
        text_widget.configure(state=tkinter.DISABLED)
        save_button.configure(state=tkinter.DISABLED)
        status_label.configure(text="Unavailable", fg="#fca5a5")
        canvas.detail_memo_player_name = ""
        canvas.detail_memo_loaded_text = ""
        canvas.detail_memo_active_key = active_key
        return

    load_error_text: str | None = None
    try:
        profile = load_player_profile(player_name)
    except Exception as exc:  # noqa: BLE001 - keep the editor usable even if DB read fails once.
        profile = {
            "player_name": player_name,
            "user_memo": "",
            "analysis_memo": "",
        }
        load_error_text = str(exc)
    user_memo = profile.get("user_memo", "")
    memo_presence_cache = dict(getattr(canvas, "player_memo_presence_cache", {}))
    memo_presence_cache[player_name] = bool(str(user_memo).strip())
    canvas.player_memo_presence_cache = memo_presence_cache
    text_widget.insert("1.0", user_memo)
    text_widget.configure(state=tkinter.NORMAL)
    save_button.configure(state=tkinter.NORMAL)
    if load_error_text:
        status_label.configure(text=f"Load failed: {load_error_text}", fg="#fca5a5")
    else:
        status_label.configure(text="Loaded", fg="#9fb0c6")
    canvas.detail_memo_player_name = player_name
    canvas.detail_memo_loaded_text = user_memo
    canvas.detail_memo_active_key = active_key


def _update_detail_overlay(
    canvas: tkinter.Canvas,
    detail_content_rect: tuple[float, float, float, float],
) -> None:
    """Place or hide the shared detail editor based on current detail view state."""

    detail_state = getattr(canvas, "detail_panel_state", DetailPanelState())
    if detail_state.view_kind != "player_memo" or detail_state.seat is None:
        _hide_detail_memo_editor(canvas)
        return

    _open_detail_memo_editor(canvas, detail_state.seat)
    memo_frame = getattr(canvas, "detail_memo_frame", None)
    if memo_frame is None:
        return
    left, top, right, bottom = detail_content_rect
    memo_frame.place(
        in_=canvas,
        x=left + DETAIL_EDITOR_INNER_MARGIN,
        y=top + DETAIL_EDITOR_INNER_MARGIN,
        width=max(right - left - DETAIL_EDITOR_INNER_MARGIN * 2, 40),
        height=max(bottom - top - DETAIL_EDITOR_INNER_MARGIN * 2, 40),
    )


def _detail_state_for_button(seat: int, label: str) -> DetailPanelState:
    """Return the common-detail target view for one player-panel button."""

    if label == "DETAIL":
        return DetailPanelState(view_kind="player_memo", seat=seat, button_label=label)
    return DetailPanelState(view_kind="panel_placeholder", seat=seat, button_label=label)


def _player_has_saved_memo(
    canvas: tkinter.Canvas,
    player_name: str,
) -> bool:
    """Return cached memo-presence state without touching disk during redraw."""

    normalized_name = str(player_name).strip()
    if not normalized_name:
        return False
    memo_presence_cache = getattr(canvas, "player_memo_presence_cache", {})
    return bool(memo_presence_cache.get(normalized_name, False))


def _resolved_component_offsets_for_canvas(
    canvas: tkinter.Canvas,
    settings: LayoutTuningSettings | Mapping[str, object] | None = None,
) -> dict[str, tuple[int, int]]:
    """Resolve one tuning snapshot against the current canvas size and return its actual drag offsets."""

    effective_settings = _normalize_layout_tuning_settings(
        settings if settings is not None else getattr(canvas, "layout_tuning_settings", None)
    )
    _width, _height, board_rect = _canvas_board_rect(canvas)
    image_table = getattr(canvas, "image_table", getattr(canvas, "base_image_table", None))
    if image_table is None:
        return _normalize_component_offsets(effective_settings.component_offsets)
    layout = _build_layout(
        board_rect[0],
        board_rect[1],
        board_rect[2],
        board_rect[3],
        image_table,
        float(getattr(canvas, "current_ui_scale", 1.0)),
        layout_tuning=effective_settings,
    )
    return _normalize_component_offsets(layout.get("resolved_component_offsets", {}))


def _current_resolved_component_offsets(
    canvas: tkinter.Canvas,
) -> dict[str, tuple[int, int]]:
    """Return the latest on-screen resolved drag offsets without mutating persisted tuning."""

    cached_offsets = getattr(canvas, "layout_resolved_component_offsets", None)
    if cached_offsets is not None:
        return _normalize_component_offsets(cached_offsets)
    return _resolved_component_offsets_for_canvas(canvas)


def _start_layout_component_drag(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Start dragging one movable layout rectangle when LAYOUT mode is active."""

    if not getattr(canvas, "layout_drag_enabled", False):
        return False
    for spec in getattr(canvas, "layout_drag_specs", ()):
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        if spec.drag_kind == "field_pair" and spec.field_names is not None:
            current_settings = _current_layout_tuning(canvas)
            current_offsets = (
                int(getattr(current_settings, spec.field_names[0])),
                int(getattr(current_settings, spec.field_names[1])),
            )
        else:
            current_offsets = _current_resolved_component_offsets(canvas).get(spec.key, (0, 0))
        canvas.layout_drag_state = LayoutDragState(
            spec=spec,
            start_pointer=(click_x, click_y),
            start_offset=current_offsets,
        )
        _set_layout_tuning_status(
            canvas,
            f"Dragging {spec.label}. Release to keep preview, Save to persist.",
            "#7dd3fc",
        )
        return True
    return False


def _update_layout_component_drag(
    canvas: tkinter.Canvas,
    pointer_x: float,
    pointer_y: float,
) -> bool:
    """Update one active layout drag and preview the resolved, non-overlapping result."""

    drag_state = getattr(canvas, "layout_drag_state", None)
    if not isinstance(drag_state, LayoutDragState):
        return False
    if drag_state.spec.drag_kind == "field_pair" and drag_state.spec.field_names is not None:
        current_settings = _current_layout_tuning(canvas)
        field_x, field_y = drag_state.spec.field_names
        ui_scale = max(float(getattr(canvas, "current_ui_scale", 1.0)), 0.01)
        desired_x = drag_state.start_offset[0] + int(round((pointer_x - drag_state.start_pointer[0]) / ui_scale))
        desired_y = drag_state.start_offset[1] + int(round((pointer_y - drag_state.start_pointer[1]) / ui_scale))
        clamped_x = int(
            max(
                LAYOUT_TUNING_CONTROL_BY_FIELD[field_x].min_value,
                min(LAYOUT_TUNING_CONTROL_BY_FIELD[field_x].max_value, desired_x),
            )
        )
        clamped_y = int(
            max(
                LAYOUT_TUNING_CONTROL_BY_FIELD[field_y].min_value,
                min(LAYOUT_TUNING_CONTROL_BY_FIELD[field_y].max_value, desired_y),
            )
        )
        if (
            int(getattr(current_settings, field_x)) == clamped_x
            and int(getattr(current_settings, field_y)) == clamped_y
        ):
            return False
        canvas.layout_tuning_settings = replace(
            current_settings,
            **{
                field_x: clamped_x,
                field_y: clamped_y,
            },
        )
        _set_layout_tuning_status(
            canvas,
            f"Dragging {drag_state.spec.label}: dx {clamped_x}, dy {clamped_y}. Save to persist.",
            "#7dd3fc",
        )
        return True
    current_settings = _current_layout_tuning(canvas)
    current_offsets = _normalize_component_offsets(current_settings.component_offsets)
    current_resolved_offsets = _current_resolved_component_offsets(canvas)
    desired_offsets = dict(current_offsets)
    desired_offsets[drag_state.spec.key] = (
        drag_state.start_offset[0] + int(round(pointer_x - drag_state.start_pointer[0])),
        drag_state.start_offset[1] + int(round(pointer_y - drag_state.start_pointer[1])),
    )
    candidate_settings = replace(current_settings, component_offsets=desired_offsets)
    resolved_offsets = _resolved_component_offsets_for_canvas(canvas, candidate_settings)
    if resolved_offsets == current_resolved_offsets:
        return False
    canvas.layout_tuning_settings = replace(current_settings, component_offsets=resolved_offsets)
    actual_dx, actual_dy = resolved_offsets.get(drag_state.spec.key, (0, 0))
    _set_layout_tuning_status(
        canvas,
        f"Dragging {drag_state.spec.label}: dx {actual_dx}, dy {actual_dy}. Save to persist.",
        "#7dd3fc",
    )
    return True


def _finish_layout_component_drag(
    canvas: tkinter.Canvas,
) -> bool:
    """Finish one active drag session and leave the previewed offsets in place."""

    drag_state = getattr(canvas, "layout_drag_state", None)
    if not isinstance(drag_state, LayoutDragState):
        return False
    canvas.layout_drag_state = None
    if drag_state.spec.drag_kind == "field_pair" and drag_state.spec.field_names is not None:
        current_settings = _current_layout_tuning(canvas)
        actual_dx = int(getattr(current_settings, drag_state.spec.field_names[0]))
        actual_dy = int(getattr(current_settings, drag_state.spec.field_names[1]))
        _set_layout_tuning_status(
            canvas,
            f"{drag_state.spec.label} previewed at dx {actual_dx}, dy {actual_dy}. Save to persist.",
            "#facc15",
        )
        return True
    current_offsets = _current_resolved_component_offsets(canvas)
    actual_dx, actual_dy = current_offsets.get(drag_state.spec.key, (0, 0))
    _set_layout_tuning_status(
        canvas,
        f"{drag_state.spec.label} previewed at dx {actual_dx}, dy {actual_dy}. Save to persist.",
        "#facc15",
    )
    return True


def _normalize_lag_marker_reference_kind(raw_kind: object) -> str:
    """Normalize the shared lag-marker reference toggle into one supported kind."""

    normalized_kind = str(raw_kind or "").strip().lower()
    if normalized_kind == LAG_MARKER_REFERENCE_KIND_BLACK:
        return LAG_MARKER_REFERENCE_KIND_BLACK
    if normalized_kind == LAG_MARKER_REFERENCE_KIND_GREEN:
        return LAG_MARKER_REFERENCE_KIND_GREEN
    return LAG_MARKER_REFERENCE_KIND_BLUE


def _normalize_lag_marker_reference_kind_overrides(
    raw_overrides: Mapping[tuple[object, ...], object] | None,
) -> dict[tuple[object, ...], str]:
    """Normalize per-discard lag-marker mode overrides."""

    normalized: dict[tuple[object, ...], str] = {}
    if not isinstance(raw_overrides, Mapping):
        return normalized
    for raw_key, raw_kind in raw_overrides.items():
        normalized[tuple(raw_key)] = _normalize_lag_marker_reference_kind(raw_kind)
    return normalized


def _next_lag_marker_reference_kind(current_kind: object) -> str:
    """Return the next lag-marker interpretation state in `blue -> green -> black` order."""

    normalized_kind = _normalize_lag_marker_reference_kind(current_kind)
    if normalized_kind == LAG_MARKER_REFERENCE_KIND_BLUE:
        return LAG_MARKER_REFERENCE_KIND_GREEN
    if normalized_kind == LAG_MARKER_REFERENCE_KIND_GREEN:
        return LAG_MARKER_REFERENCE_KIND_BLACK
    return LAG_MARKER_REFERENCE_KIND_BLUE


def _empty_table_situation_scores() -> tuple[int, ...]:
    """Return one neutral 10-block score tuple used by the manual situation tables."""

    return tuple(0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT))


def _clamp_table_situation_score(raw_score: object) -> int:
    """Clamp one manual situation score into the supported `-4..4` range."""

    try:
        numeric_score = int(raw_score)
    except (TypeError, ValueError):
        return 0
    return max(-TABLE_SITUATION_MANUAL_SCORE_MAX, min(TABLE_SITUATION_MANUAL_SCORE_MAX, numeric_score))


def _normalize_table_situation_scores_by_seat(
    raw_scores_by_seat: Mapping[int, Iterable[object]] | None,
) -> dict[int, tuple[int, ...]]:
    """Normalize per-opponent manual situation scores into fixed 10-block tuples."""

    normalized = {
        int(seat): _empty_table_situation_scores()
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    if not isinstance(raw_scores_by_seat, Mapping):
        return normalized
    for raw_seat, raw_scores in raw_scores_by_seat.items():
        try:
            seat = int(raw_seat)
        except (TypeError, ValueError):
            continue
        if seat not in normalized:
            continue
        candidate_scores = list(_empty_table_situation_scores())
        if isinstance(raw_scores, SequenceABC):
            for block_index, raw_score in enumerate(raw_scores[:TABLE_SITUATION_BLOCK_COUNT]):
                candidate_scores[block_index] = _clamp_table_situation_score(raw_score)
        normalized[seat] = tuple(candidate_scores)
    return normalized


def _normalize_table_situation_display_scores_by_seat(
    raw_scores_by_seat: Mapping[int, Iterable[object]] | None,
) -> dict[int, tuple[float, ...]]:
    """Normalize rendered per-seat situation scores while preserving decimal auto-reflections."""

    normalized = {
        int(seat): tuple(0.0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT))
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    if not isinstance(raw_scores_by_seat, Mapping):
        return normalized
    for raw_seat, raw_scores in raw_scores_by_seat.items():
        try:
            seat = int(raw_seat)
        except (TypeError, ValueError):
            continue
        if seat not in normalized:
            continue
        candidate_scores = [0.0] * TABLE_SITUATION_BLOCK_COUNT
        if isinstance(raw_scores, SequenceABC):
            for block_index, raw_score in enumerate(raw_scores[:TABLE_SITUATION_BLOCK_COUNT]):
                candidate_scores[block_index] = _clamp_table_situation_display_score(raw_score)
        normalized[seat] = tuple(candidate_scores)
    return normalized


def _adjust_table_situation_score(current_score: object, delta: int) -> int:
    """Move one manual situation score by `delta` while staying inside `-4..4`."""

    normalized_score = _clamp_table_situation_score(current_score)
    return _clamp_table_situation_score(normalized_score + int(delta))


def _set_table_situation_score(
    canvas: tkinter.Canvas,
    seat: int,
    block_index: int,
    score: object,
) -> bool:
    """Persist one manual score inside the canvas-local per-round state."""

    normalized_scores = {
        current_seat: list(current_scores)
        for current_seat, current_scores in _normalize_table_situation_scores_by_seat(
            getattr(canvas, "table_situation_scores_by_seat", {})
        ).items()
    }
    if int(seat) not in normalized_scores:
        return False
    if not 0 <= int(block_index) < TABLE_SITUATION_BLOCK_COUNT:
        return False
    normalized_scores[int(seat)][int(block_index)] = _clamp_table_situation_score(score)
    canvas.table_situation_scores_by_seat = {
        current_seat: tuple(current_scores)
        for current_seat, current_scores in normalized_scores.items()
    }
    return True


def _table_situation_discard_tile_34_index(discard: object) -> int | None:
    """Return one discard's 34-kind tile index from either live or legacy discard records."""

    tile_34_index = getattr(discard, "tile_34", None)
    if tile_34_index is not None:
        try:
            normalized_tile_34_index = int(tile_34_index)
        except (TypeError, ValueError):
            normalized_tile_34_index = None
        if normalized_tile_34_index is not None and 0 <= normalized_tile_34_index < 34:
            return normalized_tile_34_index
    return tile37_to_tile34_index(getattr(discard, "tile_id", None))


def _is_table_situation_tedashi_discard(discard: object) -> bool:
    """Return True when one discard is a tedashi regardless of whether it was later called."""

    draw_type = getattr(discard, "draw_type", None)
    if draw_type is not None:
        try:
            return int(draw_type) == int(DrawType.TEDASHI)
        except (TypeError, ValueError):
            pass
    return not bool(getattr(discard, "tsumogiri", False))


def _table_situation_inner_bucket(number: int) -> int:
    """Return one monotonic `innerness` bucket where `4-6 > 3/7 > 2/8 > 1/9`."""

    try:
        normalized_number = int(number)
    except (TypeError, ValueError):
        return -1
    if not 1 <= normalized_number <= 9:
        return -1
    return min(min(normalized_number, 10 - normalized_number), 4)


def _table_situation_block_index_for_tile_34(tile_34_index: int | None) -> int | None:
    """Map one 34-kind tile to the corresponding 3x3/honor situation block index."""

    try:
        normalized_tile_34_index = int(tile_34_index)
    except (TypeError, ValueError):
        return None
    if 0 <= normalized_tile_34_index < 27:
        return (normalized_tile_34_index // 9) * 3 + ((normalized_tile_34_index % 9) // 3)
    if 27 <= normalized_tile_34_index < 34:
        return 9
    return None


def _table_situation_red_tint_neighbor_targets(
    tile_34_index: int | None,
    *,
    fast_early_tedashi: bool,
) -> tuple[tuple[int, float], ...]:
    """Return the suited neighbor tiles that improve the table-situation score before red tint."""

    try:
        normalized_tile_34_index = int(tile_34_index)
    except (TypeError, ValueError):
        return ()
    if not 0 <= normalized_tile_34_index < 27:
        return ()
    suit_index = normalized_tile_34_index // 9
    suit_number = normalized_tile_34_index % 9 + 1
    source_bucket = _table_situation_inner_bucket(suit_number)
    adjacent_score = (
        TABLE_SITUATION_AUTO_FAST_ADJACENT_SCORE
        if fast_early_tedashi
        else TABLE_SITUATION_AUTO_BASE_ADJACENT_SCORE
    )
    inner_two_away_score = (
        TABLE_SITUATION_AUTO_FAST_INNER_TWO_AWAY_SCORE
        if fast_early_tedashi
        else TABLE_SITUATION_AUTO_BASE_INNER_TWO_AWAY_SCORE
    )
    targets: list[tuple[int, float]] = []
    for delta in (-1, 1):
        target_number = suit_number + delta
        if not 1 <= target_number <= 9:
            continue
        targets.append((suit_index * 9 + (target_number - 1), float(adjacent_score)))
    for delta in (-2, 2):
        target_number = suit_number + delta
        if not 1 <= target_number <= 9:
            continue
        if _table_situation_inner_bucket(target_number) < source_bucket:
            continue
        targets.append((suit_index * 9 + (target_number - 1), float(inner_two_away_score)))
    return tuple(targets)


def _table_situation_red_tint_positive_targets(
    tile_34_index: int | None,
) -> tuple[tuple[int, float], ...]:
    """Return positive block hints contributed by one red-tint discard itself."""

    try:
        normalized_tile_34_index = int(tile_34_index)
    except (TypeError, ValueError):
        return ()
    if not 0 <= normalized_tile_34_index < 27:
        return ()
    suit_index = normalized_tile_34_index // 9
    suit_number = normalized_tile_34_index % 9 + 1
    targets: list[tuple[int, float]] = []
    for delta in (-1, 1):
        target_number = suit_number + delta
        if not 1 <= target_number <= 9:
            continue
        targets.append(
            (
                suit_index * 9 + (target_number - 1),
                float(TABLE_SITUATION_AUTO_RED_TINT_ADJACENT_SCORE),
            )
        )
    for delta in (-2, 2):
        target_number = suit_number + delta
        if not 1 <= target_number <= 9:
            continue
        targets.append(
            (
                suit_index * 9 + (target_number - 1),
                float(TABLE_SITUATION_AUTO_RED_TINT_TWO_AWAY_SCORE),
            )
        )
    return tuple(targets)


def _build_table_situation_auto_scores_by_seat(
    discard_map: Mapping[Player, Iterable[Discard]],
    discard_red_tint_indices_by_seat: Mapping[int, Iterable[int]] | None,
) -> dict[int, tuple[float, ...]]:
    """Build per-seat auto-reflected situation scores from tedashi before the first red-tint discard."""

    auto_scores_by_seat = {
        int(seat): tuple(0.0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT))
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }
    normalized_red_tint_indices = _normalize_discard_red_tint_indices_by_seat(
        discard_red_tint_indices_by_seat
    )
    for player in HAND_DANGER_BAR_SEAT_ORDER:
        seat = int(player)
        discards = tuple(discard_map.get(player, ()))
        highlighted_indices = sorted(
            discard_index
            for discard_index in normalized_red_tint_indices.get(seat, frozenset())
            if 0 <= discard_index < len(discards)
        )
        if not highlighted_indices:
            continue
        first_red_tint_index = highlighted_indices[0]
        tile_scores = [0.0] * 27
        tedashi_count = 0
        for discard_index, discard in enumerate(discards[:first_red_tint_index]):
            if not _is_table_situation_tedashi_discard(discard):
                continue
            tedashi_count += 1
            source_tile_34_index = _table_situation_discard_tile_34_index(discard)
            if source_tile_34_index is None or not 0 <= source_tile_34_index < 27:
                continue
            thinking_time_ms = getattr(discard, "thinking_time_ms", None)
            try:
                normalized_thinking_time_ms = (
                    None if thinking_time_ms is None else float(thinking_time_ms)
                )
            except (TypeError, ValueError):
                normalized_thinking_time_ms = None
            fast_early_tedashi = (
                tedashi_count <= TABLE_SITUATION_AUTO_FAST_TEDASHI_LIMIT
                and normalized_thinking_time_ms is not None
                and normalized_thinking_time_ms <= TABLE_SITUATION_AUTO_FAST_THINKING_MS_MAX
            )
            for target_tile_34_index, amount in _table_situation_red_tint_neighbor_targets(
                source_tile_34_index,
                fast_early_tedashi=fast_early_tedashi,
            ):
                tile_scores[target_tile_34_index] += float(amount)
        for discard_index in highlighted_indices:
            discard = discards[discard_index]
            source_tile_34_index = _table_situation_discard_tile_34_index(discard)
            if source_tile_34_index is None or not 0 <= source_tile_34_index < 27:
                continue
            for target_tile_34_index, amount in _table_situation_red_tint_positive_targets(
                source_tile_34_index
            ):
                tile_scores[target_tile_34_index] += float(amount)
        block_scores = [0.0] * TABLE_SITUATION_BLOCK_COUNT
        for block_index in range(9):
            suit_index = block_index // 3
            group_index = block_index % 3
            block_start = suit_index * 9 + group_index * 3
            block_scores[block_index] = sum(tile_scores[block_start : block_start + 3]) / 3.0
        auto_scores_by_seat[seat] = tuple(block_scores)
    return auto_scores_by_seat


def _resolve_table_situation_scores_by_seat(
    manual_scores_by_seat: Mapping[int, Sequence[object]] | None,
    auto_scores_by_seat: Mapping[int, Sequence[object]] | None,
) -> dict[int, tuple[float, ...]]:
    """Combine manual adjustments and auto-reflected table-situation scores into one display map."""

    normalized_manual_scores = _normalize_table_situation_scores_by_seat(manual_scores_by_seat)
    normalized_auto_scores = _normalize_table_situation_display_scores_by_seat(auto_scores_by_seat)
    resolved_scores: dict[int, tuple[float, ...]] = {}
    for seat in HAND_DANGER_BAR_SEAT_ORDER:
        manual_scores = normalized_manual_scores.get(int(seat), _empty_table_situation_scores())
        auto_scores = normalized_auto_scores.get(
            int(seat),
            tuple(0.0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT)),
        )
        resolved_scores[int(seat)] = tuple(
            float(manual_scores[block_index]) + float(auto_scores[block_index])
            for block_index in range(TABLE_SITUATION_BLOCK_COUNT)
        )
    return resolved_scores


def _table_situation_total(scores: Sequence[object]) -> float:
    """Return the signed total for one 10-block rendered situation score vector."""

    return sum(_clamp_table_situation_display_score(score) for score in scores[:TABLE_SITUATION_BLOCK_COUNT])


def _clamp_table_situation_display_score(score: object) -> float:
    """Clamp one rendered score into the display range while preserving decimals."""

    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        numeric_score = 0.0
    return max(-TABLE_SITUATION_DISPLAY_SCORE_MAX, min(TABLE_SITUATION_DISPLAY_SCORE_MAX, numeric_score))


def _round_half_away_from_zero(value: float) -> int:
    """Round one float away from zero so aggregate cells stay intuitive around `±0.5`."""

    normalized_value = float(value)
    if normalized_value >= 0:
        return int(normalized_value + 0.5)
    return int(normalized_value - 0.5)


def _aggregate_table_situation_scores(
    scores_by_seat: Mapping[int, Sequence[object]] | None,
) -> tuple[float, ...]:
    """Return one common-view 10-block score vector by averaging the three opponent tables."""

    normalized_scores = _normalize_table_situation_display_scores_by_seat(scores_by_seat)
    aggregated_scores: list[float] = []
    for block_index in range(TABLE_SITUATION_BLOCK_COUNT):
        block_total = 0.0
        for seat in HAND_DANGER_BAR_SEAT_ORDER:
            block_total += float(
                normalized_scores.get(
                    seat,
                    tuple(0.0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT)),
                )[block_index]
            )
        aggregated_scores.append(
            _clamp_table_situation_display_score(
                block_total / max(len(HAND_DANGER_BAR_SEAT_ORDER), 1)
            )
        )
    return tuple(aggregated_scores)


def _table_situation_scores_have_fractional_component(scores: Sequence[object]) -> bool:
    """Return whether one score vector contains visible decimal information."""

    for score in scores[:TABLE_SITUATION_BLOCK_COUNT]:
        normalized_score = _clamp_table_situation_display_score(score)
        if abs(normalized_score - round(normalized_score)) >= 0.001:
            return True
    return False


def _table_situation_zero_suited_division(scores: Sequence[object]) -> float:
    """Return `Σ / zero_suited_block_count` using only the nine suited common-panel blocks."""

    normalized_scores = [
        _clamp_table_situation_display_score(score)
        for score in scores[:TABLE_SITUATION_BLOCK_COUNT]
    ]
    zero_suited_block_count = sum(
        1
        for score in normalized_scores[:9]
        if abs(score) < 0.05
    )
    if zero_suited_block_count <= 0:
        return 0.0
    return sum(normalized_scores) / float(zero_suited_block_count)


def _table_situation_cell_colors(score: object) -> tuple[str, str, str]:
    """Return `(fill, outline, text)` colors for one manual situation score cell."""

    normalized_score = _clamp_table_situation_display_score(score)
    if normalized_score <= -3.0:
        return ("#123622", "#22c55e", "#dcfce7")
    if normalized_score <= -1.0:
        return ("#173b31", "#34d399", "#d1fae5")
    if normalized_score < 1.0:
        return ("#172233", "#475569", "#cbd5e1")
    if normalized_score < 3.0:
        return ("#3f2716", "#f59e0b", "#fde68a")
    return ("#4c1d1d", "#ef4444", "#fecaca")


def _table_situation_total_colors(total_score: object) -> tuple[str, str, str]:
    """Return colors for the total summary box using the same polarity as each cell."""

    return _table_situation_cell_colors(
        max(
            -TABLE_SITUATION_DISPLAY_SCORE_MAX,
            min(TABLE_SITUATION_DISPLAY_SCORE_MAX, _clamp_table_situation_display_score(total_score)),
        )
    )


def _format_table_situation_total_text(total_score: object, *, force_decimal: bool = False) -> str:
    """Format one signed total for the compact panel footer."""

    try:
        numeric_total = float(total_score)
    except (TypeError, ValueError):
        numeric_total = 0.0
    if force_decimal:
        return f"{numeric_total:+.1f}" if abs(numeric_total) >= 0.05 else "0.0"
    if abs(numeric_total - round(numeric_total)) < 0.001:
        normalized_total = int(round(numeric_total))
        return f"{normalized_total:+d}" if normalized_total else "0"
    return f"{numeric_total:+.1f}" if abs(numeric_total) >= 0.05 else "0.0"


def _handle_table_situation_cell_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Increment one manual situation cell score by `+1` on primary click."""

    if not TABLE_SITUATION_ENABLED:
        return False
    click_specs = tuple(getattr(canvas, "table_situation_cell_click_specs", ()))
    if not click_specs:
        return False
    current_scores = _normalize_table_situation_scores_by_seat(
        getattr(canvas, "table_situation_scores_by_seat", {})
    )
    for spec in click_specs:
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        seat_scores = current_scores.get(int(spec.seat), _empty_table_situation_scores())
        current_score = seat_scores[int(spec.block_index)]
        return _set_table_situation_score(
            canvas,
            int(spec.seat),
            int(spec.block_index),
            _adjust_table_situation_score(current_score, +1),
        )
    return False


def _handle_table_situation_cell_secondary_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Decrement one manual situation cell score by `-1` on secondary click."""

    if not TABLE_SITUATION_ENABLED:
        return False
    click_specs = tuple(getattr(canvas, "table_situation_cell_click_specs", ()))
    if not click_specs:
        return False
    current_scores = _normalize_table_situation_scores_by_seat(
        getattr(canvas, "table_situation_scores_by_seat", {})
    )
    for spec in click_specs:
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        seat_scores = current_scores.get(int(spec.seat), _empty_table_situation_scores())
        current_score = seat_scores[int(spec.block_index)]
        return _set_table_situation_score(
            canvas,
            int(spec.seat),
            int(spec.block_index),
            _adjust_table_situation_score(current_score, -1),
        )
    return False


def _lag_marker_reference_entry_key(
    round_identity: object | None,
    player: Player,
    discard: Discard,
    fallback_index: int,
) -> tuple[object, ...]:
    """Return one stable per-discard key for lag-marker UI overrides."""

    return (
        "lag_marker",
        str(round_identity or ""),
        int(player),
        _discard_global_index(discard, fallback_index),
        int(getattr(discard, "event_index", -1)),
        int(getattr(discard, "round_discard_index", -1)),
        int(getattr(discard, "tile_id", 0)),
    )


def _lag_marker_base_kind_from_color(color: str) -> str:
    """Return the default `L/Pl` mode represented by one lag-marker color."""

    return (
        LAG_MARKER_REFERENCE_KIND_GREEN
        if _lag_marker_label(color) == "Pl"
        else LAG_MARKER_REFERENCE_KIND_BLUE
    )


def _handle_lag_marker_reference_button_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Cycle one discard's lag-marker interpretation when one marker hitbox is clicked."""

    button_specs = getattr(canvas, "lag_marker_reference_button_specs", ())
    kind_overrides = _normalize_lag_marker_reference_kind_overrides(
        getattr(canvas, "lag_marker_reference_kinds_by_entry", {})
    )
    for spec in button_specs:
        center_x, center_y = spec.center
        dx = float(click_x) - center_x
        dy = float(click_y) - center_y
        if dx * dx + dy * dy > float(spec.radius) * float(spec.radius):
            continue
        current_kind = _normalize_lag_marker_reference_kind(spec.kind)
        next_kind = _next_lag_marker_reference_kind(current_kind)
        base_kind = _normalize_lag_marker_reference_kind(
            getattr(spec, "base_kind", LAG_MARKER_REFERENCE_KIND_BLUE)
        )
        entry_key = tuple(getattr(spec, "entry_key", ()))
        if entry_key:
            if next_kind == base_kind:
                kind_overrides.pop(entry_key, None)
            else:
                kind_overrides[entry_key] = next_kind
            canvas.lag_marker_reference_kinds_by_entry = kind_overrides
        canvas.lag_marker_reference_kind = next_kind
        return True
    return False


def _inferred_visible_candidate_seat_order() -> tuple[int, ...]:
    """Return the seat order used by lag-based inferred-visible candidate buttons."""

    return (
        int(Player.KAMICHA),
        int(Player.SHIMOCHA),
        int(Player.TOIMEN),
    )


def _inferred_visible_entry_key(
    round_identity: object | None,
    discard: Discard,
) -> tuple[object, ...]:
    """Build one stable key for a lag-based inferred-visible entry."""

    return (
        str(round_identity or ""),
        INFERRED_VISIBLE_REASON_PON_LAG,
        int(getattr(discard, "event_index", -1)),
        int(getattr(discard, "round_discard_index", -1)),
        int(getattr(discard, "tile_id", 0)),
    )


def _red_tint_neighbor_entry_key(
    round_identity: object | None,
    seat: int,
    discard: Discard,
    target_tile_34_index: int,
    distance: int,
) -> tuple[object, ...]:
    """Build one stable key for a red-tint-derived inferred-visible entry."""

    return (
        str(round_identity or ""),
        INFERRED_VISIBLE_REASON_RED_TINT_NEIGHBOR,
        int(seat),
        int(getattr(discard, "event_index", -1)),
        int(getattr(discard, "round_discard_index", -1)),
        int(getattr(discard, "tile_id", 0)),
        int(target_tile_34_index),
        int(distance),
    )


def _empty_inferred_visible_count_tuple() -> tuple[float, ...]:
    """Return one empty 34-kind float tuple used by inferred visible-count bookkeeping."""

    return tuple(0.0 for _unused_index in range(34))


def _inferred_visible_runtime_enabled(canvas: object | None) -> bool:
    """Return whether inferred-visible runtime work is enabled for one canvas."""

    if canvas is None:
        return bool(INFERRED_VISIBLE_ENABLED)
    return bool(getattr(canvas, "inferred_visible_runtime_enabled", INFERRED_VISIBLE_ENABLED))


def _single_tile_inferred_count_tuple(
    tile_34_index: int,
    amount: float,
) -> tuple[float, ...]:
    """Return one 34-kind float tuple with `amount` only at `tile_34_index`."""

    normalized_amount = max(0.0, float(amount))
    if tile_34_index < 0 or tile_34_index >= 34 or normalized_amount <= 0.0:
        return _empty_inferred_visible_count_tuple()
    counts = [0.0] * 34
    counts[tile_34_index] = normalized_amount
    return tuple(counts)


def _red_tint_neighbor_targets(
    tile_34_index: int | None,
) -> tuple[tuple[int, float, int], ...]:
    """Return suited neighbor tile kinds implied by one red-tint discard."""

    try:
        normalized_index = int(tile_34_index)
    except (TypeError, ValueError):
        return ()
    if not 0 <= normalized_index < 27:
        return ()
    suit_index = normalized_index // 9
    suit_number = normalized_index % 9 + 1
    targets: list[tuple[int, float, int]] = []
    for distance, amount in (
        (1, INFERRED_VISIBLE_RED_TINT_ADJACENT_AMOUNT),
        (2, INFERRED_VISIBLE_RED_TINT_TWO_AWAY_AMOUNT),
    ):
        for delta in (-distance, distance):
            target_number = suit_number + delta
            if not 1 <= target_number <= 9:
                continue
            targets.append((suit_index * 9 + (target_number - 1), float(amount), distance))
    return tuple(targets)


def _build_red_tint_inferred_entries(
    discard_map: Mapping[Player, Iterable[Discard]],
    round_identity: object | None,
    discard_red_tint_indices_by_seat: Mapping[int, Iterable[int]] | None,
) -> list[InferredVisibleEntry]:
    """Build inferred-visible entries from each opponent's red-tint discards."""

    normalized_red_tint_indices = _normalize_discard_red_tint_indices_by_seat(
        discard_red_tint_indices_by_seat
    )
    entries: list[InferredVisibleEntry] = []
    for player in (Player.KAMICHA, Player.TOIMEN, Player.SHIMOCHA):
        seat = int(player)
        highlighted_indices = normalized_red_tint_indices.get(seat, frozenset())
        if not highlighted_indices:
            continue
        discards = tuple(discard_map.get(player, ()))
        for discard_index in sorted(highlighted_indices):
            if discard_index < 0 or discard_index >= len(discards):
                continue
            discard = discards[discard_index]
            source_tile_34_index = tile37_to_tile34_index(getattr(discard, "tile_id", None))
            if source_tile_34_index is None:
                continue
            for target_tile_34_index, amount, distance in _red_tint_neighbor_targets(source_tile_34_index):
                entries.append(
                    InferredVisibleEntry(
                        key=_red_tint_neighbor_entry_key(
                            round_identity,
                            seat,
                            discard,
                            target_tile_34_index,
                            distance,
                        ),
                        tile_37=int(_canonical_tile37_from_tile34_index(target_tile_34_index) or 0),
                        tile_34_index=int(target_tile_34_index),
                        source_kind=INFERRED_VISIBLE_REASON_RED_TINT_NEIGHBOR,
                        source_event_index=int(getattr(discard, "event_index", -1)),
                        source_discard_index=int(getattr(discard, "round_discard_index", -1)),
                        candidate_seats=(seat,),
                        active_candidate_seats=(seat,),
                        inactive_candidate_seats=(),
                        revealed_candidate_seats=(),
                        seat_adjustments_34_index={
                            seat: _single_tile_inferred_count_tuple(target_tile_34_index, amount)
                        },
                        total_adjustment=float(amount),
                    )
                )
    return entries


def _candidate_revealed_same_tile_after_source(
    discard_map: Mapping[Player, Iterable[Discard]],
    *,
    seat: int,
    tile_34_index: int,
    source_event_index: int,
) -> bool:
    """Return whether one candidate seat later discarded the inferred tile kind."""

    if source_event_index < 0:
        return False
    try:
        player = Player(int(seat))
    except ValueError:
        return False
    for discard in discard_map.get(player, ()):
        discard_event_index = int(getattr(discard, "event_index", -1))
        if discard_event_index < 0 or discard_event_index <= source_event_index:
            continue
        if tile37_to_tile34_index(getattr(discard, "tile_id", None)) != tile_34_index:
            continue
        return True
    return False


def _normalize_inferred_visible_entry_exclusions(
    exclusions_by_entry: Mapping[tuple[object, ...], Iterable[int]] | None,
) -> dict[tuple[object, ...], set[int]]:
    """Normalize inferred-visible exclusion toggles into one stable key->seat-set mapping."""

    normalized: dict[tuple[object, ...], set[int]] = {}
    if not isinstance(exclusions_by_entry, Mapping):
        return normalized
    for key, seats in exclusions_by_entry.items():
        normalized[tuple(key)] = {int(seat) for seat in seats}
    return normalized


def _normalize_inferred_visible_deleted_entry_keys(
    deleted_entry_keys: Iterable[tuple[object, ...]] | None,
) -> set[tuple[object, ...]]:
    """Normalize inferred-visible deleted-entry state into one stable entry-key set."""

    normalized: set[tuple[object, ...]] = set()
    if deleted_entry_keys is None:
        return normalized
    for key in deleted_entry_keys:
        normalized.add(tuple(key))
    return normalized


def _normalize_inferred_visible_manual_counts_by_tile34(
    raw_counts: Mapping[int, object] | None,
) -> dict[int, int]:
    """Clamp manual inferred-visible tile counters into `0..4` indexed by tile34."""

    normalized: dict[int, int] = {}
    if not isinstance(raw_counts, Mapping):
        return normalized
    for raw_tile_34_index, raw_count in raw_counts.items():
        try:
            tile_34_index = int(raw_tile_34_index)
            manual_count = int(raw_count)
        except (TypeError, ValueError):
            continue
        if tile_34_index < 0 or tile_34_index >= 34:
            continue
        normalized_count = max(0, min(4, manual_count))
        if normalized_count <= 0:
            continue
        normalized[tile_34_index] = normalized_count
    return normalized


def _selected_inferred_visible_popup_entry_key(
    canvas: tkinter.Canvas,
    tile_34_index: int,
) -> tuple[object, ...]:
    """Return one stable virtual entry key for the selected inferred-visible popup buttons."""

    return (
        _SELECTED_INFERRED_VISIBLE_POPUP_ENTRY_KIND,
        str(getattr(canvas, "current_round_identity", "") or ""),
        int(tile_34_index),
    )


def _is_selected_inferred_visible_popup_entry_key(entry_key: tuple[object, ...] | Sequence[object]) -> bool:
    """Return whether one inferred-visible candidate-button key belongs to the selected popup."""

    if not entry_key:
        return False
    return str(entry_key[0]) == _SELECTED_INFERRED_VISIBLE_POPUP_ENTRY_KIND


def _normalize_selected_inferred_visible_disabled_seats_by_tile34(
    raw_mapping: Mapping[int, Iterable[object]] | None,
) -> dict[int, set[int]]:
    """Normalize selected-popup seat toggles into one tile34 -> disabled-seat-set mapping."""

    popup_candidate_seat_order = (
        int(Player.KAMICHA),
        int(Player.TOIMEN),
        int(Player.SHIMOCHA),
    )
    normalized: dict[int, set[int]] = {}
    if not isinstance(raw_mapping, Mapping):
        return normalized
    for raw_tile_34_index, raw_seats in raw_mapping.items():
        try:
            tile_34_index = int(raw_tile_34_index)
        except (TypeError, ValueError):
            continue
        if not 0 <= tile_34_index < 34:
            continue
        disabled_seats: set[int] = set()
        for raw_seat in raw_seats:
            try:
                seat = int(raw_seat)
            except (TypeError, ValueError):
                continue
            if seat in popup_candidate_seat_order:
                disabled_seats.add(seat)
        if disabled_seats:
            normalized[tile_34_index] = disabled_seats
    return normalized


def _build_inferred_visible_entries_from_state(
    discard_map: Mapping[Player, Iterable[Discard]],
    round_identity: object | None,
    *,
    discard_red_tint_indices_by_seat: Mapping[int, Iterable[int]] | None = None,
    lag_kinds_by_entry: Mapping[tuple[object, ...], object] | None = None,
    exclusions_by_entry: Mapping[tuple[object, ...], Iterable[int]] | None = None,
    deleted_entry_keys: Iterable[tuple[object, ...]] | None = None,
) -> tuple[list[InferredVisibleEntry], dict[tuple[object, ...], set[int]], set[tuple[object, ...]]]:
    """Build lag-based inferred-visible entries from actual discards only.

    This path intentionally ignores awaseuchi/public-event history. Actual visible counts stay in
    `VisibleTileSummary`, while inferred entries are derived separately from the self river plus the
    current lag-marker UI toggles.
    """

    normalized_lag_kinds_by_entry = _normalize_lag_marker_reference_kind_overrides(
        lag_kinds_by_entry
    )
    multi_player_lag_tiles_34 = _collect_multi_player_lag_tiles_34(discard_map)
    candidate_seat_order = _inferred_visible_candidate_seat_order()
    existing_exclusions = _normalize_inferred_visible_entry_exclusions(exclusions_by_entry)
    existing_deleted_keys = _normalize_inferred_visible_deleted_entry_keys(deleted_entry_keys)
    current_keys: set[tuple[object, ...]] = set()
    entries: list[InferredVisibleEntry] = []
    for entry in _build_red_tint_inferred_entries(
        discard_map,
        round_identity,
        discard_red_tint_indices_by_seat,
    ):
        current_keys.add(entry.key)
        if entry.key in existing_deleted_keys:
            continue
        excluded_seats = {
            seat
            for seat in existing_exclusions.get(entry.key, set())
            if seat in entry.candidate_seats
        }
        active_candidate_seats = tuple(
            seat for seat in entry.candidate_seats if seat not in excluded_seats
        )
        inactive_candidate_seats = tuple(
            seat for seat in entry.candidate_seats if seat in excluded_seats
        )
        seat_adjustments_34_index = {
            int(seat): (
                adjustments
                if seat in active_candidate_seats
                else _empty_inferred_visible_count_tuple()
            )
            for seat, adjustments in entry.seat_adjustments_34_index.items()
        }
        total_adjustment = 0.0
        for seat in active_candidate_seats:
            adjustments = seat_adjustments_34_index.get(int(seat), ())
            if 0 <= entry.tile_34_index < len(adjustments):
                total_adjustment += float(adjustments[entry.tile_34_index])
        entries.append(
            InferredVisibleEntry(
                key=entry.key,
                tile_37=entry.tile_37,
                tile_34_index=entry.tile_34_index,
                source_kind=entry.source_kind,
                source_event_index=entry.source_event_index,
                source_discard_index=entry.source_discard_index,
                candidate_seats=entry.candidate_seats,
                active_candidate_seats=active_candidate_seats,
                inactive_candidate_seats=inactive_candidate_seats,
                revealed_candidate_seats=(),
                seat_adjustments_34_index=seat_adjustments_34_index,
                total_adjustment=total_adjustment,
            )
        )
    for discard_index, discard in enumerate(discard_map.get(Player.JICHA, ())):
        if (
            _is_riseki_completion_discard(discard)
            or discard.called
            or not _is_visual_lag_flag(getattr(discard, "lagged", 0))
        ):
            continue
        tile_34_index = tile37_to_tile34_index(getattr(discard, "tile_id", None))
        if tile_34_index is None:
            continue
        entry_key = _inferred_visible_entry_key(round_identity, discard)
        lag_marker_entry_key = _lag_marker_reference_entry_key(
            round_identity,
            Player.JICHA,
            discard,
            discard_index,
        )
        base_kind = _lag_marker_base_kind_from_color(
            _lag_marker_color(Player.JICHA, discard, multi_player_lag_tiles_34)
        )
        effective_lag_kind = _normalize_lag_marker_reference_kind(
            normalized_lag_kinds_by_entry.get(lag_marker_entry_key, base_kind)
        )
        current_keys.add(entry_key)
        if effective_lag_kind == LAG_MARKER_REFERENCE_KIND_BLACK:
            continue
        if entry_key in existing_deleted_keys:
            continue
        excluded_seats = {
            seat
            for seat in existing_exclusions.get(entry_key, set())
            if seat in candidate_seat_order
        }
        active_candidate_seats = tuple(
            seat for seat in candidate_seat_order if seat not in excluded_seats
        )
        inactive_candidate_seats = tuple(
            seat for seat in candidate_seat_order if seat in excluded_seats
        )
        base_total_amount = (
            INFERRED_VISIBLE_PON_LAG_AMOUNT
            if effective_lag_kind == LAG_MARKER_REFERENCE_KIND_GREEN
            else 0.0
        )
        base_share = (
            float(base_total_amount) / len(active_candidate_seats)
            if active_candidate_seats
            else 0.0
        )
        revealed_candidate_seats: list[int] = []
        seat_adjustments_34_index: dict[int, tuple[float, ...]] = {}
        total_adjustment = 0.0
        for seat in candidate_seat_order:
            seat_amount = base_share if seat in active_candidate_seats else 0.0
            if seat_amount > 0.0 and _candidate_revealed_same_tile_after_source(
                discard_map,
                seat=seat,
                tile_34_index=tile_34_index,
                source_event_index=int(getattr(discard, "event_index", -1)),
            ):
                seat_amount = max(0.0, seat_amount - INFERRED_VISIBLE_REVEAL_REDUCTION)
                revealed_candidate_seats.append(seat)
            seat_adjustments_34_index[seat] = _single_tile_inferred_count_tuple(
                tile_34_index,
                seat_amount,
            )
            total_adjustment += seat_amount
        entries.append(
            InferredVisibleEntry(
                key=entry_key,
                tile_37=int(getattr(discard, "tile_id", 0)),
                tile_34_index=int(tile_34_index),
                source_kind=INFERRED_VISIBLE_REASON_PON_LAG,
                source_event_index=int(getattr(discard, "event_index", -1)),
                source_discard_index=int(getattr(discard, "round_discard_index", -1)),
                candidate_seats=candidate_seat_order,
                active_candidate_seats=active_candidate_seats,
                inactive_candidate_seats=inactive_candidate_seats,
                revealed_candidate_seats=tuple(revealed_candidate_seats),
                seat_adjustments_34_index=seat_adjustments_34_index,
                total_adjustment=total_adjustment,
            )
        )
    normalized_exclusions = {
        key: set(existing_exclusions.get(key, set()))
        for key in current_keys
    }
    normalized_deleted_keys = {
        key
        for key in existing_deleted_keys
        if key in current_keys
    }
    return entries, normalized_exclusions, normalized_deleted_keys


def _build_inferred_visible_entries(
    canvas: tkinter.Canvas,
    discard_map: Mapping[Player, Iterable[Discard]],
    round_identity: object | None,
    discard_red_tint_indices_by_seat: Mapping[int, Iterable[int]] | None = None,
) -> list[InferredVisibleEntry]:
    """Build lag-based inferred-visible entries from the current self river and UI toggles."""

    entries, normalized_exclusions, normalized_deleted_keys = _build_inferred_visible_entries_from_state(
        discard_map,
        round_identity,
        discard_red_tint_indices_by_seat=discard_red_tint_indices_by_seat,
        lag_kinds_by_entry=getattr(canvas, "lag_marker_reference_kinds_by_entry", {}),
        exclusions_by_entry=getattr(canvas, "inferred_visible_entry_excluded_seats", {}),
        deleted_entry_keys=getattr(canvas, "inferred_visible_deleted_entry_keys", set()),
    )
    canvas.inferred_visible_entry_excluded_seats = normalized_exclusions
    canvas.inferred_visible_deleted_entry_keys = normalized_deleted_keys
    canvas.inferred_visible_entries = list(entries)
    return entries


def _build_visible_tile_inference_summary_from_entries(
    visible_summary: VisibleTileSummary,
    entries: Sequence[InferredVisibleEntry],
    *,
    manual_counts_by_tile34: Mapping[int, object] | None = None,
) -> VisibleTileInferenceSummary:
    """Combine actual visible counts with one prebuilt inferred-entry list."""

    player_adjustments: dict[int, list[float]] = {
        seat: [0.0] * 34
        for seat in _inferred_visible_candidate_seat_order()
    }
    global_adjustments = [0.0] * 34
    for entry in entries:
        for seat, adjustments in entry.seat_adjustments_34_index.items():
            seat_counts = player_adjustments.setdefault(int(seat), [0.0] * 34)
            for tile_34_index, value in enumerate(adjustments):
                if value <= 0.0:
                    continue
                seat_counts[tile_34_index] += float(value)
                global_adjustments[tile_34_index] += float(value)
    for tile_34_index, manual_count in _normalize_inferred_visible_manual_counts_by_tile34(
        manual_counts_by_tile34
    ).items():
        global_adjustments[tile_34_index] += float(manual_count)
    return build_visible_tile_inference_summary(
        visible_summary,
        global_adjustments_34_index=tuple(global_adjustments),
        player_adjustments_34_index=player_adjustments,
    )


def _inferred_visible_discard_map_signature(
    discard_map: Mapping[Player, Iterable[Discard]],
) -> tuple[tuple[int, tuple[tuple[int, bool, int, int, int], ...]], ...]:
    """Return one stable signature for the actual discard data used by inferred-visible logic."""

    return tuple(
        (
            int(player),
            tuple(
                (
                    int(getattr(discard, "tile_id", 0)),
                    bool(getattr(discard, "called", False)),
                    int(getattr(discard, "lagged", 0)),
                    int(getattr(discard, "event_index", -1)),
                    int(getattr(discard, "round_discard_index", -1)),
                )
                for discard in discard_map.get(player, ())
            ),
        )
        for player in Player
    )


def _inferred_visible_exclusion_signature(
    exclusions_by_entry: Mapping[tuple[object, ...], Iterable[int]],
) -> tuple[tuple[tuple[object, ...], tuple[int, ...]], ...]:
    """Return one stable signature for per-entry inferred-visible candidate exclusions."""

    return tuple(
        sorted(
            (
                tuple(key),
                tuple(sorted(int(seat) for seat in seats)),
            )
            for key, seats in exclusions_by_entry.items()
        )
    )


def _inferred_visible_deleted_key_signature(
    deleted_entry_keys: Iterable[tuple[object, ...]],
) -> tuple[tuple[object, ...], ...]:
    """Return one stable signature for inferred-visible deleted entry keys."""

    return tuple(sorted(tuple(key) for key in deleted_entry_keys))


def _lag_marker_reference_kind_override_signature(
    lag_kinds_by_entry: Mapping[tuple[object, ...], object] | None,
) -> tuple[tuple[tuple[object, ...], str], ...]:
    """Return one stable signature for per-discard lag-marker mode overrides."""

    return tuple(
        sorted(
            (
                tuple(key),
                _normalize_lag_marker_reference_kind(kind),
            )
            for key, kind in _normalize_lag_marker_reference_kind_overrides(
                lag_kinds_by_entry
            ).items()
        )
    )


def _inferred_visible_async_cache_key(
    discard_map: Mapping[Player, Iterable[Discard]],
    visible_summary: VisibleTileSummary,
    round_identity: object | None,
    *,
    discard_red_tint_indices_by_seat: Mapping[int, Iterable[int]] | None,
    lag_kinds_by_entry: Mapping[tuple[object, ...], object] | None,
    exclusions_by_entry: Mapping[tuple[object, ...], Iterable[int]],
    deleted_entry_keys: Iterable[tuple[object, ...]],
) -> tuple[object, ...]:
    """Return one cache key for the async inferred-visible worker state."""

    return (
        "inferred_visible",
        round_identity,
        tuple(int(count) for count in getattr(visible_summary, "visible_counts_34_index", ())),
        tuple(
            (
                int(seat),
                tuple(sorted(int(index) for index in indices)),
            )
            for seat, indices in sorted(
                _normalize_discard_red_tint_indices_by_seat(discard_red_tint_indices_by_seat).items()
            )
        ),
        _lag_marker_reference_kind_override_signature(lag_kinds_by_entry),
        _inferred_visible_exclusion_signature(exclusions_by_entry),
        _inferred_visible_deleted_key_signature(deleted_entry_keys),
        _inferred_visible_discard_map_signature(discard_map),
    )


def _ensure_inferred_visible_background_worker(
    canvas: tkinter.Canvas,
) -> None:
    """Start the long-lived inferred-visible worker once for this canvas."""

    existing_thread = getattr(canvas, "inferred_visible_async_thread", None)
    if isinstance(existing_thread, threading.Thread) and existing_thread.is_alive():
        return
    request_queue = getattr(canvas, "inferred_visible_async_request_queue", None)
    if request_queue is None:
        request_queue = queue.Queue()
        canvas.inferred_visible_async_request_queue = request_queue
    result_queue = getattr(canvas, "inferred_visible_async_result_queue", None)
    if result_queue is None:
        result_queue = queue.Queue()
        canvas.inferred_visible_async_result_queue = result_queue

    def _schedule_apply() -> None:
        try:
            canvas.after(
                0,
                lambda: (
                    getattr(canvas, "redraw_action", None)()
                    if callable(getattr(canvas, "redraw_action", None))
                    else None
                ),
            )
        except (AttributeError, tkinter.TclError):
            return

    def _worker() -> None:
        while True:
            job = request_queue.get()
            if job is _INFERRED_VISIBLE_WORKER_STOP:
                return
            latest_job = job
            while True:
                try:
                    next_job = request_queue.get_nowait()
                except queue.Empty:
                    break
                if next_job is _INFERRED_VISIBLE_WORKER_STOP:
                    return
                latest_job = next_job
            if not isinstance(latest_job, Mapping):
                continue
            cache_key = latest_job.get("cache_key")
            discard_map = latest_job.get("discard_map", {})
            visible_summary = latest_job.get("visible_summary")
            round_identity = latest_job.get("round_identity")
            lag_kinds_by_entry = latest_job.get("lag_kinds_by_entry", {})
            exclusions_by_entry = latest_job.get("exclusions_by_entry", {})
            deleted_entry_keys = latest_job.get("deleted_entry_keys", ())
            if not isinstance(visible_summary, VisibleTileSummary):
                continue
            try:
                entries, normalized_exclusions, normalized_deleted_keys = _build_inferred_visible_entries_from_state(
                    discard_map,
                    round_identity,
                    discard_red_tint_indices_by_seat=latest_job.get("discard_red_tint_indices_by_seat", {}),
                    lag_kinds_by_entry=lag_kinds_by_entry,
                    exclusions_by_entry=exclusions_by_entry,
                    deleted_entry_keys=deleted_entry_keys,
                )
                result_queue.put(
                    {
                        "cache_key": cache_key,
                        "ok": True,
                        "summary": _build_visible_tile_inference_summary_from_entries(
                            visible_summary,
                            entries,
                        ),
                        "entries": tuple(entries),
                        "exclusions": normalized_exclusions,
                        "deleted_keys": normalized_deleted_keys,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - background inference must not block redraw.
                result_queue.put(
                    {
                        "cache_key": cache_key,
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            finally:
                _schedule_apply()

    worker_thread = threading.Thread(
        target=_worker,
        name="inferred-visible-worker",
        daemon=True,
    )
    canvas.inferred_visible_async_thread = worker_thread
    worker_thread.start()


def _queue_inferred_visible_background_update(
    canvas: tkinter.Canvas,
    cache_key: tuple[object, ...],
    discard_map: Mapping[Player, Iterable[Discard]],
    visible_summary: VisibleTileSummary,
    round_identity: object | None,
    *,
    discard_red_tint_indices_by_seat: Mapping[int, Iterable[int]] | None,
    lag_kinds_by_entry: Mapping[tuple[object, ...], object] | None,
    exclusions_by_entry: Mapping[tuple[object, ...], Iterable[int]],
    deleted_entry_keys: Iterable[tuple[object, ...]],
) -> None:
    """Queue one recomputation onto the long-lived inferred-visible worker.

    This path reuses one persistent worker thread per canvas, so it must not emit the
    background-thread start notice on every queued job.
    """

    if not _inferred_visible_runtime_enabled(canvas):
        return

    _ensure_inferred_visible_background_worker(canvas)
    if getattr(canvas, "inferred_visible_async_completed_cache_key", None) == cache_key:
        return
    if getattr(canvas, "inferred_visible_async_pending_key", None) == cache_key:
        return
    request_queue = getattr(canvas, "inferred_visible_async_request_queue", None)
    if request_queue is None:
        return
    immutable_discard_map = {
        player: tuple(discard_map.get(player, ()))
        for player in Player
    }
    immutable_lag_kinds_by_entry = _normalize_lag_marker_reference_kind_overrides(
        lag_kinds_by_entry
    )
    immutable_red_tint_indices_by_seat = _normalize_discard_red_tint_indices_by_seat(
        discard_red_tint_indices_by_seat
    )
    immutable_exclusions = _normalize_inferred_visible_entry_exclusions(exclusions_by_entry)
    immutable_deleted_keys = _normalize_inferred_visible_deleted_entry_keys(deleted_entry_keys)
    canvas.inferred_visible_async_in_flight = True
    canvas.inferred_visible_async_pending_key = cache_key
    request_queue.put(
        {
            "cache_key": cache_key,
            "discard_map": immutable_discard_map,
            "visible_summary": visible_summary,
            "round_identity": round_identity,
            "discard_red_tint_indices_by_seat": immutable_red_tint_indices_by_seat,
            "lag_kinds_by_entry": immutable_lag_kinds_by_entry,
            "exclusions_by_entry": immutable_exclusions,
            "deleted_entry_keys": tuple(sorted(immutable_deleted_keys)),
        }
    )


def _drain_inferred_visible_background_result_queue(canvas: tkinter.Canvas) -> bool:
    """Apply finished inferred-visible worker payloads back onto the Tk thread."""

    if not _inferred_visible_runtime_enabled(canvas):
        return False

    result_queue = getattr(canvas, "inferred_visible_async_result_queue", None)
    if result_queue is None:
        return False
    changed = False
    requested_key = getattr(canvas, "inferred_visible_async_requested_key", None)
    while True:
        try:
            payload = result_queue.get_nowait()
        except queue.Empty:
            break
        if not isinstance(payload, Mapping):
            continue
        cache_key = payload.get("cache_key")
        if cache_key == getattr(canvas, "inferred_visible_async_pending_key", None):
            canvas.inferred_visible_async_pending_key = None
            canvas.inferred_visible_async_in_flight = False
        changed = True
        if not bool(payload.get("ok", False)):
            continue
        if cache_key != requested_key:
            continue
        summary = payload.get("summary")
        if not isinstance(summary, VisibleTileInferenceSummary):
            continue
        entries = payload.get("entries")
        if not isinstance(entries, SequenceABC):
            continue
        canvas.inferred_visible_async_completed_cache_key = cache_key
        canvas.current_visible_tile_inference_summary = summary
        canvas.inferred_visible_entries = list(entries)
        canvas.inferred_visible_entry_excluded_seats = _normalize_inferred_visible_entry_exclusions(
            payload.get("exclusions", {})
        )
        canvas.inferred_visible_deleted_entry_keys = _normalize_inferred_visible_deleted_entry_keys(
            payload.get("deleted_keys", ())
        )
    return changed


def _build_visible_tile_inference_summary_for_canvas(
    canvas: tkinter.Canvas,
    discard_map: Mapping[Player, Iterable[Discard]],
    visible_summary: VisibleTileSummary,
    round_identity: object | None,
    discard_red_tint_indices_by_seat: Mapping[int, Iterable[int]] | None = None,
) -> tuple[VisibleTileInferenceSummary, list[InferredVisibleEntry]]:
    """Return the inferred-visible summary, computed separately from actual visible counts."""

    if not _inferred_visible_runtime_enabled(canvas):
        summary = VisibleTileInferenceSummary()
        canvas.current_visible_tile_inference_summary = summary
        canvas.inferred_visible_async_requested_key = None
        canvas.inferred_visible_async_pending_key = None
        canvas.inferred_visible_async_in_flight = False
        return summary, []

    lag_kinds_by_entry = _normalize_lag_marker_reference_kind_overrides(
        getattr(canvas, "lag_marker_reference_kinds_by_entry", {})
    )
    manual_counts_by_tile34 = _normalize_inferred_visible_manual_counts_by_tile34(
        getattr(canvas, "inferred_visible_manual_counts_by_tile34", {})
    )
    base_summary = _build_visible_tile_inference_summary_from_entries(
        visible_summary,
        (),
        manual_counts_by_tile34=manual_counts_by_tile34,
    )
    exclusions_by_entry = _normalize_inferred_visible_entry_exclusions(
        getattr(canvas, "inferred_visible_entry_excluded_seats", {})
    )
    deleted_entry_keys = _normalize_inferred_visible_deleted_entry_keys(
        getattr(canvas, "inferred_visible_deleted_entry_keys", set())
    )
    cache_key = _inferred_visible_async_cache_key(
        discard_map,
        visible_summary,
        round_identity,
        discard_red_tint_indices_by_seat=discard_red_tint_indices_by_seat,
        lag_kinds_by_entry=lag_kinds_by_entry,
        exclusions_by_entry=exclusions_by_entry,
        deleted_entry_keys=deleted_entry_keys,
    )
    canvas.inferred_visible_async_requested_key = cache_key
    if getattr(canvas, "inferred_visible_async_completed_cache_key", None) == cache_key:
        entries = list(getattr(canvas, "inferred_visible_entries", ()))
        summary = _build_visible_tile_inference_summary_from_entries(
            visible_summary,
            entries,
            manual_counts_by_tile34=manual_counts_by_tile34,
        )
        canvas.current_visible_tile_inference_summary = summary
        return summary, entries
    _queue_inferred_visible_background_update(
        canvas,
        cache_key,
        discard_map,
        visible_summary,
        round_identity,
        discard_red_tint_indices_by_seat=discard_red_tint_indices_by_seat,
        lag_kinds_by_entry=lag_kinds_by_entry,
        exclusions_by_entry=exclusions_by_entry,
        deleted_entry_keys=deleted_entry_keys,
    )
    current_entries = list(getattr(canvas, "inferred_visible_entries", ()))
    summary = _build_visible_tile_inference_summary_from_entries(
        visible_summary,
        current_entries,
        manual_counts_by_tile34=manual_counts_by_tile34,
    )
    canvas.current_visible_tile_inference_summary = summary
    return summary, current_entries


def _canonical_tile37_from_tile34_index(tile_34_index: int | None) -> int | None:
    """Return the default non-red 37-kind display tile for one canonical 34-index."""

    try:
        normalized_index = int(tile_34_index)
    except (TypeError, ValueError):
        return None
    if 0 <= normalized_index <= 8:
        return normalized_index + 1
    if 9 <= normalized_index <= 17:
        return normalized_index + 2
    if 18 <= normalized_index <= 26:
        return normalized_index + 3
    if 27 <= normalized_index <= 33:
        return normalized_index + 4
    return None


def _select_inferred_visible_tile(
    canvas: tkinter.Canvas,
    tile_37: int | None,
) -> bool:
    """Select one tile kind for the inferred-visible popup using a 37-kind display id."""

    tile_34_index = tile37_to_tile34_index(tile_37)
    if tile_34_index is None:
        return False
    canvas.selected_inferred_visible_tile_34_index = int(tile_34_index)
    canvas.selected_inferred_visible_tile_37 = int(tile_37)
    return True


def _clear_selected_inferred_visible_tile(canvas: tkinter.Canvas) -> None:
    """Dismiss the focused inferred-visible tile popup without clearing manual counts."""

    canvas.selected_inferred_visible_tile_34_index = None
    canvas.selected_inferred_visible_tile_37 = None


def _set_inferred_visible_manual_count(
    canvas: tkinter.Canvas,
    tile_34_index: int | None,
    count: int,
) -> bool:
    """Set one manual inferred-visible count directly, clamped to `x0..x4`."""

    if tile_34_index is None:
        return False
    normalized_tile_34_index = int(tile_34_index)
    if not 0 <= normalized_tile_34_index < 34:
        return False
    manual_counts = _normalize_inferred_visible_manual_counts_by_tile34(
        getattr(canvas, "inferred_visible_manual_counts_by_tile34", {})
    )
    normalized_count = max(0, min(4, int(count)))
    if normalized_count <= 0:
        manual_counts.pop(normalized_tile_34_index, None)
    else:
        manual_counts[normalized_tile_34_index] = normalized_count
    canvas.inferred_visible_manual_counts_by_tile34 = manual_counts
    return True


def _handle_inferred_visible_candidate_button_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Toggle one inferred-visible candidate seat button."""

    button_specs = tuple(getattr(canvas, "inferred_visible_candidate_button_specs", ()))
    if not button_specs:
        return False
    exclusions_by_entry = {
        tuple(key): {int(seat) for seat in seats}
        for key, seats in getattr(canvas, "inferred_visible_entry_excluded_seats", {}).items()
    }
    popup_disabled_seats_by_tile34 = _normalize_selected_inferred_visible_disabled_seats_by_tile34(
        getattr(canvas, "selected_inferred_visible_disabled_seats_by_tile34", {})
    )
    for spec in button_specs:
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        target_entry_keys = tuple(getattr(spec, "entry_keys", ()) or (spec.entry_key,))
        if target_entry_keys and all(
            _is_selected_inferred_visible_popup_entry_key(tuple(entry_key))
            for entry_key in target_entry_keys
        ):
            tile_34_index = int(target_entry_keys[0][2])
            current_disabled_seats = set(popup_disabled_seats_by_tile34.get(tile_34_index, set()))
            if int(spec.seat) in current_disabled_seats:
                current_disabled_seats.discard(int(spec.seat))
            else:
                current_disabled_seats.add(int(spec.seat))
            if current_disabled_seats:
                popup_disabled_seats_by_tile34[tile_34_index] = current_disabled_seats
            else:
                popup_disabled_seats_by_tile34.pop(tile_34_index, None)
            canvas.selected_inferred_visible_disabled_seats_by_tile34 = popup_disabled_seats_by_tile34
            return True
        should_enable = not any(
            int(spec.seat) not in exclusions_by_entry.get(tuple(entry_key), set())
            for entry_key in target_entry_keys
        )
        for entry_key in target_entry_keys:
            current_exclusions = set(exclusions_by_entry.get(tuple(entry_key), set()))
            if should_enable:
                current_exclusions.discard(int(spec.seat))
            else:
                current_exclusions.add(int(spec.seat))
            exclusions_by_entry[tuple(entry_key)] = current_exclusions
        canvas.inferred_visible_entry_excluded_seats = exclusions_by_entry
        return True
    return False


def _handle_inferred_visible_candidate_button_double_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Keep only the double-clicked candidate seat active for one inferred-visible entry."""

    button_specs = tuple(getattr(canvas, "inferred_visible_candidate_button_specs", ()))
    if not button_specs:
        return False
    exclusions_by_entry = {
        tuple(key): {int(seat) for seat in seats}
        for key, seats in getattr(canvas, "inferred_visible_entry_excluded_seats", {}).items()
    }
    popup_disabled_seats_by_tile34 = _normalize_selected_inferred_visible_disabled_seats_by_tile34(
        getattr(canvas, "selected_inferred_visible_disabled_seats_by_tile34", {})
    )
    for spec in button_specs:
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        candidate_seats = {
            int(seat)
            for seat in tuple(getattr(spec, "all_candidate_seats", ()))
        }
        if not candidate_seats:
            candidate_seats = {int(spec.seat)}
        target_entry_keys = tuple(getattr(spec, "entry_keys", ()) or (spec.entry_key,))
        if target_entry_keys and all(
            _is_selected_inferred_visible_popup_entry_key(tuple(entry_key))
            for entry_key in target_entry_keys
        ):
            tile_34_index = int(target_entry_keys[0][2])
            popup_disabled_seats_by_tile34[tile_34_index] = {
                int(candidate_seat)
                for candidate_seat in candidate_seats
                if int(candidate_seat) != int(spec.seat)
            }
            canvas.selected_inferred_visible_disabled_seats_by_tile34 = popup_disabled_seats_by_tile34
            return True
        next_exclusions = {
            int(candidate_seat)
            for candidate_seat in candidate_seats
            if int(candidate_seat) != int(spec.seat)
        }
        for entry_key in target_entry_keys:
            exclusions_by_entry[tuple(entry_key)] = set(next_exclusions)
        canvas.inferred_visible_entry_excluded_seats = exclusions_by_entry
        return True
    return False


def _handle_inferred_visible_tile_count_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Cycle one manual inferred-visible tile count between `x0` and `x4`."""

    click_specs = tuple(getattr(canvas, "inferred_visible_tile_count_click_specs", ()))
    if not click_specs:
        return False
    for spec in click_specs:
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        manual_counts = _normalize_inferred_visible_manual_counts_by_tile34(
            getattr(canvas, "inferred_visible_manual_counts_by_tile34", {})
        )
        current_count = int(manual_counts.get(int(spec.tile_34_index), 0))
        next_count = (current_count + 1) % 5
        return _set_inferred_visible_manual_count(canvas, int(spec.tile_34_index), next_count)
    return False


def _handle_inferred_visible_manual_count_button_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Set one manual inferred-visible count directly from `x0..x4` buttons."""

    click_specs = tuple(getattr(canvas, "inferred_visible_manual_count_button_specs", ()))
    if not click_specs:
        return False
    for spec in click_specs:
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        return _set_inferred_visible_manual_count(canvas, int(spec.tile_34_index), int(spec.count))
    return False


def _handle_selected_inferred_visible_delete_button_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Dismiss the currently selected inferred-visible popup tile."""

    button_specs = tuple(getattr(canvas, "selected_inferred_visible_delete_button_specs", ()))
    if not button_specs:
        return False
    for spec in button_specs:
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        _clear_selected_inferred_visible_tile(canvas)
        return True
    return False


def _handle_inferred_visible_delete_button_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Hide one inferred-visible entry card from both the popup list and its adjustment summary."""

    button_specs = tuple(getattr(canvas, "inferred_visible_delete_button_specs", ()))
    if not button_specs:
        return False
    deleted_entry_keys = _normalize_inferred_visible_deleted_entry_keys(
        getattr(canvas, "inferred_visible_deleted_entry_keys", set())
    )
    for spec in button_specs:
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        deleted_entry_keys.add(tuple(spec.entry_key))
        canvas.inferred_visible_deleted_entry_keys = deleted_entry_keys
        return True
    return False


def _handle_discard_tile_selection_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Select one discard tile kind so inferred-visible cards only show that 34 kind."""

    click_specs = tuple(getattr(canvas, "discard_tile_selection_click_specs", ()))
    if not click_specs:
        return False
    for spec in reversed(click_specs):
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        selected_tile_37 = getattr(spec, "tile_37", None)
        if selected_tile_37 is not None:
            return _select_inferred_visible_tile(canvas, selected_tile_37)
        canvas.selected_inferred_visible_tile_34_index = int(spec.tile_34_index)
        canvas.selected_inferred_visible_tile_37 = _canonical_tile37_from_tile34_index(
            int(spec.tile_34_index)
        )
        return True
    return False


def _filter_inferred_visible_entries_for_display(
    canvas: tkinter.Canvas,
    entries: Sequence[InferredVisibleEntry],
) -> list[InferredVisibleEntry]:
    """Return only the entries matching the currently selected discard tile kind."""

    selected_tile_34_index = getattr(canvas, "selected_inferred_visible_tile_34_index", None)
    try:
        normalized_selected_tile_34_index = int(selected_tile_34_index)
    except (TypeError, ValueError):
        return []
    if normalized_selected_tile_34_index < 0 or normalized_selected_tile_34_index >= 34:
        return []
    return [
        entry
        for entry in entries
        if int(entry.tile_34_index) == normalized_selected_tile_34_index
    ]


def _handle_player_panel_button_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Switch the shared detail view when one player-panel button is clicked."""

    button_specs = getattr(canvas, "player_panel_button_specs", ())
    current_state = getattr(canvas, "detail_panel_state", DetailPanelState())
    for spec in button_specs:
        left, top, right, bottom = spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        next_state = _detail_state_for_button(spec.seat, spec.label)
        if (
            current_state.view_kind == next_state.view_kind
            and current_state.seat == next_state.seat
            and current_state.button_label == next_state.button_label
        ):
            next_state = DetailPanelState()
        if current_state.view_kind == "player_memo" and not _save_detail_memo_if_needed(canvas):
            return True
        canvas.detail_panel_state = next_state
        if next_state.view_kind != "player_memo":
            _hide_detail_memo_editor(canvas)
        return True
    return False


def _handle_hand_response_button_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Toggle the self-hand recommendation panel from the compact hand-side button."""

    button_spec = getattr(canvas, "hand_response_button_spec", None)
    if button_spec is None:
        return False
    left, top, right, bottom = button_spec.rect
    if not (left <= click_x <= right and top <= click_y <= bottom):
        return False
    current_state = getattr(canvas, "hand_response_panel_state", HandResponsePanelState())
    canvas.hand_response_panel_state = HandResponsePanelState(
        visible=not current_state.visible,
        betaori_visible=bool(getattr(current_state, "betaori_visible", False)),
    )
    canvas.hand_response_requested_hand_key = None
    canvas.hand_response_last_request_started_monotonic_s = None
    return True


def _handle_hand_betaori_response_button_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Toggle the display-only betaori top3 panel from its hand-side button."""

    button_spec = getattr(canvas, "hand_betaori_response_button_spec", None)
    if button_spec is None:
        return False
    left, top, right, bottom = button_spec.rect
    if not (left <= click_x <= right and top <= click_y <= bottom):
        return False
    current_state = getattr(canvas, "hand_response_panel_state", HandResponsePanelState())
    canvas.hand_response_panel_state = HandResponsePanelState(
        visible=bool(getattr(current_state, "visible", False)),
        betaori_visible=not bool(getattr(current_state, "betaori_visible", False)),
    )
    return True


def _handle_self_hand_bridge_click(
    canvas: tkinter.Canvas,
    click_x: float,
    click_y: float,
) -> bool:
    """Execute one Tenhou discard when the user clicks a currently displayed self-hand tile."""

    click_specs = tuple(getattr(canvas, "self_hand_bridge_click_specs", ()))
    if not click_specs:
        return False
    if not callable(getattr(canvas, "hand_bridge_discard_by_index_action", None)):
        return False
    for click_spec in click_specs:
        left, top, right, bottom = click_spec.rect
        if not (left <= click_x <= right and top <= click_y <= bottom):
            continue
        return _dispatch_bridge_discard_by_index(
            canvas,
            int(click_spec.hand_index),
            feedback_text=f"Discard slot {click_spec.hand_index}...",
        )
    return False


def _handle_bridge_secondary_click(
    canvas: tkinter.Canvas,
) -> bool:
    """Handle one canvas right-click as `skip/pass` or `tsumogiri`, mirroring Tenhou shortcuts."""

    skip_control_id = _select_bridge_skip_control_id(_bridge_status_snapshot(canvas))
    if skip_control_id is not None:
        return _dispatch_bridge_control_click(
            canvas,
            skip_control_id,
            feedback_text="Skip...",
        )
    tsumogiri_index = _resolve_self_hand_tsumogiri_index(
        tuple(getattr(canvas, "self_hand_bridge_click_specs", ()))
    )
    if tsumogiri_index is None:
        return False
    return _dispatch_bridge_discard_by_index(
        canvas,
        tsumogiri_index,
        feedback_text=f"Tsumogiri slot {tsumogiri_index}...",
    )


def _format_hand_danger_count(value: float) -> str:
    """Format a weighted musuji count for compact UI display."""

    rounded_value = round(max(0.0, value), 1)
    return f"{rounded_value:.1f}".rstrip("0").rstrip(".")


def _format_hand_danger_numerator(value: float) -> str:
    """Format one numerator-side musuji count with one decimal place."""

    return f"{max(0.0, float(value)):.1f}"


def _split_player_panel_remain_text(summary_data: Mapping[str, object]) -> tuple[str, str]:
    """Split one player-panel remain display into a label and numeric body."""

    label_text = "Remain:"
    if bool(summary_data.get("is_loading", False)):
        return label_text, "..."
    remain_text = _format_hand_danger_count(float(summary_data.get("denominator_count", 0.0)))
    raw_no_temp_remain = summary_data.get("denominator_count_without_temporary_safe")
    try:
        no_temp_remain_text = (
            None
            if raw_no_temp_remain is None
            else _format_hand_danger_count(float(raw_no_temp_remain))
        )
    except (TypeError, ValueError):
        no_temp_remain_text = None
    if no_temp_remain_text is None:
        return label_text, remain_text
    return label_text, f"{remain_text}/{no_temp_remain_text}"


def _format_player_panel_remain_text(summary_data: Mapping[str, object]) -> str:
    """Format one player-panel remain string as `current/no-temp` when both are available."""

    label_text, value_text = _split_player_panel_remain_text(summary_data)
    return f"{label_text} {value_text}"


def _player_panel_remain_text_color(summary_data: Mapping[str, object], default_color: str) -> str:
    """Return the remain text color using only the no-temp remain thresholds."""

    if bool(summary_data.get("is_loading", False)):
        return default_color
    raw_no_temp_remain = summary_data.get("denominator_count_without_temporary_safe")
    try:
        no_temp_remain = float(raw_no_temp_remain)
    except (TypeError, ValueError):
        return default_color
    if no_temp_remain < 0.0:
        return default_color
    if no_temp_remain <= 6.0:
        return PLAYER_ALERT_PURPLE
    if no_temp_remain <= 9.0:
        return PLAYER_ALERT_RED
    if no_temp_remain <= 12.0:
        return PLAYER_ALERT_YELLOW
    return default_color


def _format_player_panel_line_summary_text(
    line_summary: Mapping[str, object],
    *,
    include_rank: bool = True,
    include_percent: bool = True,
) -> str:
    """Format one `Line` row as text like `1-4m m6 6%`."""

    rank_text = str(line_summary.get("rank_text", "") or "").strip()
    left_tile_label = str(line_summary.get("left_tile_label", "") or "").strip()
    right_tile_label = str(line_summary.get("right_tile_label", "") or "").strip()
    suit_label = str(line_summary.get("suit_label", "") or "").strip()
    percent_text = str(line_summary.get("percent_text", "") or "").strip()
    suit_remaining_count_text = str(
        line_summary.get("suit_remaining_count_text", "") or ""
    ).strip()
    line_label = ""
    if len(left_tile_label) >= 2 and len(right_tile_label) >= 2:
        left_number = left_tile_label[:-1]
        right_number = right_tile_label[:-1]
        line_suit_label = suit_label or right_tile_label[-1]
        if left_number and right_number and line_suit_label:
            line_label = f"{left_number}-{right_number}{line_suit_label}"
    trailing_parts = []
    if suit_label and suit_remaining_count_text:
        trailing_parts.append(f"{suit_label}{suit_remaining_count_text}")
    if include_percent and percent_text and percent_text != "-":
        trailing_parts.append(percent_text)
    parts: list[str] = []
    if include_rank and rank_text and line_label:
        parts.append(rank_text)
    if line_label:
        parts.append(line_label)
        parts.extend(trailing_parts)
        return " ".join(parts).strip() or "-"
    if include_percent and percent_text:
        return (
            " ".join(
                part
                for part in ((rank_text if include_rank else ""), percent_text)
                if part and part != "-"
            ).strip()
            or "-"
        )
    return "-"


def _combined_hand_danger_probability_percent(
    danger_percentages: HandDangerPercentages,
) -> float:
    """Combine seat-wise danger percentages into an at-least-one probability."""

    remaining_safe_probability = 1.0
    for seat in HAND_DANGER_BAR_SEAT_ORDER:
        seat_metrics = danger_percentages.get(
            seat,
            {
                "percentage": 0,
                "numerator_count": 0.0,
                "denominator_count": 0.0,
            },
        )
        seat_probability = max(0.0, min(100.0, float(seat_metrics.get("percentage", 0)))) / 100.0
        remaining_safe_probability *= 1.0 - seat_probability
    return (1.0 - remaining_safe_probability) * 100.0


def _hand_danger_tint_step(danger_probability_percent: float) -> int:
    """Quantize the combined danger probability into a tint step."""

    if danger_probability_percent <= HAND_DANGER_TINT_MIN_PERCENT:
        return 0
    clamped_percent = min(
        max(danger_probability_percent, HAND_DANGER_TINT_MIN_PERCENT),
        HAND_DANGER_TINT_MAX_PERCENT,
    )
    normalized_ratio = (
        (clamped_percent - HAND_DANGER_TINT_MIN_PERCENT)
        / (HAND_DANGER_TINT_MAX_PERCENT - HAND_DANGER_TINT_MIN_PERCENT)
    )
    return max(1, min(HAND_DANGER_TINT_STEPS, int(round(normalized_ratio * HAND_DANGER_TINT_STEPS))))


def _hand_danger_overlay_style(
    tint_step: int,
) -> tuple[tuple[int, int, int] | None, float]:
    """Return a full-tile overlay color/strength for one hand-danger tint step."""

    if tint_step <= 0:
        return None, 0.0

    first_stage_end = max(HAND_DANGER_TINT_STEPS // 2, 1)
    if tint_step <= first_stage_end:
        return (
            HAND_DANGER_TINT_YELLOW_COLOR,
            (tint_step / first_stage_end) * HAND_DANGER_TINT_MAX_BLEND,
        )

    stage_span = max(HAND_DANGER_TINT_STEPS - first_stage_end, 1)
    stage_ratio = (tint_step - first_stage_end) / stage_span
    overlay_color = tuple(
        int(round(
            HAND_DANGER_TINT_YELLOW_COLOR[index]
            + (HAND_DANGER_TINT_RED_COLOR[index] - HAND_DANGER_TINT_YELLOW_COLOR[index]) * stage_ratio
        ))
        for index in range(3)
    )
    return overlay_color, HAND_DANGER_TINT_MAX_BLEND


def _hand_danger_overlay_bands(
    danger_percentages: HandDangerPercentages,
) -> tuple[tuple[float, float, tuple[int, int, int], tuple[int, int, int], float], ...]:
    """Build the full-tile overlay bands for one self-hand tile."""

    combined_probability = _combined_hand_danger_probability_percent(danger_percentages)
    tint_step = _hand_danger_tint_step(combined_probability)
    overlay_color, overlay_strength = _hand_danger_overlay_style(tint_step)
    if overlay_color is None or overlay_strength <= 0.0:
        return ()
    return (
        (
            0.0,
            1.0,
            overlay_color,
            overlay_color,
            overlay_strength,
        ),
    )


def _hand_tile_image(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    tile_id: int,
    danger_percentages: HandDangerPercentages,
) -> tkinter.PhotoImage:
    """Return the self-hand tile image with combined danger tint when needed."""

    overlay_bands = _hand_danger_overlay_bands(danger_percentages)
    if not overlay_bands:
        return img_table[Player.JICHA][DrawType.TEDASHI][tile_id]

    cache_key = (
        tile_id,
        overlay_bands,
    )
    cache = getattr(canvas, "hand_danger_tile_image_cache", {})
    cached_image = cache.get(cache_key)
    if cached_image is not None:
        return cached_image

    tinted_image = build_tile_photoimage(
        canvas,
        tile_id,
        Player.JICHA,
        DrawType.TEDASHI,
        overlay_bands=overlay_bands,
        tile_scale=getattr(canvas, "current_ui_scale", 1.0),
    )
    cache[cache_key] = tinted_image
    canvas.hand_danger_tile_image_cache = cache
    return tinted_image


def _render_table_using_cached_layout_if_possible(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    discard_map: Mapping[Player, Iterable[Discard]],
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    hand_recommendation_panel: HandRecommendationPanelData,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    opponent_suji_panel_summaries: OpponentSujiPanelSummaries,
    player_push_alert_percentages: PlayerPushAlertPercentages,
    push_marker_alert_percentages: PlayerPushAlertPercentages,
    player_alert_indicators_by_seat: PlayerAlertIndicatorsBySeat,
    player_score_diffs_by_seat: PlayerScoreDiffs,
    discard_red_tint_indices_by_seat: dict[int, frozenset[int]],
    player_names_by_seat: PlayerNamesBySeat,
    meld_tiles: Sequence[int],
    dora_indicator_tiles: Sequence[int],
    round_events: Sequence[object] | None,
    round_info_panel: RoundInfoPanelData,
    melds_by_player: SeatMeldMap,
    visible_summary: VisibleTileSummary | None = None,
    self_hand_value_alert: SelfHandValueAlertState | None = None,
) -> tuple[bool, tuple[float, float, float, float]]:
    """Redraw dynamic table layers in-place when the previous layout is still reusable."""

    if not bool(getattr(canvas, "winfo_exists", lambda: False)()):
        return False, (0.0, 0.0, 0.0, 0.0)
    if _inferred_visible_runtime_enabled(canvas):
        return False, (0.0, 0.0, 0.0, 0.0)
    if bool(getattr(canvas, "layout_drag_enabled", False)):
        return False, (0.0, 0.0, 0.0, 0.0)
    layout = getattr(canvas, "last_render_layout", None)
    if not isinstance(layout, Mapping):
        return False, (0.0, 0.0, 0.0, 0.0)
    detail_content_rect = layout.get("detail_content_rect")
    hand_rect = layout.get("hand_rect")
    if (
        not isinstance(detail_content_rect, tuple)
        or len(detail_content_rect) != 4
        or not isinstance(hand_rect, tuple)
        or len(hand_rect) != 4
    ):
        return False, (0.0, 0.0, 0.0, 0.0)

    render_phase_timings: list[PhaseTiming] = []
    _reset_transient_canvas_draw_state(canvas)
    _delete_canvas_items_by_tags(canvas, _LIVE_LAYOUT_DRAG_TAG)
    canvas.current_hand_rect = tuple(float(value) for value in hand_rect)

    phase_started_at = time.perf_counter()
    if visible_summary is None:
        visible_summary = collect_visible_tile_summary(
            discard_map,
            hand_tiles,
            meld_tiles,
            dora_indicator_tiles,
        )
    visible_inference_summary, inferred_visible_entries = _build_visible_tile_inference_summary_for_canvas(
        canvas,
        discard_map,
        visible_summary,
        getattr(canvas, "current_round_identity", None),
        discard_red_tint_indices_by_seat,
    )
    if TABLE_SITUATION_ENABLED:
        manual_table_situation_scores_by_seat = _normalize_table_situation_scores_by_seat(
            getattr(canvas, "table_situation_scores_by_seat", {})
        )
        auto_table_situation_scores_by_seat = _build_table_situation_auto_scores_by_seat(
            discard_map,
            discard_red_tint_indices_by_seat,
        )
        resolved_table_situation_scores_by_seat = _resolve_table_situation_scores_by_seat(
            manual_table_situation_scores_by_seat,
            auto_table_situation_scores_by_seat,
        )
    else:
        auto_table_situation_scores_by_seat = {
            int(seat): tuple(0.0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT))
            for seat in HAND_DANGER_BAR_SEAT_ORDER
        }
        resolved_table_situation_scores_by_seat = {
            int(seat): tuple(0.0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT))
            for seat in HAND_DANGER_BAR_SEAT_ORDER
        }
    canvas.table_situation_auto_scores_by_seat = auto_table_situation_scores_by_seat
    canvas.table_situation_resolved_scores_by_seat = resolved_table_situation_scores_by_seat
    _append_phase_timing(render_phase_timings, "summaries", phase_started_at)

    phase_started_at = time.perf_counter()
    _redraw_side_panels_if_needed(
        canvas,
        img_table,
        layout,
        discard_map,
        melds_by_player,
        dora_indicator_tiles,
        visible_summary,
        visible_inference_summary,
        hand_tiles,
        hand_draw_tile,
        hand_danger_percentages,
        opponent_suji_panel_summaries,
        player_push_alert_percentages,
        player_alert_indicators_by_seat,
        player_score_diffs_by_seat,
        player_names_by_seat,
        getattr(canvas, "detail_panel_state", DetailPanelState()),
    )
    _append_phase_timing(render_phase_timings, "side_panels", phase_started_at)

    phase_started_at = time.perf_counter()
    _delete_canvas_items_by_tags(canvas, _LIVE_FRAME_TAG)
    frame_previous_items = _capture_canvas_item_ids(canvas)
    _draw_center_panel(canvas, layout["center_panel"], dora_indicator_tiles, round_info_panel)
    _draw_meld_zones(canvas, layout)
    _draw_discard_zones(canvas, layout)
    _draw_seat_labels(canvas, layout, round_info_panel)
    _draw_melds(canvas, img_table, melds_by_player, layout)
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_FRAME_TAG,
        previous_item_ids=frame_previous_items,
    )
    _append_phase_timing(render_phase_timings, "table_frame", phase_started_at)

    phase_started_at = time.perf_counter()
    _delete_canvas_items_by_tags(canvas, _LIVE_ASYNC_DISCARD_TAG)
    discard_previous_items = _capture_canvas_item_ids(canvas)
    _draw_discards(
        canvas,
        img_table,
        discard_map,
        discard_red_tint_indices_by_seat,
        layout,
        visible_summary,
        push_marker_alert_percentages,
        melds_by_player,
        round_events,
    )
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_ASYNC_DISCARD_TAG,
        previous_item_ids=discard_previous_items,
    )
    _append_phase_timing(render_phase_timings, "discards", phase_started_at)

    phase_started_at = time.perf_counter()
    _delete_canvas_items_by_tags(canvas, _LIVE_DETAIL_OVERLAY_TAG)
    detail_previous_items = _capture_canvas_item_ids(canvas)
    _draw_table_situation_seat_panels(canvas, layout)
    _draw_inferred_visible_sections(
        canvas,
        layout,
        inferred_visible_entries,
    )
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_DETAIL_OVERLAY_TAG,
        previous_item_ids=detail_previous_items,
    )
    _append_phase_timing(render_phase_timings, "detail_overlays", phase_started_at)

    phase_started_at = time.perf_counter()
    _delete_canvas_items_by_tags(canvas, _LIVE_ASYNC_HAND_TAG, _HAND_RESPONSE_UI_TAG)
    hand_previous_items = _capture_canvas_item_ids(canvas)
    _draw_hand(
        canvas,
        img_table,
        tuple(float(value) for value in hand_rect),
        hand_tiles,
        hand_draw_tile,
        dora_indicator_tiles,
        hand_recommendation_panel,
        getattr(canvas, "hand_response_panel_state", HandResponsePanelState()),
        hand_danger_percentages,
        visible_summary,
        (
            self_hand_value_alert
            if self_hand_value_alert is not None
            else SelfHandValueAlertState()
        ),
    )
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_ASYNC_HAND_TAG,
        previous_item_ids=hand_previous_items,
    )
    _append_phase_timing(render_phase_timings, "hand", phase_started_at)
    canvas.current_player_names_by_seat = player_names_by_seat
    canvas.current_player_alert_indicators_by_seat = player_alert_indicators_by_seat
    canvas.last_render_table_phase_timings = tuple(render_phase_timings)
    canvas.last_render_detail_content_rect = tuple(float(value) for value in detail_content_rect)
    return True, canvas.last_render_detail_content_rect


def _render_table(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    discard_map: Mapping[Player, Iterable[Discard]],
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    hand_recommendation_panel: HandRecommendationPanelData,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    opponent_suji_panel_summaries: OpponentSujiPanelSummaries,
    player_push_alert_percentages: PlayerPushAlertPercentages,
    push_marker_alert_percentages: PlayerPushAlertPercentages,
    player_alert_indicators_by_seat: PlayerAlertIndicatorsBySeat,
    player_score_diffs_by_seat: PlayerScoreDiffs,
    discard_red_tint_indices_by_seat: dict[int, frozenset[int]],
    player_names_by_seat: PlayerNamesBySeat,
    meld_tiles: Sequence[int],
    dora_indicator_tiles: Sequence[int],
    round_events: Sequence[object] | None,
    round_info_panel: RoundInfoPanelData,
    melds_by_player: SeatMeldMap,
    visible_summary: VisibleTileSummary | None = None,
    self_hand_value_alert: SelfHandValueAlertState | None = None,
    *,
    ui_scale: float = 1.0,
    layout_tuning: LayoutTuningSettings | Mapping[str, object] | None = None,
) -> tuple[float, float, float, float]:
    """プレイヤーパネルと詳細領域を含む卓全体を描画する。"""
    render_phase_timings: list[PhaseTiming] = []
    phase_started_at = time.perf_counter()
    # Full redraws still clear the board, but keep the delete scoped to known live-render tags.
    _delete_canvas_items_by_tags(
        canvas,
        _LIVE_BACKGROUND_TAG,
        _LIVE_FRAME_TAG,
        _LIVE_ASYNC_SIDE_PANEL_TAG,
        _LIVE_ASYNC_DISCARD_TAG,
        _LIVE_DETAIL_OVERLAY_TAG,
        _LIVE_ASYNC_HAND_TAG,
        _HAND_RESPONSE_UI_TAG,
        _LIVE_LAYOUT_DRAG_TAG,
        _THREAD_ACTIVITY_NOTICE_TAG,
    )
    # 動的に生成した PhotoImage の参照も毎回入れ替える。
    _reset_transient_canvas_draw_state(canvas)
    canvas.side_panel_render_cache = None
    _append_phase_timing(render_phase_timings, "clear", phase_started_at)

    # 実ウィンドウサイズと最小サイズの大きい方を採用する。
    phase_started_at = time.perf_counter()
    width, height, board_rect = _canvas_board_rect(canvas)
    canvas.configure(width=width, height=height)

    board_left, board_top, board_right, board_bottom = board_rect

    background_previous_items = _capture_canvas_item_ids(canvas)
    _draw_background(canvas, board_left, board_top, board_right, board_bottom)
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_BACKGROUND_TAG,
        previous_item_ids=background_previous_items,
    )
    # 現在のウィンドウサイズに合わせて各パネル矩形を算出する。
    layout = _build_layout(
        board_left,
        board_top,
        board_right,
        board_bottom,
        img_table,
        ui_scale,
        layout_tuning=layout_tuning,
    )
    canvas.last_render_layout = layout
    canvas.last_render_layout_signature = _build_layout_signature(
        canvas,
        ui_scale=ui_scale,
        layout_tuning=layout_tuning,
    )
    resolved_component_offsets = _normalize_component_offsets(layout.get("resolved_component_offsets", {}))
    canvas.layout_resolved_component_offsets = resolved_component_offsets
    canvas.current_hand_rect = tuple(float(value) for value in layout["hand_rect"])
    _append_phase_timing(render_phase_timings, "layout", phase_started_at)
    # 見えている牌情報を集計し、3見え/4見え表示に使う。
    phase_started_at = time.perf_counter()
    if visible_summary is None:
        visible_summary = collect_visible_tile_summary(
            discard_map,
            hand_tiles,
            meld_tiles,
            dora_indicator_tiles,
        )
    visible_inference_summary, inferred_visible_entries = _build_visible_tile_inference_summary_for_canvas(
        canvas,
        discard_map,
        visible_summary,
        getattr(canvas, "current_round_identity", None),
        discard_red_tint_indices_by_seat,
    )
    if TABLE_SITUATION_ENABLED:
        manual_table_situation_scores_by_seat = _normalize_table_situation_scores_by_seat(
            getattr(canvas, "table_situation_scores_by_seat", {})
        )
        auto_table_situation_scores_by_seat = _build_table_situation_auto_scores_by_seat(
            discard_map,
            discard_red_tint_indices_by_seat,
        )
        resolved_table_situation_scores_by_seat = _resolve_table_situation_scores_by_seat(
            manual_table_situation_scores_by_seat,
            auto_table_situation_scores_by_seat,
        )
    else:
        manual_table_situation_scores_by_seat = {
            int(seat): _empty_table_situation_scores()
            for seat in HAND_DANGER_BAR_SEAT_ORDER
        }
        auto_table_situation_scores_by_seat = {
            int(seat): tuple(0.0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT))
            for seat in HAND_DANGER_BAR_SEAT_ORDER
        }
        resolved_table_situation_scores_by_seat = {
            int(seat): tuple(0.0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT))
            for seat in HAND_DANGER_BAR_SEAT_ORDER
        }
    canvas.table_situation_auto_scores_by_seat = auto_table_situation_scores_by_seat
    canvas.table_situation_resolved_scores_by_seat = resolved_table_situation_scores_by_seat
    _append_phase_timing(render_phase_timings, "summaries", phase_started_at)

    phase_started_at = time.perf_counter()
    _redraw_side_panels_if_needed(
        canvas,
        img_table,
        layout,
        discard_map,
        melds_by_player,
        dora_indicator_tiles,
        visible_summary,
        visible_inference_summary,
        hand_tiles,
        hand_draw_tile,
        hand_danger_percentages,
        opponent_suji_panel_summaries,
        player_push_alert_percentages,
        player_alert_indicators_by_seat,
        player_score_diffs_by_seat,
        player_names_by_seat,
        getattr(canvas, "detail_panel_state", DetailPanelState()),
        force_redraw=True,
    )
    _append_phase_timing(render_phase_timings, "side_panels", phase_started_at)
    phase_started_at = time.perf_counter()
    frame_previous_items = _capture_canvas_item_ids(canvas)
    _draw_center_panel(canvas, layout["center_panel"], dora_indicator_tiles, round_info_panel)
    _draw_meld_zones(canvas, layout)
    _draw_discard_zones(canvas, layout)
    _draw_seat_labels(canvas, layout, round_info_panel)
    _draw_melds(canvas, img_table, melds_by_player, layout)
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_FRAME_TAG,
        previous_item_ids=frame_previous_items,
    )
    _append_phase_timing(render_phase_timings, "table_frame", phase_started_at)
    phase_started_at = time.perf_counter()
    discard_previous_items = _capture_canvas_item_ids(canvas)
    _draw_discards(
        canvas,
        img_table,
        discard_map,
        discard_red_tint_indices_by_seat,
        layout,
        visible_summary,
        push_marker_alert_percentages,
        melds_by_player,
        round_events,
    )
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_ASYNC_DISCARD_TAG,
        previous_item_ids=discard_previous_items,
    )
    _append_phase_timing(render_phase_timings, "discards", phase_started_at)
    phase_started_at = time.perf_counter()
    detail_previous_items = _capture_canvas_item_ids(canvas)
    _draw_table_situation_seat_panels(canvas, layout)
    _draw_inferred_visible_sections(
        canvas,
        layout,
        inferred_visible_entries,
    )
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_DETAIL_OVERLAY_TAG,
        previous_item_ids=detail_previous_items,
    )
    _append_phase_timing(render_phase_timings, "detail_overlays", phase_started_at)
    phase_started_at = time.perf_counter()
    hand_previous_items = _capture_canvas_item_ids(canvas)
    _draw_hand(
        canvas,
        img_table,
        layout["hand_rect"],
        hand_tiles,
        hand_draw_tile,
        dora_indicator_tiles,
        hand_recommendation_panel,
        getattr(canvas, "hand_response_panel_state", HandResponsePanelState()),
        hand_danger_percentages,
        visible_summary,
        (
            self_hand_value_alert
            if self_hand_value_alert is not None
            else SelfHandValueAlertState()
        ),
    )
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_ASYNC_HAND_TAG,
        previous_item_ids=hand_previous_items,
    )
    if getattr(canvas, "layout_drag_enabled", False):
        drag_previous_items = _capture_canvas_item_ids(canvas)
        _draw_layout_drag_overlays(canvas, layout)
        _tag_new_canvas_items(
            canvas,
            tag=_LIVE_LAYOUT_DRAG_TAG,
            previous_item_ids=drag_previous_items,
        )
    _append_phase_timing(render_phase_timings, "hand", phase_started_at)
    canvas.last_render_table_phase_timings = tuple(render_phase_timings)
    canvas.last_render_detail_content_rect = tuple(float(value) for value in layout["detail_content_rect"])
    return layout["detail_content_rect"]


def _draw_background(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> None:
    """卓外背景と卓の外枠を描く。"""
    # まずキャンバス全体の地色を塗る。
    canvas.create_rectangle(0, 0, canvas.winfo_width(), canvas.winfo_height(), fill=BOARD_OUTER, outline="")
    # その上に卓全体のフレームを描く。
    canvas.create_rectangle(
        left - 8,
        top - 8,
        right + 8,
        bottom + 8,
        fill=BOARD_FRAME,
        outline="#111827",
        width=2,
    )
    canvas.create_rectangle(left, top, right, bottom, fill=TABLE_FILL, outline="")
    canvas.create_rectangle(left, top, right, bottom, outline=TABLE_BORDER, width=2)


def _draw_status_bar(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> None:
    """将来のステータスバー表示用の空フック。"""
    return


def _build_layout(
    board_left: float,
    board_top: float,
    board_right: float,
    board_bottom: float,
    img_table: TileImageTable,
    ui_scale: float,
    *,
    layout_tuning: LayoutTuningSettings | Mapping[str, object] | None = None,
) -> dict[str, object]:
    """基準ワイヤーフレームに沿って各領域の矩形を計算する。"""

    # 自家向き牌と横向き牌の実寸を基準に、他の領域サイズを決める。
    tuning = _normalize_layout_tuning_settings(layout_tuning)
    bottom_width, bottom_height = _tile_size(img_table, Player.JICHA)
    side_width, side_height = _tile_size(img_table, Player.SHIMOCHA)
    discard_bottom_width = max(1, int(round(bottom_width * float(tuning.discard_tile_scale))))
    discard_bottom_height = max(1, int(round(bottom_height * float(tuning.discard_tile_scale))))
    discard_side_width = max(1, int(round(side_width * float(tuning.discard_tile_scale))))
    discard_side_height = max(1, int(round(side_height * float(tuning.discard_tile_scale))))
    meld_bottom_height = max(1, int(round(bottom_height * float(tuning.meld_tile_scale))))
    meld_side_height = max(1, int(round(side_height * float(tuning.meld_tile_scale))))
    responsive_mode = ui_scale < 0.999
    if responsive_mode:
        discard_zone_gap = _scaled_length(DISCARD_ZONE_GAP, ui_scale, minimum=12)
        detail_panel_width = _scaled_length(tuning.detail_panel_width, ui_scale, minimum=168)
        detail_panel_gap = _scaled_length(tuning.detail_panel_gap, ui_scale, minimum=12)
        horizontal_panel_width = _scaled_length(tuning.horizontal_panel_width, ui_scale, minimum=380)
        horizontal_panel_height = _scaled_length(
            tuning.horizontal_panel_height,
            max(ui_scale, 0.9),
            minimum=68,
        )
        vertical_panel_width = _scaled_length(tuning.vertical_panel_width, ui_scale, minimum=92)
        vertical_panel_pref_height = _scaled_length(
            tuning.vertical_panel_height,
            max(ui_scale, 0.9),
            minimum=320,
        )
        hand_strip_width = _scaled_length(HAND_STRIP_WIDTH, ui_scale, minimum=320)
        hand_strip_height = _scaled_length(
            HAND_STRIP_HEIGHT,
            max(ui_scale, 0.92),
            minimum=68,
        )
        center_panel_pref_width = _scaled_length(CENTER_PANEL_WIDTH, ui_scale, minimum=128)
        center_panel_pref_height = _scaled_length(
            CENTER_PANEL_HEIGHT,
            max(ui_scale, 0.92),
            minimum=112,
        )
        horizontal_meld_height = _scaled_length(
            tuning.top_bottom_meld_height,
            ui_scale,
            minimum=max(meld_bottom_height, meld_side_height) + 8,
        )
        panel_table_gap = _scaled_length(tuning.panel_table_gap, ui_scale, minimum=0)
        detail_top_margin = _scaled_length(tuning.detail_panel_top, ui_scale, minimum=20)
        detail_edge_margin = _scaled_length(10, ui_scale, minimum=8)
        main_left_margin = _scaled_length(tuning.main_left_margin, ui_scale, minimum=4)
        bottom_margin = _scaled_length(tuning.bottom_panel_margin, ui_scale, minimum=0)
        panel_top_margin = _scaled_length(tuning.side_panels_top, max(ui_scale, 0.92), minimum=40)
        right_panel_right_margin = _scaled_length(tuning.right_panel_margin, ui_scale, minimum=0)
        hand_gap_margin = _scaled_length(tuning.hand_panel_gap, ui_scale, minimum=0)
        hand_bottom_margin = _scaled_length(tuning.hand_bottom_margin, ui_scale, minimum=0)
        top_panel_top_margin = _scaled_length(tuning.top_panel_top, ui_scale, minimum=0)
        center_square_min = _scaled_length(120, ui_scale, minimum=96)
        vertical_panel_bottom_gap = _scaled_length(16, ui_scale, minimum=10)
        center_panel_min = _scaled_length(80, ui_scale, minimum=64)
        top_meld_width = _scaled_length(tuning.top_meld_width, ui_scale, minimum=60)
        bottom_meld_width = _scaled_length(tuning.bottom_meld_width, ui_scale, minimum=60)
        side_meld_width = _scaled_length(tuning.side_meld_width, ui_scale, minimum=48)
        top_bottom_zone_width = _scaled_length(
            tuning.top_bottom_discard_width,
            ui_scale,
            minimum=discard_bottom_width * 6,
        )
        top_bottom_zone_height = _scaled_length(
            tuning.top_bottom_discard_height,
            ui_scale,
            minimum=discard_bottom_height * 3,
        )
        side_zone_width = _scaled_length(
            tuning.side_discard_width,
            ui_scale,
            minimum=discard_side_width * 3,
        )
        side_zone_height = _scaled_length(
            tuning.side_discard_height,
            ui_scale,
            minimum=discard_side_height * 6,
        )
        side_meld_height = min(
            side_zone_height,
            _scaled_length(
                tuning.side_meld_height,
                ui_scale,
                minimum=max(meld_bottom_height, meld_side_height) + 8,
            ),
        )
        self_lower_layout_shift = _scaled_length(SELF_LOWER_LAYOUT_SHIFT, ui_scale, minimum=8)
    else:
        discard_zone_gap = DISCARD_ZONE_GAP
        detail_panel_width = tuning.detail_panel_width
        detail_panel_gap = tuning.detail_panel_gap
        horizontal_panel_width = tuning.horizontal_panel_width
        horizontal_panel_height = tuning.horizontal_panel_height
        vertical_panel_width = tuning.vertical_panel_width
        vertical_panel_pref_height = tuning.vertical_panel_height
        hand_strip_width = HAND_STRIP_WIDTH
        hand_strip_height = HAND_STRIP_HEIGHT
        center_panel_pref_width = CENTER_PANEL_WIDTH
        center_panel_pref_height = CENTER_PANEL_HEIGHT
        horizontal_meld_height = max(tuning.top_bottom_meld_height, max(meld_bottom_height, meld_side_height) + 8)
        panel_table_gap = tuning.panel_table_gap
        detail_top_margin = tuning.detail_panel_top
        detail_edge_margin = 10
        main_left_margin = tuning.main_left_margin
        bottom_margin = tuning.bottom_panel_margin
        panel_top_margin = tuning.side_panels_top
        right_panel_right_margin = tuning.right_panel_margin
        hand_gap_margin = tuning.hand_panel_gap
        hand_bottom_margin = tuning.hand_bottom_margin
        top_panel_top_margin = tuning.top_panel_top
        center_square_min = 120
        vertical_panel_bottom_gap = 16
        center_panel_min = 80
        top_meld_width = tuning.top_meld_width
        bottom_meld_width = tuning.bottom_meld_width
        side_meld_width = tuning.side_meld_width
        top_bottom_zone_width = max(float(tuning.top_bottom_discard_width), float(discard_bottom_width * 6))
        top_bottom_zone_height = max(float(tuning.top_bottom_discard_height), float(discard_bottom_height * 3))
        side_zone_width = max(float(tuning.side_discard_width), float(discard_side_width * 3))
        side_zone_height = max(float(tuning.side_discard_height), float(discard_side_height * 6))
        side_meld_height = min(
            side_zone_height,
            max(float(tuning.side_meld_height), float(max(meld_bottom_height, meld_side_height) + 8)),
        )
        self_lower_layout_shift = float(SELF_LOWER_LAYOUT_SHIFT)

    # 捨て牌エリアは、表示牌画像がちょうど 6 列 x 3 行で収まる大きさに固定する。
    desired_center_square_size = max(top_bottom_zone_width, side_zone_height)

    # 右端の詳細パネル領域を先に確保する。
    detail_left = board_right - detail_panel_width
    detail_rect = (
        detail_left,
        board_top + detail_top_margin,
        board_right - detail_edge_margin,
        board_bottom - detail_edge_margin,
    )

    # メイン卓領域の左右端とパネル基準位置を決める。
    main_right = detail_left - detail_panel_gap
    main_left = board_left + main_left_margin
    bottom_panel_bottom = board_bottom - bottom_margin
    bottom_panel_top = bottom_panel_bottom - horizontal_panel_height
    vertical_panel_top = board_top + panel_top_margin

    # 河・副露帯の基準線はプレイヤーパネル矩形から独立に確保する。
    left_panel_reserved_right = main_left + vertical_panel_width
    right_panel_reserved_left = main_right - right_panel_right_margin - vertical_panel_width
    play_left = left_panel_reserved_right + panel_table_gap
    play_right = right_panel_reserved_left - panel_table_gap
    main_center_x = (play_left + play_right) / 2

    hand_rect = (
        main_center_x - hand_strip_width / 2,
        board_bottom - hand_bottom_margin - hand_strip_height - self_lower_layout_shift,
        main_center_x + hand_strip_width / 2,
        board_bottom - hand_bottom_margin - self_lower_layout_shift,
    )
    top_panel_rect = (
        main_center_x - horizontal_panel_width / 2,
        board_top + top_panel_top_margin,
        main_center_x + horizontal_panel_width / 2,
        board_top + top_panel_top_margin + horizontal_panel_height,
    )
    bottom_panel_rect = (
        main_center_x - horizontal_panel_width / 2,
        bottom_panel_top,
        main_center_x + horizontal_panel_width / 2,
        bottom_panel_bottom,
    )

    # 卓面本体は「上副露帯 -> 上河 -> 中央正方形 -> 下河 -> 下副露帯」の固定順で積む。
    table_top = top_panel_rect[3] + discard_zone_gap
    table_bottom = hand_rect[1] - discard_zone_gap
    center_square_max_from_height = (
        table_bottom
        - table_top
        - discard_zone_gap * 4
        - horizontal_meld_height * 2
        - top_bottom_zone_height * 2
    )
    center_square_max_from_width = (
        play_right
        - play_left
        - discard_zone_gap * 4
        - side_zone_width * 2
        - side_meld_width * 2
    )
    center_square_size = max(
        center_square_min,
        min(desired_center_square_size, center_square_max_from_height, center_square_max_from_width),
    )
    center_table_half_width = max(center_square_size, top_bottom_zone_width) / 2

    top_meld_rect = (
        play_left,
        table_top,
        play_right,
        table_top + horizontal_meld_height,
    )
    top_discard_rect = (
        main_center_x - top_bottom_zone_width / 2,
        top_meld_rect[3] + discard_zone_gap,
        main_center_x + top_bottom_zone_width / 2,
        top_meld_rect[3] + discard_zone_gap + top_bottom_zone_height,
    )
    center_square_rect = (
        main_center_x - center_square_size / 2,
        top_discard_rect[3] + discard_zone_gap,
        main_center_x + center_square_size / 2,
        top_discard_rect[3] + discard_zone_gap + center_square_size,
    )
    bottom_discard_rect = (
        main_center_x - top_bottom_zone_width / 2,
        center_square_rect[3] + discard_zone_gap - self_lower_layout_shift,
        main_center_x + top_bottom_zone_width / 2,
        center_square_rect[3] + discard_zone_gap + top_bottom_zone_height - self_lower_layout_shift,
    )
    bottom_meld_rect = (
        play_left,
        bottom_discard_rect[3] + discard_zone_gap,
        play_right,
        min(
            hand_rect[1] - discard_zone_gap,
            bottom_discard_rect[3] + discard_zone_gap + horizontal_meld_height,
        ),
    )

    # 左右河は 90 度 / 270 度回転前提の固定 3x6 長方形とする。
    left_discard_rect = (
        main_center_x - center_table_half_width - discard_zone_gap - side_zone_width,
        top_discard_rect[1],
        main_center_x - center_table_half_width - discard_zone_gap,
        top_discard_rect[1] + side_zone_height,
    )
    right_discard_rect = (
        main_center_x + center_table_half_width + discard_zone_gap,
        top_discard_rect[1],
        main_center_x + center_table_half_width + discard_zone_gap + side_zone_width,
        top_discard_rect[1] + side_zone_height,
    )

    # 左右プレイヤーパネルの高さだけ先に確定し、横位置は卓面確定後に詰めて決める。
    reserved_hand_top = hand_rect[1] - hand_gap_margin
    vertical_panel_bottom = reserved_hand_top - vertical_panel_bottom_gap
    available_vertical_panel_height = max(vertical_panel_bottom - vertical_panel_top, 0)
    if available_vertical_panel_height <= 0:
        vertical_panel_height = 0
    elif available_vertical_panel_height < 240:
        vertical_panel_height = available_vertical_panel_height
    else:
        vertical_panel_height = min(available_vertical_panel_height, vertical_panel_pref_height)

    # 捨て牌エリア内側の空き領域に中央情報パネルを入れる。
    info_area_left = left_panel_reserved_right + discard_zone_gap
    info_area_top = top_panel_rect[3] + discard_zone_gap
    info_area_right = top_discard_rect[0] - discard_zone_gap
    info_area_bottom = center_square_rect[1] - discard_zone_gap
    center_panel_width = min(center_panel_pref_width, max(info_area_right - info_area_left, center_panel_min))
    center_panel_height = min(center_panel_pref_height, max(info_area_bottom - info_area_top, center_panel_min))
    center_panel_left = info_area_left
    center_panel_top = info_area_top
    center_panel_rect = (
        center_panel_left,
        center_panel_top,
        center_panel_left + center_panel_width,
        center_panel_top + center_panel_height,
    )
    top_meld_left = max(play_left, center_panel_rect[2] + discard_zone_gap)
    top_meld_available_width = max(play_right - top_meld_left, 0)
    resolved_top_meld_width = max(0.0, min(float(top_meld_width), top_meld_available_width))
    top_meld_rect = (
        top_meld_left,
        top_meld_rect[1],
        top_meld_left + resolved_top_meld_width,
        top_meld_rect[3],
    )
    bottom_meld_available_width = max(play_right - play_left, 0)
    resolved_bottom_meld_width = max(0.0, min(float(bottom_meld_width), bottom_meld_available_width))
    bottom_meld_rect = (
        play_right - resolved_bottom_meld_width,
        bottom_meld_rect[1],
        play_right,
        bottom_meld_rect[3],
    )
    side_meld_top = left_discard_rect[1] + max((side_zone_height - side_meld_height) / 2, 0)
    left_meld_rect = (
        left_discard_rect[0] - discard_zone_gap - side_meld_width,
        side_meld_top,
        left_discard_rect[0] - discard_zone_gap,
        side_meld_top + side_meld_height,
    )
    right_meld_rect = (
        right_discard_rect[2] + discard_zone_gap,
        side_meld_top,
        right_discard_rect[2] + discard_zone_gap + side_meld_width,
        side_meld_top + side_meld_height,
    )

    table_left_edge = min(
        top_meld_rect[0],
        left_meld_rect[0],
        bottom_meld_rect[0],
        left_discard_rect[0],
    )
    table_right_edge = max(
        top_meld_rect[2],
        right_meld_rect[2],
        bottom_meld_rect[2],
        right_discard_rect[2],
    )
    left_panel_right = max(main_left, min(left_panel_reserved_right, table_left_edge - panel_table_gap))
    right_panel_right = main_right - right_panel_right_margin
    right_panel_left = min(
        right_panel_right,
        max(right_panel_reserved_left, table_right_edge + panel_table_gap),
    )
    left_panel_rect = (
        main_left,
        vertical_panel_top,
        left_panel_right,
        vertical_panel_top + vertical_panel_height,
    )
    right_panel_rect = (
        right_panel_left,
        vertical_panel_top,
        right_panel_right,
        vertical_panel_top + vertical_panel_height,
    )

    # 詳細パネルは上から 3見え / 4見え / その下の詳細本体に分割する。
    detail_height = detail_rect[3] - detail_rect[1]
    visible3_rect = (detail_rect[0], detail_rect[1], detail_rect[2], detail_rect[1] + detail_height * 0.27)
    visible4_rect = (detail_rect[0], visible3_rect[3], detail_rect[2], visible3_rect[3] + detail_height * 0.27)
    detail_content_rect = (detail_rect[0], visible4_rect[3], detail_rect[2], detail_rect[3])

    base_component_rects = {
        "player_toimen": top_panel_rect,
        "player_kamicha": left_panel_rect,
        "player_shimocha": right_panel_rect,
        "discard_toimen": top_discard_rect,
        "discard_kamicha": left_discard_rect,
        "discard_shimocha": right_discard_rect,
        "discard_jicha": bottom_discard_rect,
        "meld_toimen": top_meld_rect,
        "meld_kamicha": left_meld_rect,
        "meld_shimocha": right_meld_rect,
        "meld_jicha": bottom_meld_rect,
    }
    resolved_component_rects, resolved_component_offsets = _resolve_layout_component_rects(
        base_component_rects,
        tuning.component_offsets,
        (board_left, board_top, board_right, board_bottom),
        (
            detail_rect,
            center_panel_rect,
            hand_rect,
            bottom_panel_rect,
        ),
    )
    top_panel_rect = resolved_component_rects.get("player_toimen", top_panel_rect)
    left_panel_rect = resolved_component_rects.get("player_kamicha", left_panel_rect)
    right_panel_rect = resolved_component_rects.get("player_shimocha", right_panel_rect)
    top_discard_rect = resolved_component_rects.get("discard_toimen", top_discard_rect)
    left_discard_rect = resolved_component_rects.get("discard_kamicha", left_discard_rect)
    right_discard_rect = resolved_component_rects.get("discard_shimocha", right_discard_rect)
    bottom_discard_rect = resolved_component_rects.get("discard_jicha", bottom_discard_rect)
    top_meld_rect = resolved_component_rects.get("meld_toimen", top_meld_rect)
    left_meld_rect = resolved_component_rects.get("meld_kamicha", left_meld_rect)
    right_meld_rect = resolved_component_rects.get("meld_shimocha", right_meld_rect)
    bottom_meld_rect = resolved_component_rects.get("meld_jicha", bottom_meld_rect)

    top_inference_rect = (
        max(top_panel_rect[0], top_meld_rect[0]),
        top_panel_rect[3] + 6,
        min(top_panel_rect[2], top_meld_rect[2]),
        top_meld_rect[1] - 6,
    )
    left_inference_rect = (
        left_panel_rect[2] + 6,
        max(left_panel_rect[1], left_meld_rect[1]),
        left_meld_rect[0] - 6,
        min(left_panel_rect[3], left_meld_rect[3]),
    )
    right_inference_rect = (
        right_meld_rect[2] + 6,
        max(right_panel_rect[1], right_meld_rect[1]),
        right_panel_rect[0] - 6,
        min(right_panel_rect[3], right_meld_rect[3]),
    )
    self_inference_right = min(hand_rect[0], bottom_discard_rect[0]) - 8
    self_inference_rect = (
        max(board_left + 12, self_inference_right - 220),
        max(bottom_discard_rect[1], hand_rect[1] - 10),
        self_inference_right,
        min(board_bottom - 12, hand_rect[3]),
    )

    # 以降の描画が参照しやすいよう、矩形群を辞書で返す。
    return {
        "detail_rect": detail_rect,
        "visible3_rect": visible3_rect,
        "visible4_rect": visible4_rect,
        "detail_content_rect": detail_content_rect,
        "self_inference_rect": self_inference_rect,
        "center_square": center_square_rect,
        "top_panel": top_panel_rect,
        "bottom_panel": bottom_panel_rect,
        "left_panel": left_panel_rect,
        "right_panel": right_panel_rect,
        "center_panel": center_panel_rect,
        "hand_rect": hand_rect,
        "meld_rects": {
            Player.TOIMEN: top_meld_rect,
            Player.KAMICHA: left_meld_rect,
            Player.SHIMOCHA: right_meld_rect,
            Player.JICHA: bottom_meld_rect,
        },
        "player_inference_rects": {
            int(Player.TOIMEN): top_inference_rect,
            int(Player.KAMICHA): left_inference_rect,
            int(Player.SHIMOCHA): right_inference_rect,
        },
        "discard_rects": {
            Player.TOIMEN: top_discard_rect,
            Player.KAMICHA: left_discard_rect,
            Player.SHIMOCHA: right_discard_rect,
            Player.JICHA: bottom_discard_rect,
        },
        "drag_components": resolved_component_rects,
        "resolved_component_offsets": resolved_component_offsets,
    }


def _build_side_panel_render_signature(
    canvas: tkinter.Canvas,
    *,
    layout: Mapping[str, object],
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]],
    dora_indicator_tiles: Sequence[int],
    visible_summary: VisibleTileSummary,
    visible_inference_summary: VisibleTileInferenceSummary,
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    opponent_suji_panel_summaries: OpponentSujiPanelSummaries,
    player_push_alert_percentages: PlayerPushAlertPercentages,
    player_alert_indicators_by_seat: PlayerAlertIndicatorsBySeat,
    player_score_diffs_by_seat: PlayerScoreDiffs,
    player_names_by_seat: PlayerNamesBySeat,
    detail_panel_state: DetailPanelState,
) -> object:
    """Return a stable signature for the whole tagged side-panel region."""

    layout_subset = {
        key: layout.get(key)
        for key in (
            "top_panel",
            "left_panel",
            "right_panel",
            "detail_rect",
            "visible3_rect",
            "visible4_rect",
            "detail_content_rect",
            "discard_rects",
        )
    }
    memo_presence = tuple(
        (
            int(seat),
            str(player_name),
            bool(_player_has_saved_memo(canvas, str(player_name))),
        )
        for seat, player_name in sorted(player_names_by_seat.items())
    )
    public_honor_tiles = tuple(
        int(tile_id)
        for tile_id in _public_honor_tiles_below_three_visible(
            discard_map,
            melds_by_player,
            dora_indicator_tiles,
        )
    )
    discarded_public_honor_tiles = _self_discarded_public_honor_tiles(
        discard_map,
        public_honor_tiles,
    )
    payload = {
        "layout": layout_subset,
        "ui_scale": float(getattr(canvas, "current_ui_scale", 1.0)),
        "lag_marker_reference_kind": _normalize_lag_marker_reference_kind(
            getattr(canvas, "lag_marker_reference_kind", LAG_MARKER_REFERENCE_KIND_BLUE)
        ),
        "detail_panel_state": detail_panel_state,
        "memo_presence": memo_presence,
        "player_names_by_seat": player_names_by_seat,
        "player_score_diffs_by_seat": player_score_diffs_by_seat,
        "opponent_suji_panel_summaries": opponent_suji_panel_summaries,
        "player_push_alert_percentages": player_push_alert_percentages,
        "player_alert_indicators_by_seat": player_alert_indicators_by_seat,
        "hand_tiles": tuple(int(tile_id) for tile_id in hand_tiles),
        "hand_draw_tile": int(hand_draw_tile) if hand_draw_tile is not None else None,
        "hand_danger_percentages": tuple(hand_danger_percentages),
        "visible_summary": visible_summary,
        "visible_inference_summary": visible_inference_summary,
        "public_honor_tiles": public_honor_tiles,
        "discarded_public_honor_tiles": discarded_public_honor_tiles,
    }
    return _stable_render_signature(payload)


def _restore_side_panel_render_cache(canvas: tkinter.Canvas) -> bool:
    """Restore click specs/image references when a cached side-panel tag is reused unchanged."""

    cache = getattr(canvas, "side_panel_render_cache", None)
    if not isinstance(cache, SidePanelRenderCache):
        return False
    canvas.player_panel_button_specs = list(cache.player_panel_button_specs)
    canvas.lag_marker_reference_button_specs = list(cache.lag_marker_reference_button_specs)
    canvas.detail_images = list(cache.detail_images)
    return True


def _remember_side_panel_render_cache(
    canvas: tkinter.Canvas,
    *,
    signature: object,
) -> None:
    """Capture the side-panel transient state so redraws can skip rebuilding it when unchanged."""

    canvas.side_panel_render_cache = SidePanelRenderCache(
        signature=signature,
        player_panel_button_specs=tuple(getattr(canvas, "player_panel_button_specs", ())),
        lag_marker_reference_button_specs=tuple(
            getattr(canvas, "lag_marker_reference_button_specs", ())
        ),
        detail_images=tuple(getattr(canvas, "detail_images", ())),
    )


def _redraw_side_panels_if_needed(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    layout: dict[str, object],
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]],
    dora_indicator_tiles: Sequence[int],
    visible_summary: VisibleTileSummary,
    visible_inference_summary: VisibleTileInferenceSummary,
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    opponent_suji_panel_summaries: OpponentSujiPanelSummaries,
    player_push_alert_percentages: PlayerPushAlertPercentages,
    player_alert_indicators_by_seat: PlayerAlertIndicatorsBySeat,
    player_score_diffs_by_seat: PlayerScoreDiffs,
    player_names_by_seat: PlayerNamesBySeat,
    detail_panel_state: DetailPanelState,
    *,
    force_redraw: bool = False,
) -> bool:
    """Redraw the tagged side-panel region only when its render inputs changed."""

    signature = _build_side_panel_render_signature(
        canvas,
        layout=layout,
        discard_map=discard_map,
        melds_by_player=melds_by_player,
        dora_indicator_tiles=dora_indicator_tiles,
        visible_summary=visible_summary,
        visible_inference_summary=visible_inference_summary,
        hand_tiles=hand_tiles,
        hand_draw_tile=hand_draw_tile,
        hand_danger_percentages=hand_danger_percentages,
        opponent_suji_panel_summaries=opponent_suji_panel_summaries,
        player_push_alert_percentages=player_push_alert_percentages,
        player_alert_indicators_by_seat=player_alert_indicators_by_seat,
        player_score_diffs_by_seat=player_score_diffs_by_seat,
        player_names_by_seat=player_names_by_seat,
        detail_panel_state=detail_panel_state,
    )
    cache = getattr(canvas, "side_panel_render_cache", None)
    if (
        not force_redraw
        and isinstance(cache, SidePanelRenderCache)
        and cache.signature == signature
        and _restore_side_panel_render_cache(canvas)
    ):
        return False

    canvas.player_panel_button_specs = []
    canvas.lag_marker_reference_button_specs = []
    canvas.detail_images = []
    _delete_canvas_items_by_tags(canvas, _LIVE_ASYNC_SIDE_PANEL_TAG)
    side_panel_previous_items = _capture_canvas_item_ids(canvas)
    _draw_side_panels(
        canvas,
        img_table,
        layout,
        discard_map,
        melds_by_player,
        dora_indicator_tiles,
        visible_summary,
        visible_inference_summary,
        hand_tiles,
        hand_draw_tile,
        hand_danger_percentages,
        opponent_suji_panel_summaries,
        player_push_alert_percentages,
        player_alert_indicators_by_seat,
        player_score_diffs_by_seat,
        player_names_by_seat,
        detail_panel_state,
    )
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_ASYNC_SIDE_PANEL_TAG,
        previous_item_ids=side_panel_previous_items,
    )
    _remember_side_panel_render_cache(canvas, signature=signature)
    return True


def _draw_side_panels(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    layout: dict[str, object],
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]],
    dora_indicator_tiles: Sequence[int],
    visible_summary: VisibleTileSummary,
    visible_inference_summary: VisibleTileInferenceSummary,
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    opponent_suji_panel_summaries: OpponentSujiPanelSummaries,
    player_push_alert_percentages: PlayerPushAlertPercentages,
    player_alert_indicators_by_seat: PlayerAlertIndicatorsBySeat,
    player_score_diffs_by_seat: PlayerScoreDiffs,
    player_names_by_seat: PlayerNamesBySeat,
    detail_panel_state: DetailPanelState,
) -> None:
    """Draw per-player panels plus the shared detail display space."""
    # プレイヤーパネルと詳細パネル共通のUI色。
    panel_fill = "#121923"
    panel_outline = "#243244"
    button_fill = "#1c2735"
    button_outline = "#3a4c63"
    button_text = "#d7deea"
    text_muted = "#9fb0c6"

    # 各パネル矩形を取り出す。
    top_panel = layout["top_panel"]
    left_panel = layout["left_panel"]
    right_panel = layout["right_panel"]
    detail_panel = layout["detail_rect"]
    discard_rects = layout.get("discard_rects", {})
    public_honor_tiles = _public_honor_tiles_below_three_visible(
        discard_map,
        melds_by_player,
        dora_indicator_tiles,
    )
    discarded_public_honor_tiles = _self_discarded_public_honor_tiles(
        discard_map,
        public_honor_tiles,
    )

    # まず全パネルの外枠を描く。
    for x0, y0, x1, y1 in (top_panel, left_panel, right_panel, detail_panel):
        if x1 <= x0 or y1 <= y0:
            continue
        canvas.create_rectangle(x0, y0, x1, y1, fill=panel_fill, outline=panel_outline, width=1)

    # 各座席パネルを個別に描く。
    if left_panel[2] > left_panel[0] and left_panel[3] > left_panel[1]:
        _draw_player_panel(
            canvas,
            seat=int(Player.KAMICHA),
            panel=left_panel,
            player_name=str(player_names_by_seat.get(int(Player.KAMICHA), "")),
            summary_data=opponent_suji_panel_summaries.get(int(Player.KAMICHA), {}),
            hand_tiles=hand_tiles,
            hand_draw_tile=hand_draw_tile,
            hand_danger_percentages=hand_danger_percentages,
            push_alert_data=player_push_alert_percentages.get(int(Player.KAMICHA), {}),
            alert_indicators=player_alert_indicators_by_seat.get(int(Player.KAMICHA), ()),
            score_diff=player_score_diffs_by_seat.get(int(Player.KAMICHA), 0),
            button_fill=button_fill,
            button_outline=button_outline,
            button_text=button_text,
            text_muted=text_muted,
            detail_panel_state=detail_panel_state,
            public_honor_tiles=(),
        )
    if right_panel[2] > right_panel[0] and right_panel[3] > right_panel[1]:
        _draw_player_panel(
            canvas,
            seat=int(Player.SHIMOCHA),
            panel=right_panel,
            player_name=str(player_names_by_seat.get(int(Player.SHIMOCHA), "")),
            summary_data=opponent_suji_panel_summaries.get(int(Player.SHIMOCHA), {}),
            hand_tiles=hand_tiles,
            hand_draw_tile=hand_draw_tile,
            hand_danger_percentages=hand_danger_percentages,
            push_alert_data=player_push_alert_percentages.get(int(Player.SHIMOCHA), {}),
            alert_indicators=player_alert_indicators_by_seat.get(int(Player.SHIMOCHA), ()),
            score_diff=player_score_diffs_by_seat.get(int(Player.SHIMOCHA), 0),
            button_fill=button_fill,
            button_outline=button_outline,
            button_text=button_text,
            text_muted=text_muted,
            detail_panel_state=detail_panel_state,
            public_honor_tiles=(),
        )
    if top_panel[2] > top_panel[0] and top_panel[3] > top_panel[1]:
        _draw_player_panel(
            canvas,
            seat=int(Player.TOIMEN),
            panel=top_panel,
            player_name=str(player_names_by_seat.get(int(Player.TOIMEN), "")),
            summary_data=opponent_suji_panel_summaries.get(int(Player.TOIMEN), {}),
            hand_tiles=hand_tiles,
            hand_draw_tile=hand_draw_tile,
            hand_danger_percentages=hand_danger_percentages,
            push_alert_data=player_push_alert_percentages.get(int(Player.TOIMEN), {}),
            alert_indicators=player_alert_indicators_by_seat.get(int(Player.TOIMEN), ()),
            score_diff=player_score_diffs_by_seat.get(int(Player.TOIMEN), 0),
            button_fill=button_fill,
            button_outline=button_outline,
            button_text=button_text,
            text_muted=text_muted,
            detail_panel_state=detail_panel_state,
            horizontal=True,
            public_honor_tiles=(),
        )
    if public_honor_tiles and isinstance(discard_rects, Mapping):
        self_discard_rect = discard_rects.get(Player.JICHA)
        if isinstance(self_discard_rect, tuple) and len(self_discard_rect) == 4:
            shortlist_height = _public_honor_shortlist_section_height(
                canvas,
                max_rows=PLAYER_PANEL_PUBLIC_HONOR_MAX_ROWS,
            )
            shortlist_left = float(self_discard_rect[2]) + 8.0
            shortlist_right_limit = float(right_panel[0]) - 8.0
            shortlist_width = shortlist_right_limit - shortlist_left
            # 自家の 2見え以下字牌は、副露帯との往復確認が多いので少しだけ下へ寄せる。
            shortlist_top = _resolve_public_honor_shortlist_top(
                self_discard_rect,
                shortlist_height,
            )
            if shortlist_width >= 24.0 and float(self_discard_rect[3]) - float(self_discard_rect[1]) >= shortlist_height:
                _draw_public_honor_shortlist(
                    canvas,
                    shortlist_left,
                    shortlist_top,
                    public_honor_tiles,
                    text_muted,
                    max_text_width=shortlist_width,
                    max_rows=PLAYER_PANEL_PUBLIC_HONOR_MAX_ROWS,
                    dim_tile_ids=discarded_public_honor_tiles,
                )
    # 右の詳細パネルには見え牌表示を描く。
    _draw_detail_toggle_group(
        canvas,
        img_table,
        layout,
        visible_summary,
        visible_inference_summary,
        button_fill,
        button_outline,
        button_text,
        text_muted,
        player_names_by_seat,
        detail_panel_state,
    )


def _draw_detail_button(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    right: float,
    bottom: float,
    fill: str,
    outline: str,
    text_color: str,
) -> None:
    """詳細ボタンの矩形だけを描く最小ヘルパー。"""
    canvas.create_rectangle(left, top, right, bottom, fill=fill, outline=outline, width=1)


def _draw_player_panel(
    canvas: tkinter.Canvas,
    seat: int,
    panel: tuple[float, float, float, float],
    player_name: str,
    summary_data: Mapping[str, object],
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    push_alert_data: Mapping[str, object],
    alert_indicators: Sequence[PlayerAlertIndicator] | None,
    score_diff: int,
    button_fill: str,
    button_outline: str,
    button_text: str,
    text_muted: str,
    detail_panel_state: DetailPanelState,
    public_honor_tiles: Sequence[int] = (),
    horizontal: bool = False,
) -> None:
    """Draw a seat-specific alert panel with a detail button."""
    summary, alert, score, buttons = _resolve_player_panel_sections(canvas, panel, horizontal=horizontal)

    # 枠と内容をセクション単位に描く。
    _draw_panel_section(canvas, summary, "SUMMARY", button_outline, text_muted, button_text)
    _draw_panel_section(canvas, alert, "ALERT", button_outline, text_muted, button_text)
    _draw_panel_section(canvas, score, "SCORE", button_outline, text_muted, button_text)
    _draw_panel_section(canvas, buttons, "BUTTONS", button_outline, text_muted, button_text)
    _draw_summary_content(
        canvas,
        seat,
        summary,
        player_name,
        summary_data,
        hand_tiles,
        hand_draw_tile,
        hand_danger_percentages,
        text_muted,
        horizontal,
        public_honor_tiles,
    )
    _draw_alert_content(
        canvas,
        alert,
        (
            tuple(alert_indicators)
            if alert_indicators is not None
            else _build_player_alert_indicators(summary_data, push_alert_data, seat=seat)
        ),
        text_muted,
    )
    _draw_score_content(
        canvas,
        score,
        seat,
        score_diff,
        button_fill,
        button_outline,
        button_text,
        text_muted,
        detail_panel_state,
    )
    _draw_button_group(
        canvas,
        buttons,
        seat,
        player_name,
        button_fill,
        button_outline,
        button_text,
        horizontal,
        detail_panel_state,
    )


def _required_button_section_height(horizontal: bool) -> int:
    """Return the section height needed to keep the full player-button stack visible."""

    button_count = len(PLAYER_PANEL_BUTTON_LABELS)
    if button_count <= 0:
        return 0
    if horizontal:
        return (
            PLAYER_PANEL_HORIZONTAL_BUTTON_TOP_MARGIN
            + button_count * PLAYER_PANEL_HORIZONTAL_BUTTON_HEIGHT
            + max(0, button_count - 1) * PLAYER_PANEL_HORIZONTAL_BUTTON_GAP
            + PLAYER_PANEL_HORIZONTAL_BUTTON_BOTTOM_MARGIN
        )
    return (
        PLAYER_PANEL_VERTICAL_BUTTON_TOP_MARGIN
        + button_count * PLAYER_PANEL_VERTICAL_BUTTON_HEIGHT
        + max(0, button_count - 1) * PLAYER_PANEL_VERTICAL_BUTTON_GAP
        + PLAYER_PANEL_VERTICAL_BUTTON_BOTTOM_MARGIN
    )


def _resolve_player_panel_sections(
    canvas: tkinter.Canvas,
    panel: tuple[float, float, float, float],
    *,
    horizontal: bool,
) -> tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]:
    """Resolve summary/alert/score/buttons rects while reserving enough space."""

    left, top, right, bottom = panel
    tuning = _current_layout_tuning(canvas)
    inset = PLAYER_PANEL_SECTION_MARGIN
    gap = PLAYER_PANEL_SECTION_GAP
    if horizontal:
        score_width = min(
            PLAYER_PANEL_HORIZONTAL_SCORE_WIDTH,
            max((right - left) * 0.15, 64.0),
        )
        button_left = max(
            right - inset - 70.0,
            left + (right - left) * tuning.top_alert_ratio + gap + score_width + gap,
        )
        summary = (
            left + inset,
            top + inset,
            left + (right - left) * tuning.top_summary_ratio - 4,
            bottom - inset,
        )
        alert = (
            summary[2] + gap,
            top + inset,
            min(
                left + (right - left) * tuning.top_alert_ratio - 4,
                button_left - gap - score_width - gap,
            ),
            bottom - inset,
        )
        score = (
            alert[2] + gap,
            top + inset,
            max(alert[2] + gap + score_width, button_left - gap),
            bottom - inset,
        )
        buttons = (score[2] + gap, top + inset, right - inset, bottom - inset)
        return summary, alert, score, buttons

    section_left = left + inset
    section_right = right - inset
    section_top = top + inset
    section_bottom = bottom - inset
    raw_summary_bottom = top + (bottom - top) * tuning.side_summary_ratio - 4
    raw_alert_bottom = top + (bottom - top) * tuning.side_alert_ratio - 4
    max_score_bottom = section_bottom - _required_button_section_height(horizontal=False) - gap
    max_alert_bottom = max_score_bottom - gap - PLAYER_PANEL_VERTICAL_SCORE_MIN_HEIGHT
    max_summary_bottom = max(
        section_top + 40,
        max_alert_bottom - gap - PLAYER_PANEL_VERTICAL_ALERT_MIN_HEIGHT,
    )
    summary_bottom = min(
        max(raw_summary_bottom, section_top + PLAYER_PANEL_VERTICAL_SUMMARY_MIN_HEIGHT),
        max_summary_bottom,
    )
    min_alert_bottom = summary_bottom + gap + PLAYER_PANEL_VERTICAL_ALERT_MIN_HEIGHT
    alert_bottom = min(max(raw_alert_bottom, min_alert_bottom), max_alert_bottom)
    score_bottom = min(
        max(
            alert_bottom + gap + PLAYER_PANEL_VERTICAL_SCORE_MIN_HEIGHT,
            alert_bottom + gap + 56,
        ),
        max_score_bottom,
    )
    summary = (
        section_left,
        section_top,
        section_right,
        summary_bottom,
    )
    alert = (
        section_left,
        summary_bottom + gap,
        section_right,
        alert_bottom,
    )
    score = (
        section_left,
        alert_bottom + gap,
        section_right,
        score_bottom,
    )
    buttons = (
        section_left,
        score_bottom + gap,
        section_right,
        section_bottom,
    )
    return summary, alert, score, buttons


def _draw_panel_section(
    canvas: tkinter.Canvas,
    rect: tuple[float, float, float, float],
    label: str,
    outline: str,
    text_muted: str,
    heading: str,
) -> None:
    """パネル内の小セクション枠と見出しを描く。"""
    left, top, right, bottom = rect
    canvas.create_rectangle(left, top, right, bottom, outline=outline, width=1)
    canvas.create_text(
        left + 6,
        top + 6,
        text=label,
        anchor=tkinter.NW,
        fill=text_muted,
        font=("Consolas", 8, "bold"),
    )


def _tile_rank_label_to_tile_37(tile_text: str) -> int | None:
    """Convert one `1m` / `7z` style label into the logical 37-kind tile id used by the UI."""

    normalized = str(tile_text).strip()
    if len(normalized) < 2:
        return None
    suit = normalized[-1]
    number_text = normalized[:-1]
    try:
        suit_number = int(number_text)
    except (TypeError, ValueError):
        return None
    if suit == "m" and 1 <= suit_number <= 9:
        return suit_number
    if suit == "p" and 1 <= suit_number <= 9:
        return 9 + suit_number
    if suit == "s" and 1 <= suit_number <= 9:
        return 18 + suit_number
    if suit == "z" and 1 <= suit_number <= 7:
        return 27 + suit_number
    return None


def _parse_tile_rank_label(tile_rank_label: str) -> tuple[str, tuple[int, ...], str] | None:
    """Parse `1. 6s 5p 25.8%` into rank text, tile ids, and trailing percent text."""

    normalized = str(tile_rank_label).strip()
    rank_text, separator, rest = normalized.partition(". ")
    if not separator or not rest:
        return None
    parts = rest.split()
    if len(parts) < 2:
        return None
    percent_text = parts[-1]
    tile_ids: list[int] = []
    for tile_text in parts[:-1]:
        tile_37 = _tile_rank_label_to_tile_37(tile_text)
        if tile_37 is None:
            return None
        tile_ids.append(tile_37)
    if not tile_ids:
        return None
    return rank_text + ".", tuple(tile_ids[:5]), percent_text


def _player_panel_tile_rank_image(
    canvas: tkinter.Canvas,
    tile_37: int,
    *,
    dimmed: bool = False,
) -> tkinter.PhotoImage | None:
    """Return one very small upright tile image for player-panel tile rankings."""

    if not (1 <= tile_37 <= N_TILES):
        return None
    tuning = _current_layout_tuning(canvas)
    tile_scale = max(
        0.16,
        min(0.4, getattr(canvas, "current_ui_scale", 1.0) * tuning.panel_tile_rank_scale),
    )
    cache_key = (tile_37, round(tile_scale, 3), bool(dimmed))
    cache: dict[tuple[int, float, bool], tkinter.PhotoImage] = getattr(
        canvas,
        "player_panel_tile_rank_image_cache",
        {},
    )
    cached_image = cache.get(cache_key)
    if cached_image is not None:
        return cached_image

    if dimmed:
        compact_image = build_tile_photoimage(
            canvas,
            tile_37,
            Player.JICHA,
            DrawType.TEDASHI,
            overlay_bands=PLAYER_PANEL_PUBLIC_HONOR_DIM_OVERLAY_BANDS,
            tile_scale=tile_scale,
        )
    else:
        compact_image = build_tile_photoimage(
            canvas,
            tile_37,
            Player.JICHA,
            DrawType.TEDASHI,
            tile_scale=tile_scale,
        )
    cache[cache_key] = compact_image
    canvas.player_panel_tile_rank_image_cache = cache
    return compact_image


def _player_panel_tile_rank_row_pitch(
    canvas: tkinter.Canvas,
    configured_gap: float,
) -> float:
    """Tile-rank rows reserve one tile height plus any extra gap from LAYOUT."""

    tile_image = _player_panel_tile_rank_image(canvas, 1)
    tile_height = float(tile_image.height()) if tile_image is not None else 0.0
    return tile_height + max(0.0, float(configured_gap))


def _player_panel_line_row_pitch(canvas: tkinter.Canvas) -> float:
    """Return the text-only row pitch used by compact player-panel `Line` rows."""

    line_font = tkfont.Font(root=canvas, font=PLAYER_PANEL_SUMMARY_LINE_FONT)
    return max(10.0, float(line_font.metrics("linespace")) + PLAYER_PANEL_SUMMARY_LINE_ROW_GAP)


def _draw_tile_rank_row(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    tile_rank_label: str,
    text_muted: str,
    *,
    max_text_width: float,
) -> None:
    """Draw one player-panel tile-rank row as `rank + small tile images + percent`."""

    parsed = _parse_tile_rank_label(tile_rank_label)
    if parsed is None:
        fitted_rank_text = _fit_text_to_width(
            canvas,
            tile_rank_label,
            PLAYER_PANEL_SUMMARY_TINY_FONT,
            max_text_width,
        )
        canvas.create_text(
            left,
            top,
            text=fitted_rank_text,
            anchor=tkinter.NW,
            fill=text_muted,
            font=PLAYER_PANEL_SUMMARY_TINY_FONT,
        )
        return

    rank_text, tile_ids, percent_text = parsed
    canvas.create_text(
        left,
        top,
        text=rank_text,
        anchor=tkinter.NW,
        fill=text_muted,
        font=PLAYER_PANEL_SUMMARY_TINY_FONT,
    )
    current_x = left + 12
    for tile_37 in tile_ids:
        tile_image = _player_panel_tile_rank_image(canvas, tile_37)
        if tile_image is None:
            continue
        canvas.create_image(current_x, top + 1, image=tile_image, anchor=tkinter.NW)
        current_x += tile_image.width() + PLAYER_PANEL_TILE_RANK_TILE_GAP
    canvas.create_text(
        min(current_x + 3, left + max_text_width),
        top,
        text=percent_text,
        anchor=tkinter.NW,
        fill=text_muted,
        font=PLAYER_PANEL_SUMMARY_TINY_FONT,
    )


def _public_honor_tiles_below_three_visible(
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]],
    dora_indicator_tiles: Sequence[int],
) -> tuple[int, ...]:
    """Return honor tiles with fewer than three public copies in discards+melds+dora."""

    public_counts = [0] * 34
    for discards in discard_map.values():
        for discard in discards:
            if bool(getattr(discard, "called", False)):
                continue
            tile_37 = getattr(discard, "tile_id", getattr(discard, "tile_37", None))
            tile_34_index = tile37_to_tile34_index(tile_37)
            if tile_34_index is None or not 27 <= tile_34_index <= 33:
                continue
            public_counts[tile_34_index] += 1
    for melds in melds_by_player.values():
        for meld in melds:
            meld_tile_ids = tuple(int(tile_id) for tile_id in getattr(meld, "tiles_37", ()) if tile_id is not None)
            if not meld_tile_ids:
                representative_tile = getattr(meld, "tile_37", None)
                if representative_tile is not None:
                    meld_tile_ids = (int(representative_tile),)
            for tile_id in meld_tile_ids:
                tile_34_index = tile37_to_tile34_index(tile_id)
                if tile_34_index is None or not 27 <= tile_34_index <= 33:
                    continue
                public_counts[tile_34_index] += 1
    for tile_id in dora_indicator_tiles:
        tile_34_index = tile37_to_tile34_index(tile_id)
        if tile_34_index is None or not 27 <= tile_34_index <= 33:
            continue
        public_counts[tile_34_index] += 1

    return tuple(
        tile_34_index + 4
        for tile_34_index in range(27, 34)
        if public_counts[tile_34_index] < 3
    )


def _self_discarded_public_honor_tiles(
    discard_map: Mapping[Player, Iterable[Discard]],
    public_honor_tiles: Sequence[int],
) -> tuple[int, ...]:
    """Return shortlist honor tiles that already appear in any discard history."""

    shortlist_tile_ids = {int(tile_id) for tile_id in public_honor_tiles}
    if not shortlist_tile_ids:
        return ()
    discarded_tile_ids: set[int] = set()
    for discards in discard_map.values():
        for discard in discards:
            tile_37 = getattr(discard, "tile_id", getattr(discard, "tile_37", None))
            if tile_37 is None:
                continue
            try:
                normalized_tile_37 = int(tile_37)
            except (TypeError, ValueError):
                continue
            if normalized_tile_37 in shortlist_tile_ids:
                discarded_tile_ids.add(normalized_tile_37)
    return tuple(
        int(tile_id)
        for tile_id in public_honor_tiles
        if int(tile_id) in discarded_tile_ids
    )


def _public_honor_shortlist_section_height(
    canvas: tkinter.Canvas,
    *,
    max_rows: int = 1,
) -> float:
    """Return the reserved height for the compact public-honor shortlist block."""

    heading_font = tkfont.Font(root=canvas, font=PLAYER_PANEL_SUMMARY_COMPACT_FONT)
    tile_image = _player_panel_tile_rank_image(canvas, 28)
    tile_height = float(tile_image.height()) if tile_image is not None else 10.0
    resolved_rows = max(1, int(max_rows))
    return (
        float(heading_font.metrics("linespace"))
        + PLAYER_PANEL_PUBLIC_HONOR_SECTION_GAP
        + resolved_rows * tile_height
        + max(0, resolved_rows - 1) * PLAYER_PANEL_PUBLIC_HONOR_ROW_GAP
    )


def _resolve_public_honor_shortlist_top(
    discard_rect: tuple[float, float, float, float],
    shortlist_height: float,
) -> float:
    """自家字牌ショートリストの上端位置を、自副露帯寄りに少し補正して返す。"""

    discard_top = float(discard_rect[1])
    discard_bottom = float(discard_rect[3])
    available_shift = max(discard_bottom - discard_top - float(shortlist_height), 0.0)
    centered_top = discard_top + available_shift / 2.0
    # 自河から自副露帯へ視線を動かしやすい程度にだけ下へ寄せる。
    meld_side_shift = available_shift * PLAYER_PANEL_PUBLIC_HONOR_SELF_MELD_BIAS_RATIO
    return min(centered_top + meld_side_shift, discard_top + available_shift)


def _draw_public_honor_shortlist(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    tile_ids: Sequence[int],
    text_muted: str,
    *,
    max_text_width: float,
    max_rows: int = 1,
    dim_tile_ids: Sequence[int] = (),
) -> None:
    """Draw honors still below the public-visibility threshold in a compact wrapped block."""

    if not tile_ids:
        return
    heading_text = _fit_text_to_width(
        canvas,
        PLAYER_PANEL_PUBLIC_HONOR_HEADING,
        PLAYER_PANEL_SUMMARY_COMPACT_FONT,
        max_text_width,
    )
    canvas.create_text(
        left,
        top,
        text=heading_text,
        anchor=tkinter.NW,
        fill=text_muted,
        font=PLAYER_PANEL_SUMMARY_COMPACT_FONT,
    )
    tile_top = top + float(
        tkfont.Font(root=canvas, font=PLAYER_PANEL_SUMMARY_COMPACT_FONT).metrics("linespace")
    ) + PLAYER_PANEL_PUBLIC_HONOR_SECTION_GAP
    dim_tile_id_set = {int(tile_id) for tile_id in dim_tile_ids}
    sample_tile = _player_panel_tile_rank_image(canvas, int(tile_ids[0]))
    tile_width = float(sample_tile.width()) if sample_tile is not None else 12.0
    tile_height = float(sample_tile.height()) if sample_tile is not None else 16.0
    columns = max(
        1,
        int((max_text_width + PLAYER_PANEL_PUBLIC_HONOR_TILE_GAP) // (tile_width + PLAYER_PANEL_PUBLIC_HONOR_TILE_GAP)),
    )
    resolved_rows = max(1, int(max_rows))
    max_tiles = columns * resolved_rows
    max_right = left + max_text_width
    for index, tile_37 in enumerate(tile_ids[:max_tiles]):
        tile_image = _player_panel_tile_rank_image(
            canvas,
            int(tile_37),
            dimmed=int(tile_37) in dim_tile_id_set,
        )
        if tile_image is None:
            continue
        row = index // columns
        col = index % columns
        draw_x = left + col * (tile_width + PLAYER_PANEL_PUBLIC_HONOR_TILE_GAP)
        draw_y = tile_top + row * (tile_height + PLAYER_PANEL_PUBLIC_HONOR_ROW_GAP)
        if draw_x + tile_image.width() > max_right:
            continue
        canvas.create_image(draw_x, draw_y, image=tile_image, anchor=tkinter.NW)


def _draw_line_summary_row(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    line_summary: Mapping[str, object],
    text_muted: str,
    *,
    max_text_width: float,
) -> None:
    """Draw one player-panel `Line` row as compact text."""

    text_candidates = (
        _format_player_panel_line_summary_text(line_summary),
        _format_player_panel_line_summary_text(line_summary, include_rank=False),
        _format_player_panel_line_summary_text(
            line_summary,
            include_rank=False,
            include_percent=False,
        ),
        "-",
    )
    line_font = tkfont.Font(root=canvas, font=PLAYER_PANEL_SUMMARY_LINE_FONT)
    display_text = next(
        (
            candidate
            for candidate in text_candidates
            if candidate and line_font.measure(candidate) <= max_text_width
        ),
        _fit_text_to_width(
            canvas,
            next((candidate for candidate in text_candidates if candidate and candidate != "-"), "-"),
            PLAYER_PANEL_SUMMARY_LINE_FONT,
            max_text_width,
        ),
    )
    canvas.create_text(
        left,
        top,
        text=display_text,
        anchor=tkinter.NW,
        fill=text_muted,
        font=PLAYER_PANEL_SUMMARY_LINE_FONT,
    )


def _draw_summary_content(
    canvas: tkinter.Canvas,
    seat: int,
    rect: tuple[float, float, float, float],
    player_name: str,
    summary_data: Mapping[str, object],
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    text_muted: str,
    horizontal: bool,
    public_honor_tiles: Sequence[int],
) -> None:
    """プレイヤーパネルの summary セクションを描く。"""
    left, top, right, bottom = rect
    tuning = _current_layout_tuning(canvas)
    summary_top = tuning.panel_summary_top
    content_width = max(right - left - 16, 40)
    display_player_name = _player_panel_display_name(seat, player_name)
    should_show_player_name = bool(display_player_name)
    remain_label_text, remain_value_text = _split_player_panel_remain_text(summary_data)
    remain_text_color = _player_panel_remain_text_color(summary_data, text_muted)
    top_line_labels = tuple(str(value) for value in summary_data.get("top_line_labels", ()))
    top_line_summaries = tuple(summary_data.get("top_line_summaries", ()))
    top_safe_hand_labels = _build_current_hand_safe_rank_labels(
        hand_tiles,
        hand_draw_tile,
        hand_danger_percentages,
        seat=seat,
        limit=3,
    )
    if not top_safe_hand_labels:
        top_safe_hand_labels = tuple(str(value) for value in summary_data.get("top_safe_hand_labels", ()))
    top_tile_rank_labels = tuple(str(value) for value in summary_data.get("top_tile_rank_labels", ()))
    top_line_labels = top_line_labels[:3]
    while len(top_line_labels) < 3:
        top_line_labels = (*top_line_labels, "-")
    top_line_summaries = top_line_summaries[:3]
    while len(top_line_summaries) < 3:
        top_line_summaries = (
            *top_line_summaries,
            {
                "rank_text": f"{len(top_line_summaries) + 1}.",
                "left_tile_label": "",
                "right_tile_label": "",
                "suit_label": "",
                "line_weight_text": "",
                "percent_text": top_line_labels[len(top_line_summaries)],
                "suit_remaining_count_text": "",
            },
        )
    if horizontal:
        top_safe_hand_labels = top_safe_hand_labels[:3]
        while len(top_safe_hand_labels) < 3:
            top_safe_hand_labels = (*top_safe_hand_labels, "-")
        packed_summary_top = max(16, summary_top - PLAYER_PANEL_HORIZONTAL_SUMMARY_TOP_PACK)
        remain_y = top + packed_summary_top
        heading_y = top + packed_summary_top + (14 if should_show_player_name else 8)
        ranking_top = top + packed_summary_top + (26 if should_show_player_name else 20)
        remain_label_font = tkfont.Font(root=canvas, font=PLAYER_PANEL_SUMMARY_REMAIN_LABEL_FONT)
        remain_value_font = tkfont.Font(root=canvas, font=PLAYER_PANEL_SUMMARY_REMAIN_FONT)
        remain_gap = 4
        remain_total_width = 136
        remain_label_width = remain_label_font.measure(remain_label_text)
        fitted_remain_value_text = _fit_text_to_width(
            canvas,
            remain_value_text,
            PLAYER_PANEL_SUMMARY_REMAIN_FONT,
            max(remain_total_width - remain_label_width - remain_gap, 32),
        )
        fitted_remain_value_width = remain_value_font.measure(fitted_remain_value_text)
        if should_show_player_name:
            fitted_player_name = _fit_text_to_width(
                canvas,
                display_player_name,
                PLAYER_PANEL_NAME_FONT,
                max(content_width - 104, 40),
            )
            canvas.create_text(
                left + 8,
                remain_y,
                text=fitted_player_name,
                anchor=tkinter.NW,
                fill=text_muted,
                font=PLAYER_PANEL_NAME_FONT,
            )
        canvas.create_text(
            right - 8,
            remain_y,
            text=fitted_remain_value_text,
            anchor=tkinter.NE,
            fill=remain_text_color,
            font=PLAYER_PANEL_SUMMARY_REMAIN_FONT,
        )
        canvas.create_text(
            right - 8 - fitted_remain_value_width - remain_gap,
            remain_y,
            text=remain_label_text,
            anchor=tkinter.NE,
            fill=remain_text_color,
            font=PLAYER_PANEL_SUMMARY_REMAIN_LABEL_FONT,
        )
        # 横長パネルは SUMMARY を 3 列で使い、Line / Safe hand / 危険ランク を並べる。
        inner_left = left + 8
        inner_right = right - 8
        column_gap = 8
        available_width = max(inner_right - inner_left - column_gap * 2, 96.0)
        column_width = max(available_width / 3.0, 56.0)
        line_column_left = inner_left
        safe_column_left = line_column_left + column_width + column_gap
        tile_column_left = safe_column_left + column_width + column_gap
        safe_column_left = min(safe_column_left, inner_right - column_width - column_gap - 56)
        tile_column_left = min(tile_column_left, inner_right - 56)
        line_top = ranking_top
        safe_top = ranking_top
        tile_top = ranking_top
        canvas.create_text(
            line_column_left,
            heading_y,
            text="Line",
            anchor=tkinter.NW,
            fill=text_muted,
            font=PLAYER_PANEL_SUMMARY_COMPACT_FONT,
        )
        canvas.create_text(
            safe_column_left,
            heading_y,
            text="Safe hand",
            anchor=tkinter.NW,
            fill=text_muted,
            font=PLAYER_PANEL_SUMMARY_COMPACT_FONT,
        )
        canvas.create_text(
            tile_column_left,
            heading_y,
            text=PLAYER_PANEL_TILE_RANK_HEADING,
            anchor=tkinter.NW,
            fill=text_muted,
            font=PLAYER_PANEL_SUMMARY_COMPACT_FONT,
        )
        line_text_width = max(safe_column_left - line_column_left - column_gap, 32)
        safe_text_width = max(tile_column_left - safe_column_left - column_gap, 32)
        line_row_pitch = _player_panel_line_row_pitch(canvas)
        ranking_row_pitch = max(
            1.0,
            _player_panel_tile_rank_row_pitch(canvas, tuning.top_tile_rank_row_gap),
        )
        for index, line_summary in enumerate(top_line_summaries):
            _draw_line_summary_row(
                canvas,
                line_column_left,
                line_top + index * line_row_pitch,
                line_summary,
                text_muted,
                max_text_width=line_text_width,
            )
        for index, safe_hand_text in enumerate(top_safe_hand_labels):
            _draw_tile_rank_row(
                canvas,
                safe_column_left,
                safe_top + index * ranking_row_pitch,
                safe_hand_text,
                text_muted,
                max_text_width=safe_text_width,
            )
        for index, tile_rank_text in enumerate(top_tile_rank_labels[:3]):
            _draw_tile_rank_row(
                canvas,
                tile_column_left,
                tile_top + index * ranking_row_pitch,
                tile_rank_text,
                text_muted,
                max_text_width=max(inner_right - tile_column_left, 32),
            )
    else:
        # 縦長パネルは、Safe hand を短く差し込みつつ、Line と 危険ランク も残す。
        top_safe_hand_labels = top_safe_hand_labels[:2]
        while len(top_safe_hand_labels) < 2:
            top_safe_hand_labels = (*top_safe_hand_labels, "-")
        remain_y = top + summary_top + (18 if should_show_player_name else 0)
        safe_heading_y = top + summary_top + (34 if should_show_player_name else 16)
        ranking_row_pitch = max(
            1.0,
            _player_panel_tile_rank_row_pitch(canvas, tuning.side_tile_rank_row_gap),
        )
        line_row_pitch = _player_panel_line_row_pitch(canvas)
        safe_top = top + summary_top + (48 if should_show_player_name else 30)
        if should_show_player_name:
            fitted_player_name = _fit_text_to_width(
                canvas,
                display_player_name,
                PLAYER_PANEL_NAME_FONT,
                content_width,
            )
            canvas.create_text(
                left + 8,
                top + summary_top,
                text=fitted_player_name,
                anchor=tkinter.NW,
                fill=text_muted,
                font=PLAYER_PANEL_NAME_FONT,
            )
        remain_label_font = tkfont.Font(root=canvas, font=PLAYER_PANEL_SUMMARY_REMAIN_LABEL_FONT)
        remain_gap = 4
        remain_label_width = remain_label_font.measure(remain_label_text)
        fitted_remain_value_text = _fit_text_to_width(
            canvas,
            remain_value_text,
            PLAYER_PANEL_SUMMARY_REMAIN_FONT,
            max(content_width - remain_label_width - remain_gap, 32),
        )
        canvas.create_text(
            left + 8,
            remain_y,
            text=remain_label_text,
            anchor=tkinter.NW,
            fill=remain_text_color,
            font=PLAYER_PANEL_SUMMARY_REMAIN_LABEL_FONT,
        )
        canvas.create_text(
            left + 8 + remain_label_width + remain_gap,
            remain_y,
            text=fitted_remain_value_text,
            anchor=tkinter.NW,
            fill=remain_text_color,
            font=PLAYER_PANEL_SUMMARY_REMAIN_FONT,
        )
        canvas.create_text(
            left + 8,
            safe_heading_y,
            text="Safe hand",
            anchor=tkinter.NW,
            fill=text_muted,
            font=PLAYER_PANEL_SUMMARY_COMPACT_FONT,
        )
        for index, safe_hand_text in enumerate(top_safe_hand_labels):
            _draw_tile_rank_row(
                canvas,
                left + 8,
                safe_top + index * ranking_row_pitch,
                safe_hand_text,
                text_muted,
                max_text_width=content_width,
            )
        line_heading_y = safe_top + len(top_safe_hand_labels) * ranking_row_pitch + 2
        canvas.create_text(
            left + 8,
            line_heading_y,
            text="Line",
            anchor=tkinter.NW,
            fill=text_muted,
            font=PLAYER_PANEL_SUMMARY_COMPACT_FONT,
        )
        line_top = line_heading_y + 12
        for index, line_summary in enumerate(top_line_summaries):
            _draw_line_summary_row(
                canvas,
                left + 8,
                line_top + index * line_row_pitch,
                line_summary,
                text_muted,
                max_text_width=content_width,
            )
        tile_heading_y = line_top + len(top_line_summaries) * line_row_pitch + 1
        canvas.create_text(
            left + 8,
            tile_heading_y,
            text=PLAYER_PANEL_TILE_RANK_HEADING,
            anchor=tkinter.NW,
            fill=text_muted,
            font=PLAYER_PANEL_SUMMARY_COMPACT_FONT,
        )
        tile_top = tile_heading_y + 12
        max_tile_rows = 0
        row_top = tile_top
        tile_row_bottom_limit = bottom - 6
        while row_top + ranking_row_pitch <= tile_row_bottom_limit and max_tile_rows < 3:
            max_tile_rows += 1
            row_top += ranking_row_pitch
        for index, tile_rank_text in enumerate(top_tile_rank_labels[:max_tile_rows]):
            _draw_tile_rank_row(
                canvas,
                left + 8,
                tile_top + index * ranking_row_pitch,
                tile_rank_text,
                text_muted,
                max_text_width=content_width,
            )


def _build_player_alert_indicators(
    summary_data: Mapping[str, object],
    push_alert_data: Mapping[str, object],
    *,
    seat: int,
) -> tuple[PlayerAlertIndicator, ...]:
    """Build player-panel alert dots from current remain and latest-discard danger."""

    if bool(summary_data.get("is_loading", False)):
        return ()
    indicators: list[PlayerAlertIndicator] = []
    is_riichi = bool(summary_data.get("is_riichi", False))
    remain_count: float | None = None
    no_temp_remain_count: float | None = None
    if "denominator_count" in summary_data:
        try:
            remain_count = max(0.0, float(summary_data.get("denominator_count", 0.0)))
        except (TypeError, ValueError):
            remain_count = None
        if remain_count is not None:
            if remain_count < 6.0:
                indicators.append(
                    PlayerAlertIndicator(
                        color=PLAYER_ALERT_RED,
                        label=f"Remain {remain_count:.1f}",
                        key="remain_red",
                    )
                )
            elif remain_count < 8.0:
                indicators.append(
                    PlayerAlertIndicator(
                        color=PLAYER_ALERT_YELLOW,
                        label=f"Remain {remain_count:.1f}",
                        key="remain_yellow",
                )
                )
    if "denominator_count_without_temporary_safe" in summary_data:
        try:
            no_temp_remain_count = max(
                0.0,
                float(summary_data.get("denominator_count_without_temporary_safe", 0.0)),
            )
        except (TypeError, ValueError):
            no_temp_remain_count = None
    if is_riichi:
        return tuple(indicators)
    try:
        menzen_alert_score = max(0, int(summary_data.get("menzen_alert_score", 0)))
    except (TypeError, ValueError):
        menzen_alert_score = 0
    if menzen_alert_score >= MENZEN_ALERT_RED_SCORE:
        menzen_red_color = PLAYER_ALERT_RED
        # When the no-temp structural remain has already fallen below 13, keep the same
        # red-severity alert but emphasize the dot in purple instead of red.
        if (
            no_temp_remain_count is not None
            and no_temp_remain_count < NO_TEMP_REMAIN_RED_TINT_THRESHOLD
        ):
            menzen_red_color = PLAYER_ALERT_PURPLE
        indicators.append(
            PlayerAlertIndicator(
                color=menzen_red_color,
                label=f"門前 {menzen_alert_score}",
                key="menzen_red",
            )
        )
    elif menzen_alert_score >= MENZEN_ALERT_YELLOW_SCORE:
        indicators.append(
            PlayerAlertIndicator(
                color=PLAYER_ALERT_YELLOW,
                label=f"門前 {menzen_alert_score}",
                key="menzen_yellow",
            )
        )
    try:
        hand_pattern_alert_level = max(0, int(summary_data.get("hand_pattern_alert_level", 0)))
    except (TypeError, ValueError):
        hand_pattern_alert_level = 0
    if hand_pattern_alert_level >= HAND_PATTERN_ALERT_RED_LEVEL:
        indicators.append(
            PlayerAlertIndicator(
                color=PLAYER_ALERT_RED,
                label="手役傾向",
                key="hand_pattern_red",
            )
        )
    elif hand_pattern_alert_level >= HAND_PATTERN_ALERT_YELLOW_LEVEL:
        indicators.append(
            PlayerAlertIndicator(
                color=PLAYER_ALERT_YELLOW,
                label="手役傾向",
                key="hand_pattern_yellow",
            )
        )
    if bool(summary_data.get("suit_bias_alert", False)):
        indicators.append(
            PlayerAlertIndicator(
                color=PLAYER_ALERT_YELLOW,
                label="染/対々 UP",
                key="suit_bias",
            )
        )
    if bool(summary_data.get("ryanmen_chi_central_tedashi_alert", False)):
        indicators.append(
            PlayerAlertIndicator(
                color=PLAYER_ALERT_YELLOW,
                label="両面チー3-7",
                key="ryanmen_chi_37",
            )
        )
    if (
        bool(summary_data.get("tedashi_thinking_rise_alert", False))
        and remain_count is not None
        and remain_count <= 14.0
    ):
        indicators.append(
            PlayerAlertIndicator(
                color=PLAYER_ALERT_YELLOW,
                label="思考時間聴牌近",
                key="tenpai_near",
            )
        )
    try:
        push_alert_percent = max(0.0, float(push_alert_data.get("percentage", 0.0)))
    except (TypeError, ValueError):
        push_alert_percent = 0.0
    push_alert_threshold_percent = _player_push_alert_threshold_percent(push_alert_data)
    try:
        push_alert_seat = int(push_alert_data.get("seat", seat))
    except (TypeError, ValueError):
        push_alert_seat = seat
    push_alert_kind = str(push_alert_data.get("kind", "") or "").strip().lower()
    push_tile_label = str(push_alert_data.get("tile_label", "") or "").strip()
    try:
        push_alert_discard_index = int(push_alert_data.get("discard_index"))
    except (TypeError, ValueError):
        push_alert_discard_index = None
    if push_alert_seat == seat and push_alert_kind == "release":
        release_label = "Push解除"
        if push_tile_label:
            release_label = f"Push解除 {push_tile_label}"
        indicators.append(
            PlayerAlertIndicator(
                color=PLAYER_ALERT_GREEN,
                label=release_label,
                key=(
                    f"push_release:{push_alert_discard_index}"
                    if push_alert_discard_index is not None
                    else "push_release"
                ),
            )
        )
    elif push_alert_seat == seat and push_alert_percent >= push_alert_threshold_percent:
        push_label = f"Push {push_alert_percent:.1f}%"
        if push_tile_label:
            push_label = f"Push {push_tile_label} {push_alert_percent:.1f}%"
        indicators.append(
            PlayerAlertIndicator(
                color=PLAYER_ALERT_PURPLE,
                label=push_label,
                key=(
                    f"push:{push_alert_discard_index}"
                    if push_alert_discard_index is not None
                    else "push"
                ),
            )
        )
    return tuple(indicators)


def _build_player_panel_alert_indicators_by_seat(
    summaries_by_seat: Mapping[int, Mapping[str, object]],
    push_alerts_by_seat: Mapping[int, Mapping[str, object]],
) -> dict[int, tuple[PlayerAlertIndicator, ...]]:
    """Build per-seat player-panel alert rows from the normalized renderer payloads."""

    return {
        seat: _build_player_alert_indicators(
            summaries_by_seat.get(seat, {}),
            push_alerts_by_seat.get(seat, {}),
            seat=seat,
        )
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    }


def build_player_panel_alert_indicators_by_seat(
    summaries_by_seat: OpponentSujiPanelSummaries,
    push_alerts_by_seat: PlayerPushAlertPercentages,
) -> dict[int, tuple[PlayerAlertIndicator, ...]]:
    """Public wrapper for precomputing player-panel alert rows off the redraw path."""

    return _build_player_panel_alert_indicators_by_seat(
        _normalize_opponent_suji_panel_summaries(summaries_by_seat),
        _normalize_player_push_alert_percentages(push_alerts_by_seat),
    )


def _normalize_player_alert_indicators_by_seat(
    indicators_by_seat: PlayerAlertIndicatorsBySeat | None,
) -> dict[int, tuple[PlayerAlertIndicator, ...]]:
    """Normalize precomputed player-panel alert rows to immutable renderer tuples."""

    if indicators_by_seat is None:
        return {}
    normalized: dict[int, tuple[PlayerAlertIndicator, ...]] = {}
    for raw_seat, raw_indicators in indicators_by_seat.items():
        try:
            seat = int(raw_seat)
        except (TypeError, ValueError):
            continue
        if seat not in HAND_DANGER_BAR_SEAT_ORDER:
            continue
        normalized_indicators: list[PlayerAlertIndicator] = []
        for raw_indicator in raw_indicators:
            if isinstance(raw_indicator, PlayerAlertIndicator):
                normalized_indicators.append(raw_indicator)
                continue
            if not isinstance(raw_indicator, Mapping):
                continue
            color = str(raw_indicator.get("color", "") or "").strip()
            label = str(raw_indicator.get("label", "") or "").strip()
            key = str(raw_indicator.get("key", "") or "").strip()
            if not color or not label:
                continue
            normalized_indicators.append(
                PlayerAlertIndicator(
                    color=color,
                    label=label,
                    key=key,
                )
            )
        normalized[seat] = tuple(normalized_indicators)
    return normalized


def _player_panel_alert_sound_priority(alert_key: str) -> int:
    """Return player-panel alert sound priority, with push alerts muted."""

    if alert_key == "remain_purple" or alert_key.startswith("push:"):
        return 3
    if alert_key in {"remain_red", "menzen_red", "hand_pattern_red"}:
        return 2
    if alert_key in {
        "remain_yellow",
        "hand_pattern_yellow",
        "suit_bias",
        "ryanmen_chi_37",
        "tenpai_near",
    } or alert_key.startswith("push_release"):
        return 1
    return 0


def _player_panel_remain_sound_level_from_alert_keys(alert_keys: Sequence[str] | None) -> int:
    """Infer the remain sound level from existing remain alert keys."""

    best_level = 0
    for alert_key in (str(raw_key or "").strip() for raw_key in (alert_keys or ())):
        if alert_key == "remain_purple":
            best_level = max(best_level, 3)
        elif alert_key == "remain_red":
            best_level = max(best_level, 2)
        elif alert_key == "remain_yellow":
            best_level = max(best_level, 1)
    return best_level


def _player_panel_remain_sound_level(
    summary_data: Mapping[str, object],
    alert_keys: Sequence[str] | None = None,
) -> int:
    """Return the remain sound level from the no-temp thresholds, with key fallback."""

    raw_no_temp_remain = summary_data.get("denominator_count_without_temporary_safe")
    try:
        no_temp_remain = float(raw_no_temp_remain)
    except (TypeError, ValueError):
        return _player_panel_remain_sound_level_from_alert_keys(alert_keys)
    if no_temp_remain < 0.0:
        return 0
    if no_temp_remain <= 6.0:
        return 3
    if no_temp_remain <= 9.0:
        return 2
    if no_temp_remain <= 12.0:
        return 1
    return 0


def _player_panel_remain_sound_key(level: int) -> str:
    """Map one remain sound level to the alert key used for the sound."""

    if level >= 3:
        return "remain_purple"
    if level == 2:
        return "remain_red"
    if level == 1:
        return "remain_yellow"
    return ""


def _filter_player_panel_sound_alert_keys(alert_keys: Sequence[str] | None) -> tuple[str, ...]:
    """Keep only non-remain alert keys for generic player-panel sound transitions."""

    return tuple(
        alert_key
        for alert_key in (str(raw_key or "").strip() for raw_key in (alert_keys or ()))
        if alert_key and not alert_key.startswith("remain_")
    )


def _highest_priority_player_panel_alert_key(alert_keys: Sequence[str] | None) -> str:
    """Return one seat's current highest-priority audible alert key, or ``""`` when muted."""

    best_key = ""
    best_priority = 0
    for raw_alert_key in alert_keys or ():
        alert_key = str(raw_alert_key or "").strip()
        alert_priority = _player_panel_alert_sound_priority(alert_key)
        if alert_priority > best_priority:
            best_key = alert_key
            best_priority = alert_priority
    return best_key


def _player_panel_alert_sound_tone(alert_key: str) -> tuple[int, int]:
    """Return the beep tone for one player-panel alert key, grouped by alert color."""

    normalized_key = str(alert_key or "").strip().lower()
    if "purple" in normalized_key or normalized_key.startswith("push:"):
        return 520, 110
    if "red" in normalized_key:
        return 760, 90
    if "yellow" in normalized_key or normalized_key in {
        "suit_bias",
        "ryanmen_chi_37",
        "tenpai_near",
    }:
        return 960, 70
    if "green" in normalized_key or normalized_key.startswith("push_release"):
        return 1200, 60
    return 880, 70


def _play_player_panel_alert_sound_worker(alert_key: str) -> None:
    """Emit one short platform sound for a player-panel alert transition."""

    if winsound is None:
        return

    frequency_hz, duration_ms = _player_panel_alert_sound_tone(alert_key)
    try:
        winsound.Beep(frequency_hz, duration_ms)
    except RuntimeError:
        try:
            winsound.MessageBeep()
        except RuntimeError:
            return


def _play_player_panel_alert_sound_if_needed(
    canvas: tkinter.Canvas,
    summaries_by_seat: Mapping[int, Mapping[str, object]],
    push_alerts_by_seat: Mapping[int, Mapping[str, object]],
    *,
    alert_indicators_by_seat: PlayerAlertIndicatorsBySeat | None = None,
) -> None:
    """Play one short sound only when a seat's audible alert appears or upgrades."""

    previous_alert_keys_by_seat = getattr(
        canvas,
        "last_player_panel_alert_keys_by_seat",
        {seat: tuple() for seat in HAND_DANGER_BAR_SEAT_ORDER},
    )
    previous_remain_sound_level_by_seat = getattr(
        canvas,
        "last_player_panel_remain_sound_level_by_seat",
        {
            seat: _player_panel_remain_sound_level_from_alert_keys(
                previous_alert_keys_by_seat.get(seat, ())
            )
            for seat in HAND_DANGER_BAR_SEAT_ORDER
        },
    )
    current_indicators_by_seat = _normalize_player_alert_indicators_by_seat(
        alert_indicators_by_seat
    )
    if not current_indicators_by_seat:
        current_indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            summaries_by_seat,
            push_alerts_by_seat,
        )
    current_alert_keys_by_seat = {
        seat: tuple(indicator.key for indicator in indicators if indicator.key)
        for seat, indicators in current_indicators_by_seat.items()
    }
    canvas.last_player_panel_alert_keys_by_seat = current_alert_keys_by_seat
    current_remain_sound_level_by_seat: dict[int, int] = {}
    upgraded_alert_keys: list[str] = []
    for seat in HAND_DANGER_BAR_SEAT_ORDER:
        previous_remain_level = int(
            previous_remain_sound_level_by_seat.get(
                seat,
                _player_panel_remain_sound_level_from_alert_keys(
                    previous_alert_keys_by_seat.get(seat, ())
                ),
            )
        )
        current_remain_level = _player_panel_remain_sound_level(
            summaries_by_seat.get(seat, {}),
            current_alert_keys_by_seat.get(seat, ()),
        )
        current_remain_sound_level_by_seat[seat] = current_remain_level
        if current_remain_level > previous_remain_level:
            remain_sound_key = _player_panel_remain_sound_key(current_remain_level)
            if remain_sound_key:
                upgraded_alert_keys.append(remain_sound_key)
        previous_total_priority = max(
            previous_remain_level,
            _player_panel_alert_sound_priority(
                _highest_priority_player_panel_alert_key(
                    _filter_player_panel_sound_alert_keys(
                        previous_alert_keys_by_seat.get(seat, ())
                    )
                )
            ),
        )
        current_key = _highest_priority_player_panel_alert_key(
            _filter_player_panel_sound_alert_keys(current_alert_keys_by_seat.get(seat, ()))
        )
        if _player_panel_alert_sound_priority(current_key) > previous_total_priority:
            upgraded_alert_keys.append(current_key)
    canvas.last_player_panel_remain_sound_level_by_seat = current_remain_sound_level_by_seat
    if not upgraded_alert_keys:
        return
    highest_priority_key = max(
        upgraded_alert_keys,
        key=lambda alert_key: _player_panel_alert_sound_priority(str(alert_key)),
    )
    now_monotonic_s = time.monotonic()
    if (
        now_monotonic_s
        - float(getattr(canvas, "last_player_panel_alert_sound_monotonic_s", 0.0) or 0.0)
        < PLAYER_PANEL_ALERT_SOUND_MIN_INTERVAL_S
    ):
        return
    canvas.last_player_panel_alert_sound_monotonic_s = now_monotonic_s
    if winsound is None:
        try:
            canvas.bell()
        except tkinter.TclError:
            return
        return
    _start_tracked_background_thread(
        label="panel alert sound",
        name="player-panel-alert-sound",
        target=_play_player_panel_alert_sound_worker,
        args=(highest_priority_key,),
    )


def _draw_alert_content(
    canvas: tkinter.Canvas,
    rect: tuple[float, float, float, float],
    alert_indicators: Sequence[PlayerAlertIndicator],
    text_muted: str,
) -> None:
    """プレイヤーパネルの alert セクションを描く。"""
    left, top, right, bottom = rect
    if not alert_indicators:
        canvas.create_text(
            left + 8,
            top + 24,
            text="-",
            anchor=tkinter.NW,
            fill=PLAYER_ALERT_NONE_TEXT,
            font=("Yu Gothic UI", 7, "bold"),
        )
        return
    current_y = top + 28
    for indicator in alert_indicators[:3]:
        if current_y > bottom - 8:
            break
        canvas.create_oval(
            left + 8,
            current_y - PLAYER_ALERT_DOT_RADIUS,
            left + 8 + PLAYER_ALERT_DOT_RADIUS * 2,
            current_y + PLAYER_ALERT_DOT_RADIUS,
            fill=indicator.color,
            outline="",
        )
        canvas.create_text(
            left + 20,
            current_y - 6,
            text=indicator.label,
            anchor=tkinter.NW,
            width=max(right - left - 28, 32),
            fill=text_muted,
            font=("Yu Gothic UI", 7, "bold"),
        )
        current_y += PLAYER_ALERT_ROW_GAP


def _format_player_panel_score_diff(score_diff: int) -> str:
    """Format one self-relative score gap such as `+3,900` or `-12,000`."""

    normalized_score_diff = int(score_diff)
    if normalized_score_diff > 0:
        return f"+{normalized_score_diff:,}"
    if normalized_score_diff < 0:
        return f"{normalized_score_diff:,}"
    return "0"


def _player_panel_score_diff_text_color(score_diff: int) -> str:
    """Return the text color for one self-relative opponent score gap."""

    if score_diff > 0:
        return PLAYER_PANEL_SCORE_POSITIVE_TEXT
    if score_diff < 0:
        return PLAYER_PANEL_SCORE_NEGATIVE_TEXT
    return PLAYER_PANEL_SCORE_NEUTRAL_TEXT


def _draw_score_content(
    canvas: tkinter.Canvas,
    rect: tuple[float, float, float, float],
    seat: int,
    score_diff: int,
    button_fill: str,
    button_outline: str,
    button_text: str,
    text_muted: str,
    detail_panel_state: DetailPanelState,
) -> None:
    """Draw the score-gap section plus the placeholder condition button."""

    left, top, right, bottom = rect
    caption_y = top + 24
    value_y = top + 42
    canvas.create_text(
        (left + right) / 2,
        caption_y,
        text="自家差",
        anchor=tkinter.CENTER,
        fill=text_muted,
        font=PLAYER_PANEL_SCORE_CAPTION_FONT,
    )
    fitted_score_text = _fit_text_to_width(
        canvas,
        _format_player_panel_score_diff(score_diff),
        PLAYER_PANEL_SCORE_VALUE_FONT,
        max(right - left - 12, 24),
    )
    canvas.create_text(
        (left + right) / 2,
        value_y,
        text=fitted_score_text,
        anchor=tkinter.CENTER,
        fill=_player_panel_score_diff_text_color(score_diff),
        font=PLAYER_PANEL_SCORE_VALUE_FONT,
    )

    button_left = left + 6
    button_right = right - 6
    button_bottom = bottom - PLAYER_PANEL_SCORE_BUTTON_BOTTOM_MARGIN
    button_height = min(
        PLAYER_PANEL_VERTICAL_BUTTON_HEIGHT,
        max(PLAYER_PANEL_HORIZONTAL_BUTTON_HEIGHT + 2, button_bottom - (top + PLAYER_PANEL_SCORE_BUTTON_TOP_MARGIN)),
    )
    button_top = max(
        top + PLAYER_PANEL_SCORE_BUTTON_TOP_MARGIN,
        button_bottom - button_height,
    )
    if button_top + button_height > button_bottom or button_right <= button_left:
        return
    label = PLAYER_PANEL_SCORE_BUTTON_LABEL
    is_active = (
        detail_panel_state.seat == seat
        and detail_panel_state.button_label == label
        and detail_panel_state.view_kind == "panel_placeholder"
    )
    current_button_fill = "#29415d" if is_active else button_fill
    _draw_detail_button(
        canvas,
        button_left,
        button_top,
        button_right,
        button_bottom,
        current_button_fill,
        button_outline,
        button_text,
    )
    canvas.player_panel_button_specs.append(
        PlayerPanelButtonSpec(
            seat=seat,
            label=label,
            rect=(button_left, button_top, button_right, button_bottom),
        )
    )
    fitted_label = _fit_text_to_width(
        canvas,
        label,
        ("Yu Gothic UI", 7, "bold"),
        max(button_right - button_left - 8, 20),
    )
    canvas.create_text(
        (button_left + button_right) / 2,
        (button_top + button_bottom) / 2,
        text=fitted_label,
        fill=button_text,
        font=("Yu Gothic UI", 7, "bold"),
    )


def _draw_button_group(
    canvas: tkinter.Canvas,
    rect: tuple[float, float, float, float],
    seat: int,
    player_name: str,
    button_fill: str,
    button_outline: str,
    button_text: str,
    horizontal: bool,
    detail_panel_state: DetailPanelState,
) -> None:
    """横長・縦長パネルの違いを吸収しつつボタン群を描く。"""
    left, top, right, bottom = rect
    # 詳細切替に使う仮のボタンラベル配列。
    labels = PLAYER_PANEL_BUTTON_LABELS
    has_saved_memo = _player_has_saved_memo(canvas, player_name)
    # 横長パネルでは背の低いボタンを縦に積む。
    if horizontal:
        button_height = PLAYER_PANEL_HORIZONTAL_BUTTON_HEIGHT
        gap = PLAYER_PANEL_HORIZONTAL_BUTTON_GAP
        current_top = top + PLAYER_PANEL_HORIZONTAL_BUTTON_TOP_MARGIN
        for label in labels:
            # パネル下端を越えるボタンは描かない。
            if current_top + button_height > bottom - PLAYER_PANEL_HORIZONTAL_BUTTON_BOTTOM_MARGIN:
                break
            is_active = (
                detail_panel_state.seat == seat
                and detail_panel_state.button_label == label
                and (
                    (label == "DETAIL" and detail_panel_state.view_kind == "player_memo")
                    or (label != "DETAIL" and detail_panel_state.view_kind == "panel_placeholder")
                )
            )
            current_button_fill = "#29415d" if is_active else button_fill
            current_button_outline = button_outline
            if label == "DETAIL" and has_saved_memo:
                current_button_fill = (
                    PLAYER_PANEL_DETAIL_MEMO_ACTIVE_FILL
                    if is_active
                    else PLAYER_PANEL_DETAIL_MEMO_FILL
                )
                current_button_outline = PLAYER_PANEL_DETAIL_MEMO_OUTLINE
            _draw_detail_button(
                canvas,
                left + 6,
                current_top,
                right - 6,
                current_top + button_height,
                current_button_fill,
                current_button_outline,
                button_text,
            )
            canvas.player_panel_button_specs.append(
                PlayerPanelButtonSpec(
                    seat=seat,
                    label=label,
                    rect=(left + 6, current_top, right - 6, current_top + button_height),
                )
            )
            fitted_label = _fit_text_to_width(
                canvas,
                label,
                ("Yu Gothic UI", 7, "bold"),
                max(right - left - 18, 24),
            )
            canvas.create_text(
                (left + right) / 2,
                current_top + button_height / 2,
                text=fitted_label,
                fill=button_text,
                font=("Yu Gothic UI", 7, "bold"),
            )
            current_top += button_height + gap
    else:
        # 縦長パネルでは少し背の高いボタンを縦に積む。
        button_height = PLAYER_PANEL_VERTICAL_BUTTON_HEIGHT
        gap = PLAYER_PANEL_VERTICAL_BUTTON_GAP
        current_top = top + PLAYER_PANEL_VERTICAL_BUTTON_TOP_MARGIN
        for label in labels:
            # パネル下端を越えるボタンは描かない。
            if current_top + button_height > bottom - PLAYER_PANEL_VERTICAL_BUTTON_BOTTOM_MARGIN:
                break
            is_active = (
                detail_panel_state.seat == seat
                and detail_panel_state.button_label == label
                and (
                    (label == "DETAIL" and detail_panel_state.view_kind == "player_memo")
                    or (label != "DETAIL" and detail_panel_state.view_kind == "panel_placeholder")
                )
            )
            current_button_fill = "#29415d" if is_active else button_fill
            current_button_outline = button_outline
            if label == "DETAIL" and has_saved_memo:
                current_button_fill = (
                    PLAYER_PANEL_DETAIL_MEMO_ACTIVE_FILL
                    if is_active
                    else PLAYER_PANEL_DETAIL_MEMO_FILL
                )
                current_button_outline = PLAYER_PANEL_DETAIL_MEMO_OUTLINE
            _draw_detail_button(
                canvas,
                left + 6,
                current_top,
                right - 6,
                current_top + button_height,
                current_button_fill,
                current_button_outline,
                button_text,
            )
            canvas.player_panel_button_specs.append(
                PlayerPanelButtonSpec(
                    seat=seat,
                    label=label,
                    rect=(left + 6, current_top, right - 6, current_top + button_height),
                )
            )
            fitted_label = _fit_text_to_width(
                canvas,
                label,
                ("Yu Gothic UI", 8, "bold"),
                max(right - left - 18, 24),
            )
            canvas.create_text(
                (left + right) / 2,
                current_top + button_height / 2,
                text=fitted_label,
                fill=button_text,
                font=("Yu Gothic UI", 8, "bold"),
            )
            current_top += button_height + gap


def _lag_marker_reference_copy(kind: str) -> tuple[str, str]:
    """Return the shared-detail title/body for the selected lag-marker mode."""

    normalized_kind = _normalize_lag_marker_reference_kind(kind)
    if normalized_kind == LAG_MARKER_REFERENCE_KIND_BLACK:
        return (
            "Lag marker: N",
            "`N` は lag 情報を無効扱いにします。\n\n"
            "この状態では lag を理由にした推測見え枚数補正を加えません。"
            "\n\nClick any lag marker on the river to cycle `L -> Pl -> N`.",
        )
    if normalized_kind == LAG_MARKER_REFERENCE_KIND_GREEN:
        return (
            "Lag marker: Pl",
            "`Pl` は pon-lag-likely 扱いです。\n\n"
            "同じ 34 種牌で 2 人以上がラグっている場合、または上家打牌で "
            "`鳴き無しON`、もしくは `鳴き無しOFF` かつ自分 hand snapshot でチー/ポンできず "
            "call ボタンも出ていない場合に表示します。"
            "\n\nClick any lag marker on the river to cycle `L -> Pl -> N`.",
        )
    return (
        "Lag marker: L",
        "`L` は通常の lag marker です。\n\n"
        "未確定または probable な未鳴きラグ (`lagged = 1 / 3`) を表示します。"
        " short system delay (`lagged = 6`) は含めません。"
        "\n\nClick any lag marker on the river to cycle `L -> Pl -> N`.",
    )


def _draw_lag_marker_reference_buttons(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    button_fill: str,
    button_outline: str,
    button_text: str,
) -> float:
    """Draw the blue/green/black lag-reference circles and return the next content Y."""

    active_kind = _normalize_lag_marker_reference_kind(
        getattr(canvas, "lag_marker_reference_kind", LAG_MARKER_REFERENCE_KIND_BLUE)
    )
    canvas.lag_marker_reference_button_specs = []
    radius = float(LAG_MARKER_REFERENCE_CIRCLE_RADIUS)
    current_left = left + radius
    circle_center_y = top + radius
    label_top = circle_center_y + radius + LAG_MARKER_REFERENCE_LABEL_TOP_GAP
    for kind, label, dot_color in (
        (LAG_MARKER_REFERENCE_KIND_BLUE, "青丸", LAG_DISCARD_MARKER),
        (LAG_MARKER_REFERENCE_KIND_GREEN, "緑丸", PON_LAG_LIKELY_DISCARD_MARKER),
        (LAG_MARKER_REFERENCE_KIND_BLACK, "黒丸", "#111827"),
    ):
        is_active = kind == active_kind
        outer_radius = radius + (2.0 if is_active else 0.0)
        outer_outline = "#93c5fd" if is_active else button_outline
        outer_width = 2 if is_active else 1
        canvas.create_oval(
            current_left - outer_radius,
            circle_center_y - outer_radius,
            current_left + outer_radius,
            circle_center_y + outer_radius,
            fill=button_fill,
            outline=outer_outline,
            width=outer_width,
        )
        canvas.create_oval(
            current_left - radius + 2,
            circle_center_y - radius + 2,
            current_left + radius - 2,
            circle_center_y + radius - 2,
            fill=dot_color,
            outline="",
        )
        canvas.create_text(
            current_left,
            label_top,
            text=label,
            anchor=tkinter.N,
            fill=button_text,
            font=("Yu Gothic UI", 7, "bold"),
        )
        canvas.lag_marker_reference_button_specs.append(
            LagMarkerReferenceButtonSpec(
                kind=kind,
                center=(current_left, circle_center_y),
                radius=radius,
            )
        )
        current_left += radius * 2 + LAG_MARKER_REFERENCE_CIRCLE_GAP
    return label_top + 14


def _draw_detail_toggle_group(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    layout: dict[str, object],
    visible_summary: VisibleTileSummary,
    visible_inference_summary: VisibleTileInferenceSummary,
    button_fill: str,
    button_outline: str,
    button_text: str,
    text_muted: str,
    player_names_by_seat: PlayerNamesBySeat,
    detail_panel_state: DetailPanelState,
) -> None:
    """Draw the shared detail display space on the right side of the table."""
    # 詳細パネル内の上段2段と下段本文の矩形を取り出す。
    left, top, right, bottom = layout["detail_rect"]
    visible3_rect = layout["visible3_rect"]
    visible4_rect = layout["visible4_rect"]
    detail_content_rect = layout["detail_content_rect"]
    # 3見え/4見えセクションの境界線を引く。
    canvas.create_line(left + 1, visible3_rect[3], right - 1, visible3_rect[3], fill=button_outline, width=1)
    canvas.create_line(left + 1, visible4_rect[3], right - 1, visible4_rect[3], fill=button_outline, width=1)
    # 見え牌セクションのタイトルと、3見え/4見えの牌画像列を描く。
    canvas.create_text(
        left + 16,
        top + 18,
        text="Visible tiles",
        anchor=tkinter.W,
        fill=button_text,
        font=("Yu Gothic UI", 10, "bold"),
    )
    merged_three_samples, inferred_three_samples = _merge_visible_detail_samples(
        (
            visible_summary.three_visible_tiles
            if THREE_VISIBLE_MARKERS_ENABLED
            else []
        ),
        (
            visible_inference_summary.inferred_three_visible_tiles
            if THREE_VISIBLE_MARKERS_ENABLED
            else []
        ),
    )
    merged_four_samples, inferred_four_samples = _merge_visible_detail_samples(
        visible_summary.four_visible_tiles,
        visible_inference_summary.inferred_four_visible_tiles,
    )
    _draw_visible_tiles(
        canvas,
        img_table,
        samples=merged_three_samples,
        title="Visible x3",
        visible_count_kind="three",
        left=visible3_rect[0] + 14,
        top=visible3_rect[1] + 22,
        right=visible3_rect[2] - 14,
        bottom=visible3_rect[3] - 8,
        text_muted=text_muted,
        inferred_incremented_samples=inferred_three_samples,
    )
    _draw_visible_tiles(
        canvas,
        img_table,
        samples=merged_four_samples,
        title="Visible x4",
        visible_count_kind="four",
        left=visible4_rect[0] + 14,
        top=visible4_rect[1] + 22,
        right=visible4_rect[2] - 14,
        bottom=visible4_rect[3] - 8,
        text_muted=text_muted,
        inferred_incremented_samples=inferred_four_samples,
    )

    # 下段本文は、各プレイヤーパネルのボタンに応じて表示を切り替える共通領域として使う。
    detail_title = "Visible tile details"
    detail_body = (
        "Use each player panel button to switch this common detail area.\n\n"
        "The DETAIL button opens the selected player's memo editor from player_profiles.csv.\n"
        "STATUS, プレイヤー補正, and 条件表示 are placeholders for future implementation."
    )
    detail_title_top = detail_content_rect[1] + 18
    detail_body_top = detail_content_rect[1] + 42
    if detail_panel_state.view_kind == "visible":
        detail_title, detail_body = _lag_marker_reference_copy(
            getattr(canvas, "lag_marker_reference_kind", LAG_MARKER_REFERENCE_KIND_BLUE)
        )
        detail_title_top = detail_content_rect[1] + 18
        detail_body_top = detail_title_top + 24
    if detail_panel_state.view_kind == "panel_placeholder" and detail_panel_state.seat is not None:
        seat_title = PLAYER_PANEL_TITLE_BY_SEAT.get(detail_panel_state.seat, "PLAYER")
        player_name = str(player_names_by_seat.get(detail_panel_state.seat, "")).strip()
        detail_title = f"{seat_title} {detail_panel_state.button_label}"
        detail_body = (
            f"Selected player: {player_name or seat_title}\n\n"
            f"The shared detail area is now reserved for the {detail_panel_state.button_label} view.\n"
            "This screen is a placeholder and can be replaced later with alerts, danger rankings, or other tools."
        )
    elif detail_panel_state.view_kind == "player_memo" and detail_panel_state.seat is not None:
        seat_title = PLAYER_PANEL_TITLE_BY_SEAT.get(detail_panel_state.seat, "PLAYER")
        player_name = str(player_names_by_seat.get(detail_panel_state.seat, "")).strip()
        detail_title = f"{seat_title} Player Memo"
        detail_body = (
            f"Editing: {player_name or seat_title}\n\n"
            "Changes are saved automatically when you switch to another player-panel button or close the window."
        )

    canvas.create_text(
        left + 16,
        detail_title_top,
        text=detail_title,
        anchor=tkinter.W,
        fill=button_text,
        font=("Yu Gothic UI", 10, "bold"),
    )

    canvas.create_text(
        left + 16,
        detail_body_top,
        text=detail_body,
        anchor=tkinter.NW,
        width=max(right - left - 32, 40),
        fill=text_muted,
        font=("Yu Gothic UI", 9),
    )


def _draw_visible_tiles(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    samples: Sequence[int],
    title: str,
    visible_count_kind: str,
    left: float,
    top: float,
    right: float,
    bottom: float,
    text_muted: str,
    inferred_incremented_samples: Sequence[int] = (),
) -> None:
    """Draw visible tiles in a fixed 8-column grid inside the shared detail display space."""
    normalized_samples = _normalize_visible_display_tiles(samples)
    inferred_incremented_set = frozenset(
        tile_id
        for tile_id in _normalize_visible_display_tiles(inferred_incremented_samples)
        if tile_id in normalized_samples
    )
    # まずセクション見出しを描く。
    canvas.create_text(
        left,
        top,
        text=title,
        anchor=tkinter.NW,
        fill=text_muted,
        font=("Yu Gothic UI", 8, "bold"),
    )
    # 対象牌が無いときはハイフンだけ出して早期 return する。
    if not normalized_samples:
        canvas.create_text(
            left,
            top + 20,
            text="-",
            anchor=tkinter.NW,
            fill=text_muted,
            font=("Consolas", 10, "bold"),
        )
        return

    # 実牌画像を読み込み、詳細パネル用に縮小した PhotoImage を作る。
    tiles_dir = _resolve_tiles_dir()
    detail_images: list[ImageTk.PhotoImage] = []
    for tile_id in normalized_samples[: DETAIL_VISIBLE_COLUMNS * DETAIL_VISIBLE_ROWS]:
        asset_tile_id = logical_tile_id_to_asset_tile_id(tile_id)
        tile_path = tiles_dir / f"{asset_tile_id}.png"
        tile_image = Image.open(tile_path).convert("RGB")
        tile_image.thumbnail((DETAIL_TILE_MAX_WIDTH, DETAIL_TILE_MAX_HEIGHT), Image.Resampling.LANCZOS)
        detail_images.append(ImageTk.PhotoImage(tile_image, master=canvas))
    if not detail_images:
        canvas.create_text(
            left,
            top + 20,
            text="-",
            anchor=tkinter.NW,
            fill=text_muted,
            font=("Consolas", 10, "bold"),
        )
        return
    # Tk 側のGCで画像が消えないよう Canvas に参照を積む。
    if not hasattr(canvas, "detail_images"):
        canvas.detail_images = []
    canvas.detail_images.extend(detail_images)

    # 8列固定で、行間は与えられた高さに収まるよう調整する。
    grid_top = top + 16
    available_width = max(right - left, 40)
    available_height = max(bottom - grid_top, DETAIL_TILE_MAX_HEIGHT)
    max_image_width = max(image.width() for image in detail_images)
    column_gap = max((available_width - max_image_width * DETAIL_VISIBLE_COLUMNS) / max(DETAIL_VISIBLE_COLUMNS - 1, 1), 2)
    if DETAIL_VISIBLE_ROWS <= 1:
        row_gap = 0
    else:
        row_gap = max(
            2,
            min(
                4,
                int((available_height - DETAIL_TILE_MAX_HEIGHT * DETAIL_VISIBLE_ROWS) / (DETAIL_VISIBLE_ROWS - 1)),
            ),
        )
    for index, image in enumerate(detail_images):
        col = index % DETAIL_VISIBLE_COLUMNS
        row = index // DETAIL_VISIBLE_COLUMNS
        if row >= DETAIL_VISIBLE_ROWS:
            break
        x = left + col * (max_image_width + column_gap)
        y = grid_top + row * (DETAIL_TILE_MAX_HEIGHT + row_gap)
        tile_border_color = _detail_visible_tile_border_color(
            normalized_samples[index],
            visible_count_kind,
            inferred_incremented=normalized_samples[index] in inferred_incremented_set,
        )
        canvas.create_image(
            x,
            y,
            image=image,
            anchor=tkinter.NW,
        )
        if tile_border_color is not None:
            canvas.create_rectangle(
                x - 1,
                y - 1,
                x + image.width() + 1,
                y + image.height() + 1,
                outline=tile_border_color,
                width=2,
            )


def _detail_visible_tile_border_color(
    tile_34: int,
    visible_count_kind: str,
    *,
    inferred_incremented: bool = False,
) -> str | None:
    """Return the right-detail visible-tile border color for suited `3..7` samples only."""

    if inferred_incremented:
        return INFERRED_VISIBLE_DETAIL_BORDER
    if tile_34 not in VISIBLE_TILE_IDS_34:
        return None
    suit = tile_34 // 10
    number = tile_34 % 10
    if suit not in (0, 1, 2) or not 3 <= number <= 7:
        return None
    if visible_count_kind == "three":
        return THREE_VISIBLE_DISCARD_MARKER
    if visible_count_kind == "four":
        return FOUR_VISIBLE_DISCARD_MARKER
    return None


def _normalize_visible_display_tiles(samples: Sequence[int]) -> list[int]:
    """Normalize visible-tile display ids to representative non-red ids."""

    normalized_tiles: list[int] = []
    seen_tiles: set[int] = set()
    for tile_id in samples:
        if tile_id not in VISIBLE_TILE_IDS_34 or tile_id in seen_tiles:
            continue
        seen_tiles.add(tile_id)
        normalized_tiles.append(tile_id)
    return normalized_tiles


def _merge_visible_detail_samples(
    actual_samples: Sequence[int],
    inferred_samples: Sequence[int],
) -> tuple[list[int], frozenset[int]]:
    """Return actual/inferred merged display tiles plus the inference-only subset."""

    normalized_actual = _normalize_visible_display_tiles(actual_samples)
    normalized_inferred = _normalize_visible_display_tiles(inferred_samples)
    actual_set = set(normalized_actual)
    merged_samples = list(normalized_actual)
    for tile_id in normalized_inferred:
        if tile_id in actual_set or tile_id in merged_samples:
            continue
        merged_samples.append(tile_id)
    return merged_samples, frozenset(
        tile_id for tile_id in normalized_inferred if tile_id not in actual_set
    )


def _format_inferred_visible_amount(value: float) -> str:
    """Format one inferred visible-count float for compact UI display."""

    rounded_value = round(max(0.0, float(value)), 1)
    return f"+{rounded_value:.1f}".rstrip("0").rstrip(".")


def _inferred_visible_tile_image(
    canvas: tkinter.Canvas,
    tile_37: int,
) -> tkinter.PhotoImage | None:
    """Return one compact tile image for inferred visible-count cards."""

    if not 1 <= int(tile_37) <= N_TILES:
        return None
    tile_scale = max(
        0.45,
        min(0.9, getattr(canvas, "current_ui_scale", 1.0) * INFERRED_VISIBLE_TILE_SCALE),
    )
    cache_key = (int(tile_37), round(tile_scale, 3))
    cache: dict[tuple[int, float], tkinter.PhotoImage] = getattr(
        canvas,
        "inferred_visible_tile_image_cache",
        {},
    )
    cached_image = cache.get(cache_key)
    if cached_image is not None:
        return cached_image
    compact_image = build_tile_photoimage(
        canvas,
        int(tile_37),
        Player.JICHA,
        DrawType.TEDASHI,
        tile_scale=tile_scale,
    )
    cache[cache_key] = compact_image
    canvas.inferred_visible_tile_image_cache = cache
    return compact_image


def _draw_inferred_visible_entry_card(
    canvas: tkinter.Canvas,
    rect: tuple[float, float, float, float],
    entry: InferredVisibleEntry,
) -> None:
    """Draw one inferred-visible entry card and register its candidate buttons."""

    left, top, right, bottom = rect
    if right <= left or bottom <= top:
        return
    focused = len(entry.active_candidate_seats) == 1
    card_outline = INFERRED_VISIBLE_ACTIVE_OUTLINE if focused else INFERRED_VISIBLE_OUTLINE
    canvas.create_rectangle(
        left,
        top,
        right,
        bottom,
        fill=INFERRED_VISIBLE_FILL,
        outline=card_outline,
        width=2 if focused else 1,
    )
    manual_counts_by_tile34 = _normalize_inferred_visible_manual_counts_by_tile34(
        getattr(canvas, "inferred_visible_manual_counts_by_tile34", {})
    )
    manual_count = int(manual_counts_by_tile34.get(int(entry.tile_34_index), 0))
    delete_button_left = max(left + 8, right - INFERRED_VISIBLE_DELETE_BUTTON_WIDTH - 6)
    delete_button_top = top + 6
    delete_button_right = right - 6
    delete_button_bottom = delete_button_top + INFERRED_VISIBLE_BUTTON_HEIGHT
    _draw_detail_button(
        canvas,
        delete_button_left,
        delete_button_top,
        delete_button_right,
        delete_button_bottom,
        INFERRED_VISIBLE_BUTTON_OFF_FILL,
        INFERRED_VISIBLE_OUTLINE,
        INFERRED_VISIBLE_BUTTON_OFF_TEXT,
    )
    canvas.create_text(
        (delete_button_left + delete_button_right) / 2,
        (delete_button_top + delete_button_bottom) / 2,
        text="削除",
        fill=INFERRED_VISIBLE_BUTTON_OFF_TEXT,
        font=("Yu Gothic UI", 7, "bold"),
    )
    canvas.inferred_visible_delete_button_specs.append(
        InferredVisibleDeleteButtonSpec(
            entry_key=entry.key,
            rect=(delete_button_left, delete_button_top, delete_button_right, delete_button_bottom),
        )
    )
    tile_image = _inferred_visible_tile_image(canvas, entry.tile_37)
    text_left = left + 8
    text_right = delete_button_left - 6
    if tile_image is not None:
        tile_left = left + 8
        tile_top = top + 6
        canvas.create_image(
            tile_left,
            tile_top,
            image=tile_image,
            anchor=tkinter.NW,
        )
        text_left = left + tile_image.width() + 14
        canvas.create_text(
            tile_left + tile_image.width() / 2,
            tile_top + tile_image.height() + 2,
            text=f"x{manual_count}",
            anchor=tkinter.N,
            fill=INFERRED_VISIBLE_MUTED_TEXT,
            font=("Consolas", 8, "bold"),
        )
        canvas.inferred_visible_tile_count_click_specs.append(
            InferredVisibleTileCountClickSpec(
                tile_34_index=int(entry.tile_34_index),
                rect=(tile_left, tile_top, tile_left + tile_image.width(), tile_top + tile_image.height()),
            )
        )
    text_left = min(text_left, text_right)
    canvas.create_text(
        text_left,
        top + 8,
        text=_format_inferred_visible_amount(entry.total_adjustment),
        anchor=tkinter.NW,
        fill=INFERRED_VISIBLE_TEXT,
        font=("Consolas", 9, "bold"),
    )
    seat_label_text = " / ".join(
        INFERRED_VISIBLE_LABEL_BY_SEAT.get(int(seat), str(seat))
        for seat in entry.active_candidate_seats
    ) or "-"
    canvas.create_text(
        text_left,
        top + 24,
        text=seat_label_text,
        anchor=tkinter.NW,
        fill=INFERRED_VISIBLE_MUTED_TEXT,
        font=("Yu Gothic UI", 7, "bold"),
    )

    candidate_count = max(len(entry.candidate_seats), 1)
    button_available_width = max(right - text_left - 8, 72)
    button_width = max(
        34.0,
        (button_available_width - INFERRED_VISIBLE_BUTTON_GAP * (candidate_count - 1)) / candidate_count,
    )
    button_top = max(top + 6, bottom - INFERRED_VISIBLE_BUTTON_HEIGHT - 6)
    current_left = text_left
    for seat in entry.candidate_seats:
        is_active = seat in entry.active_candidate_seats
        is_revealed = seat in entry.revealed_candidate_seats
        button_right = min(right - 6, current_left + button_width)
        current_fill = (
            INFERRED_VISIBLE_BUTTON_ACTIVE_FILL
            if is_active
            else INFERRED_VISIBLE_BUTTON_OFF_FILL
        )
        current_outline = (
            "#facc15"
            if is_revealed
            else (INFERRED_VISIBLE_ACTIVE_OUTLINE if focused and is_active else INFERRED_VISIBLE_OUTLINE)
        )
        current_text = (
            INFERRED_VISIBLE_TEXT
            if is_active
            else INFERRED_VISIBLE_BUTTON_OFF_TEXT
        )
        _draw_detail_button(
            canvas,
            current_left,
            button_top,
            button_right,
            button_top + INFERRED_VISIBLE_BUTTON_HEIGHT,
            current_fill,
            current_outline,
            current_text,
        )
        canvas.create_text(
            (current_left + button_right) / 2,
            button_top + INFERRED_VISIBLE_BUTTON_HEIGHT / 2,
            text=INFERRED_VISIBLE_LABEL_BY_SEAT.get(int(seat), str(seat)),
            fill=current_text,
            font=("Yu Gothic UI", 7, "bold"),
        )
        canvas.inferred_visible_candidate_button_specs.append(
            InferredVisibleCandidateButtonSpec(
                entry_key=entry.key,
                seat=int(seat),
                all_candidate_seats=tuple(int(candidate_seat) for candidate_seat in entry.candidate_seats),
                rect=(current_left, button_top, button_right, button_top + INFERRED_VISIBLE_BUTTON_HEIGHT),
            )
        )
        current_left = button_right + INFERRED_VISIBLE_BUTTON_GAP


def _selected_inferred_visible_tile37(
    canvas: tkinter.Canvas,
    entries: Sequence[InferredVisibleEntry],
) -> int | None:
    """Return the 37-kind tile id used by the selected inferred-visible popup header."""

    selected_tile_37 = getattr(canvas, "selected_inferred_visible_tile_37", None)
    selected_tile_34_index = getattr(canvas, "selected_inferred_visible_tile_34_index", None)
    if tile37_to_tile34_index(selected_tile_37) == selected_tile_34_index:
        return int(selected_tile_37)
    for entry in entries:
        if int(entry.tile_34_index) == int(selected_tile_34_index):
            return int(entry.tile_37)
    return _canonical_tile37_from_tile34_index(selected_tile_34_index)


def _draw_selected_inferred_visible_tile_card(
    canvas: tkinter.Canvas,
    rect: tuple[float, float, float, float],
    entries: Sequence[InferredVisibleEntry],
) -> None:
    """Draw one compact header card for the currently selected inferred-visible tile kind."""

    selected_tile_34_index = getattr(canvas, "selected_inferred_visible_tile_34_index", None)
    if selected_tile_34_index is None:
        return
    left, top, right, bottom = rect
    if right <= left or bottom <= top:
        return
    canvas.create_rectangle(
        left,
        top,
        right,
        bottom,
        fill=INFERRED_VISIBLE_FILL,
        outline=INFERRED_VISIBLE_ACTIVE_OUTLINE,
        width=2,
    )
    delete_button_left = max(left + 8, right - INFERRED_VISIBLE_DELETE_BUTTON_WIDTH - 6)
    delete_button_top = top + 6
    delete_button_right = right - 6
    delete_button_bottom = delete_button_top + INFERRED_VISIBLE_BUTTON_HEIGHT
    _draw_detail_button(
        canvas,
        delete_button_left,
        delete_button_top,
        delete_button_right,
        delete_button_bottom,
        INFERRED_VISIBLE_BUTTON_OFF_FILL,
        INFERRED_VISIBLE_OUTLINE,
        INFERRED_VISIBLE_BUTTON_OFF_TEXT,
    )
    canvas.create_text(
        (delete_button_left + delete_button_right) / 2,
        (delete_button_top + delete_button_bottom) / 2,
        text="削除",
        fill=INFERRED_VISIBLE_BUTTON_OFF_TEXT,
        font=("Yu Gothic UI", 7, "bold"),
    )
    canvas.selected_inferred_visible_delete_button_specs.append(
        InferredVisibleSelectedTileDeleteButtonSpec(
            rect=(delete_button_left, delete_button_top, delete_button_right, delete_button_bottom)
        )
    )
    selected_tile_37 = _selected_inferred_visible_tile37(canvas, entries)
    manual_counts_by_tile34 = _normalize_inferred_visible_manual_counts_by_tile34(
        getattr(canvas, "inferred_visible_manual_counts_by_tile34", {})
    )
    popup_disabled_seats_by_tile34 = _normalize_selected_inferred_visible_disabled_seats_by_tile34(
        getattr(canvas, "selected_inferred_visible_disabled_seats_by_tile34", {})
    )
    manual_count = int(manual_counts_by_tile34.get(int(selected_tile_34_index), 0))
    tile_image = _inferred_visible_tile_image(canvas, selected_tile_37)
    text_left = left + 8
    if tile_image is not None:
        tile_left = left + 8
        tile_top = top + 6
        canvas.create_image(
            tile_left,
            tile_top,
            image=tile_image,
            anchor=tkinter.NW,
        )
        canvas.create_text(
            tile_left + tile_image.width() / 2,
            tile_top + tile_image.height() + 2,
            text=f"x{manual_count}",
            anchor=tkinter.N,
            fill=INFERRED_VISIBLE_MUTED_TEXT,
            font=("Consolas", 8, "bold"),
        )
        canvas.inferred_visible_tile_count_click_specs.append(
            InferredVisibleTileCountClickSpec(
                tile_34_index=int(selected_tile_34_index),
                rect=(tile_left, tile_top, tile_left + tile_image.width(), tile_top + tile_image.height()),
            )
        )
        text_left = left + tile_image.width() + 14
    display_amount = manual_count + sum(float(entry.total_adjustment) for entry in entries)
    popup_active_seats = tuple(
        seat
        for seat in (
            int(Player.KAMICHA),
            int(Player.TOIMEN),
            int(Player.SHIMOCHA),
        )
        if int(seat) not in popup_disabled_seats_by_tile34.get(int(selected_tile_34_index), set())
    )
    seat_label_text = " / ".join(
        INFERRED_VISIBLE_LABEL_BY_SEAT.get(int(seat), str(seat))
        for seat in popup_active_seats
    ) or "候補なし"
    canvas.create_text(
        text_left,
        top + 8,
        text=_format_inferred_visible_amount(display_amount),
        anchor=tkinter.NW,
        fill=INFERRED_VISIBLE_TEXT,
        font=("Consolas", 9, "bold"),
    )
    candidate_button_top = top + 24
    if _draw_selected_inferred_visible_candidate_buttons(
        canvas,
        entries,
        tile_34_index=int(selected_tile_34_index),
        left=text_left,
        top=candidate_button_top,
        max_right=right - 8,
    ):
        seat_label_top = candidate_button_top + INFERRED_VISIBLE_BUTTON_HEIGHT + 2
    else:
        seat_label_top = top + 24
    canvas.create_text(
        text_left,
        seat_label_top,
        text=seat_label_text,
        anchor=tkinter.NW,
        fill=INFERRED_VISIBLE_MUTED_TEXT,
        font=("Yu Gothic UI", 7, "bold"),
    )
    _draw_inferred_visible_manual_count_buttons(
        canvas,
        int(selected_tile_34_index),
        left=left + 8,
        top=top + 64,
        max_right=right - 8,
    )


def _draw_selected_inferred_visible_candidate_buttons(
    canvas: tkinter.Canvas,
    entries: Sequence[InferredVisibleEntry],
    *,
    tile_34_index: int,
    left: float,
    top: float,
    max_right: float,
) -> bool:
    """Draw aggregate 上家/対面/下家 toggle buttons for the selected tile popup."""

    candidate_seats = (
        int(Player.KAMICHA),
        int(Player.TOIMEN),
        int(Player.SHIMOCHA),
    )
    popup_entry_key = _selected_inferred_visible_popup_entry_key(canvas, int(tile_34_index))
    popup_disabled_seats_by_tile34 = _normalize_selected_inferred_visible_disabled_seats_by_tile34(
        getattr(canvas, "selected_inferred_visible_disabled_seats_by_tile34", {})
    )
    popup_disabled_seats = set(popup_disabled_seats_by_tile34.get(int(tile_34_index), set()))
    actual_exclusions_by_entry = {
        tuple(key): {int(seat) for seat in seats}
        for key, seats in getattr(canvas, "inferred_visible_entry_excluded_seats", {}).items()
    }
    available_width = max(max_right - left, 72.0)
    button_count = len(candidate_seats)
    button_width = max(
        34.0,
        (available_width - INFERRED_VISIBLE_BUTTON_GAP * max(button_count - 1, 0)) / button_count,
    )
    current_left = left
    for seat in candidate_seats:
        actual_entry_keys = tuple(
            tuple(entry.key)
            for entry in entries
            if int(seat) in entry.candidate_seats
        )
        seat_entry_keys = actual_entry_keys if actual_entry_keys else (popup_entry_key,)
        if int(seat) in popup_disabled_seats:
            is_active = False
        elif actual_entry_keys:
            is_active = any(
                int(seat) not in actual_exclusions_by_entry.get(tuple(entry_key), set())
                for entry_key in actual_entry_keys
            )
        else:
            is_active = True
        is_revealed = any(int(seat) in entry.revealed_candidate_seats for entry in entries)
        button_right = min(max_right, current_left + button_width)
        current_fill = (
            INFERRED_VISIBLE_BUTTON_ACTIVE_FILL
            if is_active
            else INFERRED_VISIBLE_BUTTON_OFF_FILL
        )
        current_outline = "#facc15" if is_revealed else INFERRED_VISIBLE_OUTLINE
        current_text = INFERRED_VISIBLE_TEXT if is_active else INFERRED_VISIBLE_BUTTON_OFF_TEXT
        _draw_detail_button(
            canvas,
            current_left,
            top,
            button_right,
            top + INFERRED_VISIBLE_BUTTON_HEIGHT,
            current_fill,
            current_outline,
            current_text,
        )
        canvas.create_text(
            (current_left + button_right) / 2,
            top + INFERRED_VISIBLE_BUTTON_HEIGHT / 2,
            text=INFERRED_VISIBLE_LABEL_BY_SEAT.get(int(seat), str(seat)),
            fill=current_text,
            font=("Yu Gothic UI", 7, "bold"),
        )
        canvas.inferred_visible_candidate_button_specs.append(
            InferredVisibleCandidateButtonSpec(
                entry_key=seat_entry_keys[0],
                seat=int(seat),
                all_candidate_seats=tuple(int(candidate_seat) for candidate_seat in candidate_seats),
                rect=(current_left, top, button_right, top + INFERRED_VISIBLE_BUTTON_HEIGHT),
                entry_keys=seat_entry_keys,
            )
        )
        current_left = button_right + INFERRED_VISIBLE_BUTTON_GAP
    return True


def _draw_inferred_visible_manual_count_buttons(
    canvas: tkinter.Canvas,
    tile_34_index: int,
    *,
    left: float,
    top: float,
    max_right: float,
) -> None:
    """Draw compact `x0..x4` direct-set buttons for one selected inferred-visible tile."""

    manual_counts_by_tile34 = _normalize_inferred_visible_manual_counts_by_tile34(
        getattr(canvas, "inferred_visible_manual_counts_by_tile34", {})
    )
    current_count = int(manual_counts_by_tile34.get(int(tile_34_index), 0))
    current_left = float(left)
    for count in range(5):
        button_left = current_left
        button_right = button_left + INFERRED_VISIBLE_MANUAL_BUTTON_WIDTH
        if button_right > max_right:
            break
        is_active = int(count) == current_count
        current_fill = (
            INFERRED_VISIBLE_BUTTON_ACTIVE_FILL
            if is_active
            else INFERRED_VISIBLE_BUTTON_OFF_FILL
        )
        current_text = (
            INFERRED_VISIBLE_TEXT
            if is_active
            else INFERRED_VISIBLE_BUTTON_OFF_TEXT
        )
        _draw_detail_button(
            canvas,
            button_left,
            top,
            button_right,
            top + INFERRED_VISIBLE_BUTTON_HEIGHT,
            current_fill,
            INFERRED_VISIBLE_ACTIVE_OUTLINE if is_active else INFERRED_VISIBLE_OUTLINE,
            current_text,
        )
        canvas.create_text(
            (button_left + button_right) / 2,
            top + INFERRED_VISIBLE_BUTTON_HEIGHT / 2,
            text=f"x{count}",
            fill=current_text,
            font=("Consolas", 7, "bold"),
        )
        canvas.inferred_visible_manual_count_button_specs.append(
            InferredVisibleManualCountButtonSpec(
                tile_34_index=int(tile_34_index),
                count=int(count),
                rect=(button_left, top, button_right, top + INFERRED_VISIBLE_BUTTON_HEIGHT),
            )
        )
        current_left = button_right + INFERRED_VISIBLE_MANUAL_BUTTON_GAP


def _draw_inferred_visible_entry_stack(
    canvas: tkinter.Canvas,
    rect: tuple[float, float, float, float],
    entries: Sequence[InferredVisibleEntry],
    *,
    horizontal: bool,
) -> None:
    """Draw one stack of inferred-visible cards inside the given rectangle."""

    if not entries:
        return
    left, top, right, bottom = rect
    if right <= left or bottom <= top:
        return
    count = len(entries)
    gap = INFERRED_VISIBLE_SECTION_GAP
    if horizontal:
        available_width = max(right - left - gap * max(count - 1, 0), 1.0)
        card_width = max(96.0, available_width / count)
        current_left = left
        for entry in entries:
            card_right = min(right, current_left + card_width)
            _draw_inferred_visible_entry_card(
                canvas,
                (current_left, top, card_right, bottom),
                entry,
            )
            current_left = card_right + gap
        return
    available_height = max(bottom - top - gap * max(count - 1, 0), 1.0)
    card_height = max(48.0, available_height / count)
    current_top = top
    for entry in entries:
        card_bottom = min(bottom, current_top + card_height)
        _draw_inferred_visible_entry_card(
            canvas,
            (left, current_top, right, card_bottom),
            entry,
        )
        current_top = card_bottom + gap


def _draw_inferred_visible_sections(
    canvas: tkinter.Canvas,
    layout: Mapping[str, object],
    entries: Sequence[InferredVisibleEntry],
) -> None:
    """Draw the self-side inferred list and focused per-player inferred cards."""

    canvas.inferred_visible_candidate_button_specs = []
    canvas.inferred_visible_tile_count_click_specs = []
    canvas.inferred_visible_manual_count_button_specs = []
    canvas.inferred_visible_delete_button_specs = []
    canvas.selected_inferred_visible_delete_button_specs = []
    if not _inferred_visible_runtime_enabled(canvas):
        return
    filtered_entries = _filter_inferred_visible_entries_for_display(canvas, entries)
    self_entries = [
        entry
        for entry in filtered_entries
        if len(entry.active_candidate_seats) != 1
    ]
    focused_entries_by_seat: dict[int, list[InferredVisibleEntry]] = {}
    for entry in filtered_entries:
        if len(entry.active_candidate_seats) != 1:
            continue
        focused_entries_by_seat.setdefault(int(entry.active_candidate_seats[0]), []).append(entry)

    self_rect = layout.get("self_inference_rect")
    if isinstance(self_rect, tuple) and len(self_rect) == 4:
        selected_tile_34_index = getattr(canvas, "selected_inferred_visible_tile_34_index", None)
        if selected_tile_34_index is not None:
            selected_card_height = min(
                float(INFERRED_VISIBLE_SELECTED_TILE_CARD_HEIGHT),
                max(1.0, self_rect[3] - self_rect[1]),
            )
            selected_card_rect = (
                self_rect[0],
                self_rect[1],
                self_rect[2],
                min(self_rect[3], self_rect[1] + selected_card_height),
            )
            _draw_selected_inferred_visible_tile_card(canvas, selected_card_rect, filtered_entries)
            remaining_rect = (
                self_rect[0],
                min(self_rect[3], selected_card_rect[3] + INFERRED_VISIBLE_SECTION_GAP),
                self_rect[2],
                self_rect[3],
            )
            if remaining_rect[3] > remaining_rect[1]:
                _draw_inferred_visible_entry_stack(
                    canvas,
                    remaining_rect,
                    self_entries,
                    horizontal=False,
                )
        else:
            _draw_inferred_visible_entry_stack(
                canvas,
                self_rect,
                self_entries,
                horizontal=False,
            )

    player_rects = layout.get("player_inference_rects", {})
    if not isinstance(player_rects, Mapping):
        return
    for seat, seat_entries in focused_entries_by_seat.items():
        rect = player_rects.get(int(seat))
        if not isinstance(rect, tuple) or len(rect) != 4:
            continue
        horizontal = (rect[2] - rect[0]) >= (rect[3] - rect[1])
        _draw_inferred_visible_entry_stack(
            canvas,
            rect,
            seat_entries,
            horizontal=horizontal,
        )


def _draw_center_panel(
    canvas: tkinter.Canvas,
    rect: tuple[float, float, float, float],
    dora_indicator_tiles: Sequence[int],
    round_info_panel: RoundInfoPanelData,
) -> None:
    """卓中央の局情報パネルを描く。"""
    left, top, right, bottom = rect
    center_x = (left + right) / 2
    canvas.create_rectangle(left + 3, top + 4, right + 3, bottom + 4, fill=SHADOW, outline="")
    canvas.create_rectangle(left, top, right, bottom, fill=CENTER_PANEL, outline=CENTER_PANEL_BORDER, width=2)
    # 中央パネルは固定文言ではなく、現在局の情報をそのまま表示する。
    canvas.create_text(
        center_x,
        top + 18,
        text=round_info_panel.round_text,
        fill=TEXT_PRIMARY,
        font=("Yu Gothic UI", 11, "bold"),
    )
    if round_info_panel.bootstrap_text:
        canvas.create_text(
            center_x,
            top + 36,
            text=round_info_panel.bootstrap_text,
            fill=TEXT_SECONDARY,
            font=("Consolas", 7, "bold"),
        )
    dora_label_y = top + (58 if round_info_panel.bootstrap_text else 50)
    dora_tiles_y = dora_label_y + 19
    canvas.create_text(center_x, dora_label_y, text="DORA", fill=TEXT_SECONDARY, font=("Consolas", 9, "bold"))
    _draw_center_dora_tiles(canvas, center_x, dora_tiles_y, dora_indicator_tiles)
    canvas.create_text(center_x, bottom - 22, text="KYOTAKU", fill=TEXT_SECONDARY, font=("Consolas", 8, "bold"))
    canvas.create_text(
        center_x,
        bottom - 8,
        text=round_info_panel.kyotaku_text,
        fill="#dbeafe",
        font=("Consolas", 10, "bold"),
    )


def _draw_center_dora_tiles(
    canvas: tkinter.Canvas,
    center_x: float,
    center_y: float,
    dora_indicator_tiles: Sequence[int],
) -> None:
    """Draw dora indicator tile images inside the center information panel."""

    if not dora_indicator_tiles:
        canvas.create_text(
            center_x,
            center_y,
            text="-",
            fill=TEXT_PRIMARY,
            font=("Consolas", 11, "bold"),
        )
        return

    tiles_dir = _resolve_tiles_dir()
    dora_images: list[ImageTk.PhotoImage] = []
    for tile_id in dora_indicator_tiles[:5]:
        asset_tile_id = logical_tile_id_to_asset_tile_id(tile_id)
        tile_path = tiles_dir / f"{asset_tile_id}.png"
        tile_image = Image.open(tile_path).convert("RGB")
        tile_image.thumbnail((CENTER_DORA_MAX_WIDTH, CENTER_DORA_MAX_HEIGHT), Image.Resampling.LANCZOS)
        dora_images.append(ImageTk.PhotoImage(tile_image, master=canvas))

    canvas.center_panel_images.extend(dora_images)

    total_width = sum(image.width() for image in dora_images)
    gap = 4
    if len(dora_images) > 1:
        total_width += gap * (len(dora_images) - 1)
    x = center_x - total_width / 2

    for image in dora_images:
        canvas.create_image(
            x,
            center_y - image.height() / 2,
            image=image,
            anchor=tkinter.NW,
        )
        x += image.width() + gap


def _draw_seat_labels(
    canvas: tkinter.Canvas,
    layout: dict[str, object],
    round_info_panel: RoundInfoPanelData | None = None,
) -> None:
    """捨て牌エリア中央の座席ラベルを描く。"""
    discard_rects = layout["discard_rects"]
    # 各捨て牌エリア矩形の中心点を座席ラベルの描画位置に使う。
    seat_centers = {player: ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2) for player, rect in discard_rects.items()}
    # 座席 enum と表示ラベルの対応表。
    seat_labels = {
        Player.JICHA: "YOU",
        Player.SHIMOCHA: "SHIMO",
        Player.TOIMEN: "TOIMEN",
        Player.KAMICHA: "KAMI",
    }
    seat_wind_labels_by_seat = (
        dict(getattr(round_info_panel, "seat_wind_labels_by_seat", {}))
        if round_info_panel is not None
        else {}
    )
    for player, label in seat_labels.items():
        sx, sy = seat_centers[player]
        seat_wind_label = str(seat_wind_labels_by_seat.get(int(player), "")).strip()
        label_y = sy - 7 if seat_wind_label else sy
        canvas.create_text(
            sx,
            label_y,
            text=label,
            fill=TEXT_SECONDARY,
            font=("Yu Gothic UI", 11, "bold"),
        )
        if seat_wind_label:
            canvas.create_text(
                sx,
                sy + 9,
                text=seat_wind_label,
                fill="#dbe7f3",
                font=("Yu Gothic UI", 9, "bold"),
            )


def _draw_meld_zones(
    canvas: tkinter.Canvas,
    layout: dict[str, object],
) -> None:
    """鳴き表示用の帯領域を描く。"""

    for left, top, right, bottom in layout["meld_rects"].values():
        if right <= left or bottom <= top:
            continue
        canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill=MELD_ZONE_FILL,
            outline=MELD_ZONE_OUTLINE,
            width=1,
        )


def _draw_discard_zones(
    canvas: tkinter.Canvas,
    layout: dict[str, object],
) -> None:
    """Draw rectangular discard zones for all four seats."""
    # 4人分すべての捨て牌エリア枠を描く。
    for left, top, right, bottom in layout["discard_rects"].values():
        canvas.create_rectangle(left, top, right, bottom, fill=ZONE_FILL, outline=ZONE_OUTLINE, width=1)


def _image_bounds_from_anchor(
    x: float,
    y: float,
    width: int,
    height: int,
    anchor: str,
) -> tuple[float, float, float, float]:
    """Return image bounds for a Tk anchor-based image placement."""

    if anchor == tkinter.NW:
        return x, y, x + width, y + height
    if anchor == tkinter.NE:
        return x - width, y, x, y + height
    if anchor == tkinter.SW:
        return x, y - height, x + width, y
    if anchor == tkinter.SE:
        return x - width, y - height, x, y
    return x, y, x + width, y + height


def _discard_marker_layout(
    player: Player,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> tuple[int, tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Return the shared marker size plus visible-count/same-jun/lag centers for a discard tile."""

    base_radius = max(3.0, min(right - left, bottom - top) * 0.11)
    marker_radius = max(3, int(round(base_radius * 1.25)))
    marker_margin = max(4, int(round(marker_radius * 1.15)))
    width = right - left
    height = bottom - top
    top_edge_left_x = left + width * 0.22
    top_edge_center_x = left + width * 0.5
    top_edge_right_x = left + width * 0.78
    side_edge_upper_y = top + height * 0.22
    side_edge_center_y = top + height * 0.5
    side_edge_lower_y = top + height * 0.78
    marker_centers = {
        Player.JICHA: (
            (top_edge_right_x, top + marker_margin),
            (top_edge_center_x, top + marker_margin),
            (top_edge_left_x, top + marker_margin),
        ),
        Player.SHIMOCHA: (
            (left + marker_margin, side_edge_upper_y),
            (left + marker_margin, side_edge_center_y),
            (left + marker_margin, side_edge_lower_y),
        ),
        Player.TOIMEN: (
            (top_edge_left_x, bottom - marker_margin),
            (top_edge_center_x, bottom - marker_margin),
            (top_edge_right_x, bottom - marker_margin),
        ),
        Player.KAMICHA: (
            (right - marker_margin, side_edge_lower_y),
            (right - marker_margin, side_edge_center_y),
            (right - marker_margin, side_edge_upper_y),
        ),
    }
    visible_count_center, same_jun_center, lag_center = marker_centers[player]
    return marker_radius, visible_count_center, same_jun_center, lag_center


def _peak_thinking_time_discard_local_index(
    discards: Sequence[Discard],
) -> int | None:
    """Return the local discard index of one seat's longest-thought discard after the first turn."""

    best_index: int | None = None
    best_thinking_time_ms = 0.0
    for local_index, discard in enumerate(discards):
        if local_index == 0:
            continue
        if _is_riseki_completion_discard(discard):
            continue
        thinking_time_ms = getattr(discard, "thinking_time_ms", None)
        if thinking_time_ms is None:
            continue
        try:
            normalized_thinking_time_ms = float(thinking_time_ms)
        except (TypeError, ValueError):
            continue
        if normalized_thinking_time_ms <= 0.0:
            continue
        if (
            best_index is None
            or normalized_thinking_time_ms > best_thinking_time_ms
            or (
                abs(normalized_thinking_time_ms - best_thinking_time_ms) < 0.001
                and local_index > best_index
            )
        ):
            best_index = local_index
            best_thinking_time_ms = normalized_thinking_time_ms
    return best_index


def _discard_global_order_index(discard: Discard, fallback_index: int) -> int:
    """Return a stable global-order index for one discard."""

    round_discard_index = getattr(discard, "round_discard_index", None)
    if round_discard_index is not None:
        try:
            return int(round_discard_index)
        except (TypeError, ValueError):
            pass
    event_index = getattr(discard, "event_index", -1)
    if event_index is not None:
        try:
            normalized_event_index = int(event_index)
        except (TypeError, ValueError):
            normalized_event_index = -1
        if normalized_event_index >= 0:
            return normalized_event_index
    return fallback_index


def _discard_tile34_index(discard: object) -> int | None:
    """Return one discard's tile34 index across UI/live discard shapes."""

    direct_tile_34 = getattr(discard, "tile_34", None)
    if direct_tile_34 is not None:
        try:
            normalized_tile_34 = int(direct_tile_34)
        except (TypeError, ValueError):
            normalized_tile_34 = -1
        if 0 <= normalized_tile_34 < 34:
            return normalized_tile_34
    tile_id = getattr(discard, "tile_id", None)
    if tile_id is not None:
        try:
            return tile37_to_tile34_index(int(tile_id))
        except (TypeError, ValueError):
            return None
    tile_37 = getattr(discard, "tile_37", None)
    if tile_37 is None:
        tile_37 = getattr(discard, "ui_tile_37", None)
    if tile_37 is not None:
        try:
            return tile37_to_tile34_index(int(tile_37))
        except (TypeError, ValueError):
            return None
    tile_136 = getattr(discard, "tile_136", None)
    if tile_136 is not None:
        try:
            return tile136_to_tile34_index(int(tile_136))
        except (TypeError, ValueError):
            return None
    return None


def _event_global_order_index(event: object, fallback_index: int) -> int:
    """Return a stable global-order index for one round event."""

    event_index = getattr(event, "event_index", -1)
    if event_index is not None:
        try:
            normalized_event_index = int(event_index)
        except (TypeError, ValueError):
            normalized_event_index = -1
        if normalized_event_index >= 0:
            return normalized_event_index
    return fallback_index


def _coerce_awaseuchi_sequence(items: Iterable[object] | Sequence[object]) -> Sequence[object]:
    """Return a stable sequence view without eagerly copying common list/tuple inputs."""

    if isinstance(items, SequenceABC):
        return items
    return tuple(items)


def _awaseuchi_discard_event_entry(
    seat: int,
    local_index: int,
    discard: object,
    fallback_index: int,
) -> tuple[int, int, str, int | None, int | None, tuple[int, ...]]:
    """Return one normalized public-event entry for a discard."""

    tile_34_index = _discard_tile34_index(discard)
    tile_34_indices = (tile_34_index,) if tile_34_index is not None else ()
    return (
        _discard_global_order_index(discard, fallback_index),
        0,
        "discard",
        seat,
        local_index,
        tile_34_indices,
    )


def _awaseuchi_meld_event_entry(
    seat: int,
    meld: object,
) -> tuple[int, int, str, int | None, int | None, tuple[int, ...]] | None:
    """Return one normalized public-event entry for a meld exposure."""

    event_index = getattr(meld, "event_index", -1)
    try:
        order = int(event_index)
    except (TypeError, ValueError):
        order = -1
    if order < 0:
        return None
    consumed_tile_ids = list(getattr(meld, "consumed_tile_ids", ()) or ())
    newly_visible_tile_ids = [
        tile136_to_tile37(tile_136)
        for tile_136 in consumed_tile_ids
    ]
    if not newly_visible_tile_ids:
        newly_visible_tile_ids = list(getattr(meld, "tiles_37", ()) or ())
    tile_34_indices: set[int] = set()
    for tile_id in newly_visible_tile_ids:
        tile_34_index = tile37_to_tile34_index(int(tile_id)) if tile_id is not None else None
        if tile_34_index is not None:
            tile_34_indices.add(tile_34_index)
    if not tile_34_indices:
        return None
    return (
        order,
        1,
        "meld",
        seat,
        None,
        tuple(sorted(tile_34_indices)),
    )


def _awaseuchi_dora_event_entry(
    event: object,
    fallback_index: int,
) -> tuple[int, int, str, int | None, int | None, tuple[int, ...]] | None:
    """Return one normalized public-event entry for a dora reveal."""

    if str(getattr(event, "event_type", "")).lower() != "dora":
        return None
    tile_37 = tile136_to_tile37(getattr(event, "tile_136", None))
    tile_34_index = tile37_to_tile34_index(int(tile_37)) if tile_37 is not None else None
    if tile_34_index is None:
        return None
    return (
        _event_global_order_index(event, fallback_index),
        1,
        "dora",
        None,
        None,
        (tile_34_index,),
    )


def _same_jun_public_event_sort_key(
    item: tuple[int, int, str, int | None, int | None, tuple[int, ...]],
) -> tuple[int, int, str, int, int]:
    """Return the sort key used by awaseuchi public-event ordering."""

    return (
        item[0],
        item[1],
        item[2],
        -1 if item[3] is None else item[3],
        -1 if item[4] is None else item[4],
    )


def _same_jun_discard_last_signature(discard_sequence: Sequence[object]) -> tuple[object, ...] | None:
    """Return one cheap structural signature for the last discard in a seat."""

    if not discard_sequence:
        return None
    last_discard = discard_sequence[-1]
    round_discard_index = getattr(last_discard, "round_discard_index", None)
    event_index = getattr(last_discard, "event_index", None)
    try:
        normalized_round_discard_index = (
            None if round_discard_index is None else int(round_discard_index)
        )
    except (TypeError, ValueError):
        normalized_round_discard_index = None
    try:
        normalized_event_index = None if event_index is None else int(event_index)
    except (TypeError, ValueError):
        normalized_event_index = None
    return (
        _discard_tile34_index(last_discard),
        normalized_round_discard_index,
        normalized_event_index,
    )


def _same_jun_meld_last_signature(meld_sequence: Sequence[object]) -> tuple[object, ...] | None:
    """Return one cheap structural signature for the last meld exposure in a seat."""

    if not meld_sequence:
        return None
    last_meld = meld_sequence[-1]
    event_entry = _awaseuchi_meld_event_entry(0, last_meld)
    if event_entry is None:
        return (
            None,
            str(getattr(last_meld, "meld_type", "") or ""),
        )
    return (
        event_entry[0],
        event_entry[2],
        event_entry[5],
    )


def _same_jun_dora_last_signature(round_events: Sequence[object]) -> tuple[object, ...] | None:
    """Return one cheap structural signature for the last retained dora event."""

    if not round_events:
        return None
    last_event = round_events[-1]
    event_entry = _awaseuchi_dora_event_entry(last_event, len(round_events) - 1)
    if event_entry is None:
        return None
    return (
        event_entry[0],
        event_entry[5],
    )


def _same_jun_public_event_source_state(
    round_identity: object | None,
    discard_sequences_by_seat: Mapping[int, Sequence[object]],
    meld_sequences_by_seat: Mapping[int, Sequence[object]],
    round_events: Sequence[object],
) -> SameJunPublicEventSourceState:
    """Return one lightweight append-friendly source-state signature for live awaseuchi UI."""

    return SameJunPublicEventSourceState(
        round_identity=round_identity,
        discard_counts_by_seat=tuple(
            len(discard_sequences_by_seat.get(int(player), ()))
            for player in Player
        ),
        discard_last_signatures_by_seat=tuple(
            _same_jun_discard_last_signature(discard_sequences_by_seat.get(int(player), ()))
            for player in Player
        ),
        meld_counts_by_seat=tuple(
            len(meld_sequences_by_seat.get(int(player), ()))
            for player in Player
        ),
        meld_last_signatures_by_seat=tuple(
            _same_jun_meld_last_signature(meld_sequences_by_seat.get(int(player), ()))
            for player in Player
        ),
        dora_count=len(round_events),
        dora_last_signature=_same_jun_dora_last_signature(round_events),
    )


def _can_incrementally_extend_same_jun_public_state(
    previous_state: SameJunPublicEventSourceState | None,
    current_state: SameJunPublicEventSourceState,
) -> bool:
    """Return whether the current awaseuchi public state can extend the previous one by append."""

    if previous_state is None:
        return False
    if previous_state.round_identity != current_state.round_identity:
        return False
    if any(
        current_count < previous_count
        for previous_count, current_count in zip(
            previous_state.discard_counts_by_seat,
            current_state.discard_counts_by_seat,
        )
    ):
        return False
    if any(
        current_count < previous_count
        for previous_count, current_count in zip(
            previous_state.meld_counts_by_seat,
            current_state.meld_counts_by_seat,
        )
    ):
        return False
    if current_state.dora_count < previous_state.dora_count:
        return False
    for previous_count, current_count, previous_signature, current_signature in zip(
        previous_state.discard_counts_by_seat,
        current_state.discard_counts_by_seat,
        previous_state.discard_last_signatures_by_seat,
        current_state.discard_last_signatures_by_seat,
    ):
        if current_count == previous_count and current_signature != previous_signature:
            return False
    for previous_count, current_count, previous_signature, current_signature in zip(
        previous_state.meld_counts_by_seat,
        current_state.meld_counts_by_seat,
        previous_state.meld_last_signatures_by_seat,
        current_state.meld_last_signatures_by_seat,
    ):
        if current_count == previous_count and current_signature != previous_signature:
            return False
    if (
        current_state.dora_count == previous_state.dora_count
        and current_state.dora_last_signature != previous_state.dora_last_signature
    ):
        return False
    return True


def _discard_has_explicit_awaseuchi_order(discard: object) -> bool:
    """Return whether one discard can be appended safely without rebuilding awaseuchi history."""

    round_discard_index = getattr(discard, "round_discard_index", None)
    if round_discard_index is not None:
        try:
            int(round_discard_index)
            return True
        except (TypeError, ValueError):
            pass
    event_index = getattr(discard, "event_index", None)
    if event_index is not None:
        try:
            return int(event_index) >= 0
        except (TypeError, ValueError):
            return False
    return False


def _same_jun_candidate_state_from_event_stream(
    event_stream: Sequence[tuple[int, int, str, int | None, int | None, tuple[int, ...]]],
    *,
    recent_public_event_window: int = AWASEUCHI_PROVISIONAL_PUBLIC_EVENT_WINDOW,
) -> tuple[dict[int, frozenset[int]], tuple[tuple[str, int | None, tuple[int, ...]], ...]]:
    """Return provisional awaseuchi matches plus the recent-public tail needed for append updates."""

    recent_window = max(0, int(recent_public_event_window))
    if recent_window <= 0:
        return (
            {int(player): frozenset() for player in Player},
            (),
        )
    recent_public_events: deque[tuple[str, int | None, tuple[int, ...]]] = deque(maxlen=recent_window)
    candidate_matches_by_seat: dict[int, set[int]] = {int(player): set() for player in Player}
    for _order, _priority, event_kind, seat, local_index, tile_34_indices in event_stream:
        if event_kind == "discard" and seat is not None and local_index is not None:
            for recent_event_kind, recent_seat, recent_tile_34_indices in recent_public_events:
                if (
                    recent_event_kind in {"discard", "meld"}
                    and recent_seat is not None
                    and recent_seat == seat
                ):
                    continue
                if any(tile_34_index in recent_tile_34_indices for tile_34_index in tile_34_indices):
                    candidate_matches_by_seat[seat].add(local_index)
                    break
        recent_public_events.append((event_kind, seat, tile_34_indices))
    return (
        {
            seat: frozenset(local_indexes)
            for seat, local_indexes in candidate_matches_by_seat.items()
        },
        tuple(recent_public_events),
    )


def _extend_same_jun_candidate_state(
    previous_matches_by_seat: Mapping[int, Collection[int]] | None,
    previous_recent_public_events: Sequence[tuple[str, int | None, tuple[int, ...]]] | None,
    new_events: Sequence[tuple[int, int, str, int | None, int | None, tuple[int, ...]]],
    *,
    recent_public_event_window: int = AWASEUCHI_PROVISIONAL_PUBLIC_EVENT_WINDOW,
) -> tuple[dict[int, frozenset[int]], tuple[tuple[str, int | None, tuple[int, ...]], ...]]:
    """Extend provisional awaseuchi state using only newly appended public events."""

    recent_window = max(0, int(recent_public_event_window))
    if recent_window <= 0:
        return (
            {int(player): frozenset() for player in Player},
            (),
        )
    candidate_matches_by_seat: dict[int, set[int]] = {
        int(player): set(previous_matches_by_seat.get(int(player), ())) if previous_matches_by_seat else set()
        for player in Player
    }
    recent_public_events: deque[tuple[str, int | None, tuple[int, ...]]] = deque(
        previous_recent_public_events or (),
        maxlen=recent_window,
    )
    for _order, _priority, event_kind, seat, local_index, tile_34_indices in new_events:
        if event_kind == "discard" and seat is not None and local_index is not None:
            for recent_event_kind, recent_seat, recent_tile_34_indices in recent_public_events:
                if (
                    recent_event_kind in {"discard", "meld"}
                    and recent_seat is not None
                    and recent_seat == seat
                ):
                    continue
                if any(tile_34_index in recent_tile_34_indices for tile_34_index in tile_34_indices):
                    candidate_matches_by_seat[seat].add(local_index)
                    break
        recent_public_events.append((event_kind, seat, tile_34_indices))
    return (
        {
            seat: frozenset(local_indexes)
            for seat, local_indexes in candidate_matches_by_seat.items()
        },
        tuple(recent_public_events),
    )


def _same_jun_match_cache_signature(
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]] | None,
    round_events: Sequence[object] | None,
) -> tuple[object, ...]:
    """Return one structural signature so static redraws can reuse awaseuchi results."""

    discard_signature = tuple(
        (
            int(player),
            tuple(
                (
                    _discard_global_order_index(discard, local_index),
                    _discard_tile34_index(discard),
                )
                for local_index, discard in enumerate(discard_map.get(player, ()))
            ),
        )
        for player in Player
    )
    meld_signature = tuple(
        (
            int(player),
            tuple(
                (
                    int(getattr(meld, "event_index", -1)),
                    str(getattr(meld, "meld_type", "") or ""),
                    tuple(int(tile_34) for tile_34 in getattr(meld, "tiles_34", ()) or ()),
                    tuple(
                        int(tile_id)
                        for tile_id in getattr(meld, "consumed_tile_ids", ()) or ()
                    ),
                )
                for meld in (melds_by_player or {}).get(player, ())
            ),
        )
        for player in Player
    )
    dora_signature = tuple(
        (
            _event_global_order_index(event, fallback_index),
            tile136_to_tile34_index(getattr(event, "tile_136", None)),
        )
        for fallback_index, event in enumerate(round_events or ())
        if str(getattr(event, "event_type", "")).lower() == "dora"
    )
    return (discard_signature, meld_signature, dora_signature)


def _same_jun_public_event_stream(
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]] | None = None,
    round_events: Sequence[object] | None = None,
) -> tuple[tuple[int, int, str, int | None, int | None, tuple[int, ...]], ...]:
    """Return the sorted public visibility event stream used by awaseuchi checks."""

    normalized_discards_by_seat = {
        int(player): list(
            discard_map.get(player)
            if discard_map.get(player) is not None
            else discard_map.get(int(player), ())
        )
        for player in Player
    }
    normalized_melds_by_seat = {
        int(player): list(
            (melds_by_player or {}).get(player)
            if (melds_by_player or {}).get(player) is not None
            else (melds_by_player or {}).get(int(player), ())
        )
        for player in Player
    }
    event_stream: list[tuple[int, int, str, int | None, int | None, tuple[int, ...]]] = []
    fallback_index = 0
    for player in Player:
        seat = int(player)
        for local_index, discard in enumerate(normalized_discards_by_seat[seat]):
            event_stream.append(
                _awaseuchi_discard_event_entry(
                    seat,
                    local_index,
                    discard,
                    fallback_index,
                )
            )
            fallback_index += 1

    for seat, melds in normalized_melds_by_seat.items():
        for meld in melds:
            event_entry = _awaseuchi_meld_event_entry(seat, meld)
            if event_entry is not None:
                event_stream.append(event_entry)

    for fallback_index, event in enumerate(round_events or ()):
        event_entry = _awaseuchi_dora_event_entry(event, fallback_index)
        if event_entry is not None:
            event_stream.append(event_entry)

    event_stream.sort(key=_same_jun_public_event_sort_key)
    return tuple(event_stream)


def _same_jun_candidate_discard_indices_by_seat_from_event_stream(
    event_stream: Sequence[tuple[int, int, str, int | None, int | None, tuple[int, ...]]],
    *,
    recent_public_event_window: int = AWASEUCHI_PROVISIONAL_PUBLIC_EVENT_WINDOW,
) -> dict[int, frozenset[int]]:
    """Return provisional awaseuchi candidates using only the newest public events."""

    candidate_matches, _recent_public_tail = _same_jun_candidate_state_from_event_stream(
        event_stream,
        recent_public_event_window=recent_public_event_window,
    )
    return candidate_matches


def _same_jun_candidate_discard_indices_by_seat(
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]] | None = None,
    round_events: Sequence[object] | None = None,
    *,
    recent_public_event_window: int = AWASEUCHI_PROVISIONAL_PUBLIC_EVENT_WINDOW,
) -> dict[int, frozenset[int]]:
    """Return provisional awaseuchi candidates from the recent public event window."""

    return _same_jun_candidate_discard_indices_by_seat_from_event_stream(
        _same_jun_public_event_stream(discard_map, melds_by_player, round_events),
        recent_public_event_window=recent_public_event_window,
    )


def _same_jun_match_discard_indices_by_seat_cached(
    canvas: tkinter.Canvas,
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]] | None = None,
    round_events: Sequence[object] | None = None,
) -> dict[int, frozenset[int]]:
    """Reuse the last awaseuchi result while the same visible public state is on screen."""

    round_identity = getattr(canvas, "current_round_identity", None)
    cache_key: tuple[object, ...] = (
        round_identity,
        *_same_jun_match_cache_signature(discard_map, melds_by_player, round_events),
    )
    if getattr(canvas, "same_jun_match_cache_key", None) == cache_key:
        return getattr(canvas, "same_jun_match_cache_value", {})
    cached_value = _same_jun_match_discard_indices_by_seat(
        discard_map,
        melds_by_player,
        round_events,
    )
    canvas.same_jun_match_cache_key = cache_key
    canvas.same_jun_match_cache_value = cached_value
    return cached_value


def _same_jun_match_discard_indices_by_seat(
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]] | None = None,
    round_events: Sequence[object] | None = None,
) -> dict[int, frozenset[int]]:
    """Return confirmed awaseuchi matches using the full public event history."""

    return _same_jun_match_discard_indices_by_seat_from_event_stream(
        _same_jun_public_event_stream(discard_map, melds_by_player, round_events)
    )


def _same_jun_match_discard_indices_by_seat_from_event_stream(
    event_stream: Sequence[tuple[int, int, str, int | None, int | None, tuple[int, ...]]],
) -> dict[int, frozenset[int]]:
    """Return discards that match pending per-seat awaseuchi flags.

    Only publicly visible count increases arm flags: discards, newly exposed meld tiles,
    and dora-indicator reveals. Private draws are intentionally excluded.
    A player's own discard does not arm that same player's flag.
    Meld visibility is an exception: the acting player's own flag is not armed by that self-exposure.
    Visible-count increase events turn one tile34 flag on for every seat.
    Each seat keeps those flags only until its own next discard completes.
    When that discard matches any pending flag, the discard receives the awaseuchi marker,
    then the seat's pending flags are cleared.
    """
    pending_tile34_flags_by_seat: dict[int, set[int]] = {int(player): set() for player in Player}
    same_jun_matches_by_seat: dict[int, set[int]] = {int(player): set() for player in Player}
    all_seats = tuple(int(player) for player in Player)
    for _order, _priority, event_kind, seat, local_index, tile_34_indices in event_stream:
        if event_kind == "discard":
            if seat is None:
                continue
            current_pending_flags = pending_tile34_flags_by_seat[seat]
            # A seat checks the currently pending flags exactly when its discard completes.
            if local_index is not None and any(
                tile_34_index in current_pending_flags for tile_34_index in tile_34_indices
            ):
                same_jun_matches_by_seat[seat].add(local_index)
            # Regardless of match/miss, the seat's one-shot pending flags expire on this discard.
            current_pending_flags.clear()
            for tile_34_index in tile_34_indices:
                # A discard becomes publicly visible to every other seat, but not to the discarder.
                for target_seat in all_seats:
                    if target_seat == seat:
                        continue
                    pending_tile34_flags_by_seat[target_seat].add(tile_34_index)
            continue
        for tile_34_index in tile_34_indices:
            for target_seat in all_seats:
                # Meld self-exposure is already known to the acting seat, so only other seats arm here.
                if event_kind == "meld" and seat is not None and target_seat == seat:
                    continue
                pending_tile34_flags_by_seat[target_seat].add(tile_34_index)

    return {
        seat: frozenset(local_indexes)
        for seat, local_indexes in same_jun_matches_by_seat.items()
    }


def _same_jun_confirmation_cache_key(
    round_identity: object | None,
    event_stream: Sequence[tuple[int, int, str, int | None, int | None, tuple[int, ...]]],
) -> tuple[object, ...]:
    """Return one stable confirm key derived from the exact public event stream."""

    return (
        round_identity,
        tuple(event_stream),
    )


def _same_jun_marker_state_from_live_public_state(
    canvas: tkinter.Canvas,
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]] | None = None,
    round_events: Sequence[object] | None = None,
) -> tuple[
    SameJunPublicEventSourceState,
    tuple[tuple[int, int, str, int | None, int | None, tuple[int, ...]], ...],
    dict[int, frozenset[int]],
]:
    """Return append-updated public-event stream plus provisional awaseuchi markers."""

    round_identity = getattr(canvas, "current_round_identity", None)
    discard_sequences_by_seat = {
        int(player): _coerce_awaseuchi_sequence(discard_map.get(player, ()))
        for player in Player
    }
    meld_sequences_by_seat = {
        int(player): _coerce_awaseuchi_sequence((melds_by_player or {}).get(player, ()))
        for player in Player
    }
    normalized_round_events = _coerce_awaseuchi_sequence(round_events or ())
    current_state = _same_jun_public_event_source_state(
        round_identity,
        discard_sequences_by_seat,
        meld_sequences_by_seat,
        normalized_round_events,
    )
    previous_state = getattr(canvas, "same_jun_public_event_source_state", None)
    if previous_state == current_state:
        return (
            current_state,
            tuple(getattr(canvas, "same_jun_match_candidate_event_stream", ())),
            {
                int(seat): frozenset(local_indexes)
                for seat, local_indexes in getattr(
                    canvas,
                    "same_jun_match_candidate_cache_value",
                    {},
                ).items()
            },
        )

    can_incrementally_extend = _can_incrementally_extend_same_jun_public_state(
        previous_state,
        current_state,
    )
    if can_incrementally_extend:
        new_events: list[tuple[int, int, str, int | None, int | None, tuple[int, ...]]] = []
        for player_index, player in enumerate(Player):
            seat = int(player)
            previous_discard_count = previous_state.discard_counts_by_seat[player_index]
            discard_sequence = discard_sequences_by_seat[seat]
            for local_index in range(previous_discard_count, len(discard_sequence)):
                discard = discard_sequence[local_index]
                if not _discard_has_explicit_awaseuchi_order(discard):
                    can_incrementally_extend = False
                    break
                new_events.append(
                    _awaseuchi_discard_event_entry(
                        seat,
                        local_index,
                        discard,
                        0,
                    )
                )
            if not can_incrementally_extend:
                break
            previous_meld_count = previous_state.meld_counts_by_seat[player_index]
            meld_sequence = meld_sequences_by_seat[seat]
            for meld in meld_sequence[previous_meld_count:]:
                event_entry = _awaseuchi_meld_event_entry(seat, meld)
                if event_entry is None:
                    can_incrementally_extend = False
                    break
                new_events.append(event_entry)
            if not can_incrementally_extend:
                break
        if can_incrementally_extend:
            for fallback_index, event in enumerate(
                normalized_round_events[previous_state.dora_count:],
                start=previous_state.dora_count,
            ):
                event_entry = _awaseuchi_dora_event_entry(event, fallback_index)
                if event_entry is None:
                    can_incrementally_extend = False
                    break
                new_events.append(event_entry)

    if can_incrementally_extend:
        new_events.sort(key=_same_jun_public_event_sort_key)
        previous_event_stream = tuple(getattr(canvas, "same_jun_match_candidate_event_stream", ()))
        if (
            previous_event_stream
            and new_events
            and _same_jun_public_event_sort_key(new_events[0])
            < _same_jun_public_event_sort_key(previous_event_stream[-1])
        ):
            can_incrementally_extend = False

    if can_incrementally_extend:
        event_stream = previous_event_stream + tuple(new_events)
        provisional_value, recent_public_events = _extend_same_jun_candidate_state(
            getattr(canvas, "same_jun_match_candidate_cache_value", {}),
            getattr(canvas, "same_jun_match_candidate_recent_public_events", ()),
            new_events,
            recent_public_event_window=AWASEUCHI_PROVISIONAL_PUBLIC_EVENT_WINDOW,
        )
    else:
        event_stream = _same_jun_public_event_stream(
            discard_sequences_by_seat,
            meld_sequences_by_seat,
            normalized_round_events,
        )
        provisional_value, recent_public_events = _same_jun_candidate_state_from_event_stream(
            event_stream,
            recent_public_event_window=AWASEUCHI_PROVISIONAL_PUBLIC_EVENT_WINDOW,
        )

    canvas.same_jun_public_event_source_state = current_state
    canvas.same_jun_match_candidate_cache_key = current_state
    canvas.same_jun_match_candidate_cache_value = provisional_value
    canvas.same_jun_match_candidate_event_stream = event_stream
    canvas.same_jun_match_candidate_recent_public_events = recent_public_events
    return current_state, event_stream, provisional_value


def _queue_same_jun_confirmation(
    canvas: tkinter.Canvas,
    cache_key: tuple[object, ...],
    event_stream: Sequence[tuple[int, int, str, int | None, int | None, tuple[int, ...]]],
) -> None:
    """Queue one background awaseuchi confirmation for the current public state."""

    if getattr(canvas, "same_jun_match_async_in_flight", False):
        return
    if getattr(canvas, "same_jun_match_async_pending_key", None) == cache_key:
        return
    result_queue = getattr(canvas, "same_jun_match_async_result_queue", None)
    if result_queue is None:
        result_queue = queue.Queue()
        canvas.same_jun_match_async_result_queue = result_queue
    canvas.same_jun_match_async_in_flight = True
    canvas.same_jun_match_async_pending_key = cache_key
    immutable_event_stream = tuple(event_stream)

    def _worker() -> None:
        try:
            result_queue.put(
                {
                    "cache_key": cache_key,
                    "ok": True,
                    "result": _same_jun_match_discard_indices_by_seat_from_event_stream(
                        immutable_event_stream
                    ),
                }
            )
        except Exception as exc:  # noqa: BLE001 - background confirmation must not kill UI redraw.
            result_queue.put(
                {
                    "cache_key": cache_key,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    _start_tracked_background_thread(
        label="awaseuchi confirm",
        name="same-jun-confirm",
        target=_worker,
    )


def _drain_same_jun_match_background_result_queue(canvas: tkinter.Canvas) -> bool:
    """Apply finished awaseuchi confirmation results back on the Tk thread."""

    result_queue = getattr(canvas, "same_jun_match_async_result_queue", None)
    if result_queue is None:
        return False
    changed = False
    while True:
        try:
            payload = result_queue.get_nowait()
        except queue.Empty:
            break
        if not isinstance(payload, Mapping):
            continue
        cache_key = payload.get("cache_key")
        if cache_key == getattr(canvas, "same_jun_match_async_pending_key", None):
            canvas.same_jun_match_async_pending_key = None
        canvas.same_jun_match_async_in_flight = False
        if not bool(payload.get("ok", False)):
            continue
        if not isinstance(cache_key, tuple):
            continue
        result = payload.get("result")
        if not isinstance(result, Mapping):
            continue
        canvas.same_jun_match_confirmed_cache_key = cache_key
        canvas.same_jun_match_confirmed_cache_value = {
            int(seat): frozenset(int(local_index) for local_index in local_indexes)
            for seat, local_indexes in result.items()
        }
        changed = True
    return changed


def _same_jun_marker_indices_by_seat(
    canvas: tkinter.Canvas,
    discard_map: Mapping[Player, Iterable[Discard]],
    melds_by_player: Mapping[Player, Iterable[Meld]] | None = None,
    round_events: Sequence[object] | None = None,
) -> dict[int, frozenset[int]]:
    """Return display-ready awaseuchi markers: provisional first, confirmed when ready."""

    round_identity = getattr(canvas, "current_round_identity", None)
    cache_key, event_stream, provisional_value = _same_jun_marker_state_from_live_public_state(
        canvas,
        discard_map,
        melds_by_player,
        round_events,
    )
    confirm_cache_key = _same_jun_confirmation_cache_key(
        round_identity,
        event_stream,
    )
    if not any(provisional_value.get(int(player), frozenset()) for player in Player):
        empty_confirmed_value = {
            int(player): frozenset()
            for player in Player
        }
        canvas.same_jun_match_confirmed_cache_key = confirm_cache_key
        canvas.same_jun_match_confirmed_cache_value = empty_confirmed_value
        return empty_confirmed_value
    confirmed_cache_key = getattr(canvas, "same_jun_match_confirmed_cache_key", None)
    if confirmed_cache_key == confirm_cache_key:
        confirmed_value = getattr(canvas, "same_jun_match_confirmed_cache_value", {})
        return {
            int(seat): frozenset(provisional_value.get(int(seat), frozenset()) & confirmed_value.get(int(seat), frozenset()))
            for seat in (int(player) for player in Player)
        }
    _queue_same_jun_confirmation(canvas, confirm_cache_key, event_stream)
    return provisional_value


def _visible_count_marker_kind(
    tile_34: int | None,
    visible_summary: VisibleTileSummary,
) -> str:
    """Return `four` / `three` / `none` for one tile's visible-count flag."""

    if tile_34 is None:
        return "none"
    display_tile_34 = tile_34
    if display_tile_34 not in VISIBLE_TILE_IDS_34 and 0 <= display_tile_34 < 34:
        if display_tile_34 < 9:
            display_tile_34 += 1
        elif display_tile_34 < 18:
            display_tile_34 += 2
        elif display_tile_34 < 27:
            display_tile_34 += 3
        else:
            display_tile_34 += 4
    if display_tile_34 in set(visible_summary.four_visible_tiles):
        return "four"
    if display_tile_34 in set(visible_summary.three_visible_tiles):
        return "three"
    return "none"


def _visible_count_marker_style(marker_kind: str) -> tuple[str, str] | None:
    """Return `(shape, fill)` for one visible-count marker kind."""

    if marker_kind == "three":
        return ("circle", THREE_VISIBLE_DISCARD_MARKER)
    return None


def _draw_visible_count_marker(
    canvas: tkinter.Canvas,
    player: Player,
    left: float,
    top: float,
    right: float,
    bottom: float,
    marker_kind: str,
) -> None:
    """Draw one 3-visible / 4-visible marker at the rotated position of the original top-right corner."""

    marker_style = _visible_count_marker_style(marker_kind)
    if marker_style is None:
        return
    shape, fill = marker_style
    marker_radius, (center_x, center_y), _same_jun_center, _lag_center = _discard_marker_layout(
        player,
        left,
        top,
        right,
        bottom,
    )
    if shape == "square":
        canvas.create_rectangle(
            center_x - marker_radius,
            center_y - marker_radius,
            center_x + marker_radius,
            center_y + marker_radius,
            fill=fill,
            outline="",
        )
        return
    canvas.create_oval(
        center_x - marker_radius,
        center_y - marker_radius,
        center_x + marker_radius,
        center_y + marker_radius,
        fill=fill,
        outline="",
    )


def _should_draw_discard_visible_count_marker(discard: Discard) -> bool:
    """Return whether one river tile should receive the 3-visible / 4-visible marker."""

    return getattr(discard, "draw_type", None) == DrawType.TEDASHI


def _self_hand_honor_visible_count(
    tile_id: int,
    visible_summary: VisibleTileSummary,
) -> int | None:
    """Return one self-hand honor tile's current visible count, else `None`."""

    tile_34_index = tile37_to_tile34_index(tile_id)
    if tile_34_index is None or tile_34_index < 27:
        return None
    visible_counts_34_index = tuple(
        int(count) for count in getattr(visible_summary, "visible_counts_34_index", ())
    )
    if tile_34_index >= len(visible_counts_34_index):
        return None
    return max(0, int(visible_counts_34_index[tile_34_index]))


def _draw_self_hand_honor_visible_count(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    right: float,
    bottom: float,
    visible_count: int | None,
) -> None:
    """Draw one compact visible-count digit above a self-hand honor tile."""

    if visible_count is None:
        return
    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    font_size = max(6, int(round(8 * current_ui_scale)))
    text_x, text_y = _self_hand_honor_visible_count_geometry(
        left,
        top,
        right,
        bottom,
        current_ui_scale,
    )
    canvas.create_text(
        text_x,
        text_y,
        text=str(int(visible_count)),
        fill=HAND_HONOR_VISIBLE_COUNT_TEXT,
        font=("Consolas", font_size, "bold"),
        anchor=tkinter.NE,
    )


def _self_hand_honor_visible_count_geometry(
    left: float,
    top: float,
    right: float,
    bottom: float,
    current_ui_scale: float,
) -> tuple[float, float]:
    """Return the top-right text anchor position for one self-hand honor visible count."""

    del bottom
    horizontal_inset = _scaled_length(3, current_ui_scale, minimum=2)
    vertical_offset = _scaled_length(3, current_ui_scale, minimum=2)
    return right - horizontal_inset, top + vertical_offset


def _draw_lag_marker(
    canvas: tkinter.Canvas,
    player: Player,
    left: float,
    top: float,
    right: float,
    bottom: float,
    *,
    entry_key: tuple[object, ...],
    base_kind: str,
    color: str = LAG_DISCARD_MARKER,
) -> None:
    """Draw one lag marker label (`L`/`Pl`/`N`) in the former lag-marker slot."""

    _marker_radius, _four_visible_center, _same_jun_center, (center_x, center_y) = _discard_marker_layout(
        player,
        left,
        top,
        right,
        bottom,
    )
    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    font_size = max(7, int(round(8 * current_ui_scale)))
    kind_overrides = _normalize_lag_marker_reference_kind_overrides(
        getattr(canvas, "lag_marker_reference_kinds_by_entry", {})
    )
    effective_kind = _normalize_lag_marker_reference_kind(
        kind_overrides.get(tuple(entry_key), base_kind)
    )
    marker_text, marker_color = _lag_marker_display_style(effective_kind)
    marker_font = ("Consolas", font_size, "bold")
    marker_angle = float(PLAYER_ROTATIONS[player])
    _draw_marker_text_badge(
        canvas,
        center_x,
        center_y,
        text=marker_text,
        text_fill=marker_color,
        background_fill=LAG_MARKER_BADGE_FILL,
        font=marker_font,
        angle=marker_angle,
        offsets=((-0.35, 0.0), (0.35, 0.0)),
    )
    canvas.lag_marker_reference_button_specs.append(
        LagMarkerReferenceButtonSpec(
            kind=effective_kind,
            center=(center_x, center_y),
            radius=max(float(_marker_radius) + 2.0, float(font_size)),
            entry_key=tuple(entry_key),
            base_kind=_normalize_lag_marker_reference_kind(base_kind),
        )
    )


def _draw_marker_text_badge(
    canvas: tkinter.Canvas,
    center_x: float,
    center_y: float,
    *,
    text: str,
    text_fill: str,
    background_fill: str,
    font: tuple[str, int, str] | tuple[str, int],
    anchor: str = tkinter.CENTER,
    angle: float = 0.0,
    offsets: Sequence[tuple[float, float]] = ((0.0, 0.0),),
) -> None:
    """Draw one small colored badge behind marker text."""

    normalized_offsets = tuple(offsets) or ((0.0, 0.0),)
    first_dx, first_dy = normalized_offsets[0]
    probe_id = canvas.create_text(
        center_x,
        center_y,
        text=text,
        fill=text_fill,
        font=font,
        anchor=anchor,
        angle=angle,
    )
    bbox = canvas.bbox(probe_id)
    if bbox is not None:
        pad_x = 2.0
        pad_y = 1.0
        badge_id = canvas.create_rectangle(
            bbox[0] - pad_x,
            bbox[1] - pad_y,
            bbox[2] + pad_x,
            bbox[3] + pad_y,
            fill=background_fill,
            outline="",
        )
        canvas.tag_lower(badge_id, probe_id)
    if first_dx or first_dy:
        canvas.move(probe_id, first_dx, first_dy)
    for extra_dx, extra_dy in normalized_offsets[1:]:
        canvas.create_text(
            center_x + float(extra_dx),
            center_y + float(extra_dy),
            text=text,
            fill=text_fill,
            font=font,
            anchor=anchor,
            angle=angle,
        )


def _lag_marker_display_style(
    kind: str,
) -> tuple[str, str]:
    """Return the rendered lag-marker label/color for one effective `L/Pl/N` mode."""

    mode = _normalize_lag_marker_reference_kind(kind)
    if mode == LAG_MARKER_REFERENCE_KIND_BLACK:
        return "N", TEXT_SECONDARY
    if mode == LAG_MARKER_REFERENCE_KIND_GREEN:
        return "Pl", PON_LAG_LIKELY_DISCARD_MARKER
    return "L", LAG_DISCARD_MARKER


def _lag_marker_label(color: str) -> str:
    """Return the short text label used for one lag-marker color class."""

    normalized_color = str(color or "").strip().lower()
    if normalized_color in {
        str(PON_LAG_LIKELY_DISCARD_MARKER).lower(),
        str(MULTI_PLAYER_LAG_DISCARD_MARKER).lower(),
    }:
        return "Pl"
    return "L"


def _discard_global_index(discard: object, fallback_index: int | None = None) -> int | None:
    """Return one discard's stable global index using round, then event, then fallback order."""

    for attr_name in ("round_discard_index", "event_index"):
        try:
            value = int(getattr(discard, attr_name))
        except (AttributeError, TypeError, ValueError):
            value = None
        if value is not None and value >= 0:
            return value
    if fallback_index is None:
        return None
    return max(0, int(fallback_index))


def _push_discard_marker_indices_by_seat(
    push_alerts_by_seat: Mapping[int, object] | None,
) -> dict[int, frozenset[int]]:
    """Return global discard indexes that should render the purple `P` push marker."""

    if not isinstance(push_alerts_by_seat, Mapping):
        return {}
    has_explicit_marker_indices = any(
        not isinstance(raw_value, Mapping) or "discard_indices" in raw_value
        for raw_value in push_alerts_by_seat.values()
    )
    if has_explicit_marker_indices:
        return {
            seat: indices
            for seat, indices in _normalize_push_marker_indices_by_seat(
                push_alerts_by_seat
            ).items()
            if indices
        }
    marker_indices: dict[int, frozenset[int]] = {}
    for fallback_seat, payload in push_alerts_by_seat.items():
        if not isinstance(payload, Mapping):
            continue
        try:
            seat = int(payload.get("seat", fallback_seat))
            discard_index = int(payload.get("discard_index"))
        except (TypeError, ValueError):
            continue
        kind = str(payload.get("kind", "") or "").strip().lower()
        try:
            percentage = max(0.0, float(payload.get("percentage", 0.0)))
        except (TypeError, ValueError):
            percentage = 0.0
        threshold_percent = _player_push_alert_threshold_percent(payload)
        if kind not in {"", "push"}:
            continue
        if kind != "push" and percentage < threshold_percent:
            continue
        if discard_index < 0:
            continue
        marker_indices[seat] = frozenset({discard_index})
    return marker_indices


def _push_discard_marker_geometry(
    player: Player,
    left: float,
    top: float,
    right: float,
    bottom: float,
    current_ui_scale: float,
) -> tuple[float, float]:
    """Return the in-tile top marker row slot used by the push marker."""

    del current_ui_scale
    _marker_radius, _visible_count_center, same_jun_center, lag_center = _discard_marker_layout(
        player,
        left,
        top,
        right,
        bottom,
    )
    return (
        (float(same_jun_center[0]) + float(lag_center[0])) * 0.5,
        (float(same_jun_center[1]) + float(lag_center[1])) * 0.5,
    )


def _draw_push_discard_marker(
    canvas: tkinter.Canvas,
    player: Player,
    left: float,
    top: float,
    right: float,
    bottom: float,
    *,
    color: str = PUSH_DISCARD_MARKER,
) -> None:
    """Draw the purple `P` push marker inside the top marker row of one discard tile."""

    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    font_size = max(8, int(round(9 * current_ui_scale)))
    center_x, center_y = _push_discard_marker_geometry(
        player,
        left,
        top,
        right,
        bottom,
        current_ui_scale,
    )
    marker_font = ("Consolas", font_size, "bold")
    marker_angle = float(PLAYER_ROTATIONS[player])
    _draw_marker_text_badge(
        canvas,
        center_x,
        center_y,
        text="P",
        text_fill=color,
        background_fill=PUSH_DISCARD_MARKER_BADGE_FILL,
        font=marker_font,
        angle=marker_angle,
        offsets=((-0.35, 0.0), (0.35, 0.0)),
    )


def _draw_same_jun_match_marker(
    canvas: tkinter.Canvas,
    player: Player,
    left: float,
    top: float,
    right: float,
    bottom: float,
    color: str = SAME_JUN_MATCH_DISCARD_MARKER,
) -> None:
    """Draw the awaseuchi marker between visible-count and lag markers."""

    marker_radius, _visible_count_center, (center_x, center_y), _lag_center = _discard_marker_layout(
        player,
        left,
        top,
        right,
        bottom,
    )
    canvas.create_oval(
        center_x - marker_radius,
        center_y - marker_radius,
        center_x + marker_radius,
        center_y + marker_radius,
        fill=color,
        outline="",
    )


def _peak_thinking_time_marker_geometry(
    player: Player,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> tuple[float, float, float]:
    """Return the diamond geometry at the pre-rotation tile's lower edge."""

    width = max(0.0, right - left)
    height = max(0.0, bottom - top)
    marker_radius = max(4.0, min(width, height) * 0.15)
    edge_margin = marker_radius + 2.0
    if player == Player.JICHA:
        center_x = left + width * 0.5
        center_y = bottom - edge_margin
    elif player == Player.TOIMEN:
        center_x = left + width * 0.5
        center_y = top + edge_margin
    elif player == Player.SHIMOCHA:
        center_x = right - edge_margin
        center_y = top + height * 0.5
    else:
        center_x = left + edge_margin
        center_y = top + height * 0.5
    return center_x, center_y, marker_radius


def _draw_peak_thinking_time_marker(
    canvas: tkinter.Canvas,
    player: Player,
    left: float,
    top: float,
    right: float,
    bottom: float,
    color: str = PEAK_THINKING_TIME_DISCARD_MARKER,
) -> None:
    """Draw a red diamond at the rotated position of the pre-rotation lower edge."""

    center_x, center_y, marker_radius = _peak_thinking_time_marker_geometry(
        player,
        left,
        top,
        right,
        bottom,
    )
    canvas.create_polygon(
        center_x,
        center_y - marker_radius,
        center_x + marker_radius,
        center_y,
        center_x,
        center_y + marker_radius,
        center_x - marker_radius,
        center_y,
        fill=color,
        outline="",
    )


def _draw_riichi_stick_marker(
    canvas: tkinter.Canvas,
    player: Player,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> None:
    """Draw a compact riichi stick on the center-facing side of the declaration discard."""

    width = right - left
    height = bottom - top
    if player in {Player.JICHA, Player.TOIMEN}:
        stick_width = max(12.0, width * 0.58)
        stick_height = max(3.0, height * 0.16)
        center_x = (left + right) / 2
        center_y = top + height * 0.24 if player == Player.JICHA else bottom - height * 0.24
        stick_left = center_x - stick_width / 2
        stick_top = center_y - stick_height / 2
        stick_right = center_x + stick_width / 2
        stick_bottom = center_y + stick_height / 2
        red_width = max(3.0, stick_width * 0.22)
        canvas.create_rectangle(
            stick_left,
            stick_top,
            stick_right,
            stick_bottom,
            fill=RIICHI_STICK_FILL,
            outline=RIICHI_STICK_OUTLINE,
            width=1,
        )
        canvas.create_rectangle(
            stick_left,
            stick_top,
            stick_left + red_width,
            stick_bottom,
            fill=RIICHI_STICK_RED,
            outline="",
        )
        return

    stick_width = max(3.0, width * 0.16)
    stick_height = max(12.0, height * 0.58)
    center_x = left + width * 0.24 if player == Player.SHIMOCHA else right - width * 0.24
    center_y = (top + bottom) / 2
    stick_left = center_x - stick_width / 2
    stick_top = center_y - stick_height / 2
    stick_right = center_x + stick_width / 2
    stick_bottom = center_y + stick_height / 2
    red_height = max(3.0, stick_height * 0.22)
    canvas.create_rectangle(
        stick_left,
        stick_top,
        stick_right,
        stick_bottom,
        fill=RIICHI_STICK_FILL,
        outline=RIICHI_STICK_OUTLINE,
        width=1,
    )
    canvas.create_rectangle(
        stick_left,
        stick_top,
        stick_right,
        stick_top + red_height,
        fill=RIICHI_STICK_RED,
        outline="",
    )


def _draw_called_discard_border(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> None:
    """Draw a red frame around a discard consumed by a call."""

    canvas.create_rectangle(
        left + 1,
        top + 1,
        right - 1,
        bottom - 1,
        outline=CALLED_DISCARD_BORDER,
        width=CALLED_DISCARD_BORDER_WIDTH,
    )


def _draw_post_call_tedashi_discard_border(
    canvas: tkinter.Canvas,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> None:
    """Draw a yellow frame around a tedashi made immediately after a meld call."""

    canvas.create_rectangle(
        left + 1,
        top + 1,
        right - 1,
        bottom - 1,
        outline=POST_CALL_TEDASHI_DISCARD_BORDER,
        width=POST_CALL_TEDASHI_DISCARD_BORDER_WIDTH,
    )


def _discard_border_kind(discard: Discard) -> str:
    """Return the river-border kind for one discard."""

    if discard.called:
        return "called"
    if (
        discard.draw_type == DrawType.TEDASHI
        and str(getattr(discard, "thinking_time_source", "") or "").strip() == "call"
    ):
        return "post_call_tedashi"
    return "none"


def _collect_multi_player_lag_tiles_34(
    discard_map: Mapping[Player, Iterable[Discard]],
) -> set[int]:
    """Return 34-kind tiles that have lagged discards in two or more players' rivers."""

    lagged_players_by_tile_34: dict[int, set[Player]] = {}
    for player in Player:
        for discard in discard_map.get(player, []):
            if (
                _is_riseki_completion_discard(discard)
                or discard.called
                or not _is_visual_lag_flag(discard.lagged)
            ):
                continue
            tile_34 = tile37_to_tile34_index(discard.tile_id)
            if tile_34 is None:
                continue
            lagged_players_by_tile_34.setdefault(tile_34, set()).add(player)
    return {
        tile_34
        for tile_34, players in lagged_players_by_tile_34.items()
        if len(players) >= 2
    }


def _count_tile34_in_hand_snapshot(hand_tiles_136: Sequence[int], tile_34: int) -> int:
    """Count how many copies of one 34-kind tile exist in one 136-hand snapshot."""

    count = 0
    for tile_136 in hand_tiles_136:
        if tile136_to_tile34_index(tile_136) == tile_34:
            count += 1
    return count


def _can_pon_from_hand_snapshot(hand_tiles_136: Sequence[int], tile_34: int) -> bool:
    """Return whether one concealed-hand snapshot can pon the discard tile."""

    return _count_tile34_in_hand_snapshot(hand_tiles_136, tile_34) >= 2


def _can_chi_from_hand_snapshot(hand_tiles_136: Sequence[int], tile_34: int) -> bool:
    """Return whether one concealed-hand snapshot can chi the discard tile."""

    if tile_34 < 0 or tile_34 >= 27:
        return False
    suit_offset = (tile_34 // 9) * 9
    rank = tile_34 - suit_offset + 1
    counts = {
        suit_offset + local_rank - 1: _count_tile34_in_hand_snapshot(
            hand_tiles_136,
            suit_offset + local_rank - 1,
        )
        for local_rank in range(1, 10)
    }
    for left_rank, right_rank in (
        (rank - 2, rank - 1),
        (rank - 1, rank + 1),
        (rank + 1, rank + 2),
    ):
        if not (1 <= left_rank <= 9 and 1 <= right_rank <= 9):
            continue
        left_tile_34 = suit_offset + left_rank - 1
        right_tile_34 = suit_offset + right_rank - 1
        if counts.get(left_tile_34, 0) >= 1 and counts.get(right_tile_34, 0) >= 1:
            return True
    return False


def _self_cannot_call_lagged_discard(player: Player, discard: Discard) -> bool:
    """Return whether the self-hand snapshot shows no legal chi/pon response to this discard."""

    if player == Player.JICHA:
        return False
    hand_tiles_136 = tuple(
        int(tile_136)
        for tile_136 in getattr(discard, "self_hand_tiles_before_discard_136", ())
        if tile_136 is not None
    )
    if not hand_tiles_136:
        return False
    discard_tile_34 = tile37_to_tile34_index(getattr(discard, "tile_id", None))
    if discard_tile_34 is None:
        return False
    if player == Player.KAMICHA and _can_chi_from_hand_snapshot(hand_tiles_136, discard_tile_34):
        return False
    if _can_pon_from_hand_snapshot(hand_tiles_136, discard_tile_34):
        return False
    return True


def _bridge_naki_disabled_active_for_lag(
    status: TenhouUiBridgeStatus | None,
    *,
    override_active: bool | None = None,
) -> bool:
    """Return the effective `鳴き無し` toggle state used by lag-marker promotion."""

    toggle_control = _lookup_bridge_toggle_control(status, BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID)
    reported_active = bool(getattr(toggle_control, "active", False)) if toggle_control is not None else False
    display_active, _clear_override = _resolve_bridge_toggle_active_state(
        reported_active,
        override_active,
    )
    return display_active


def _bridge_has_visible_lag_call_controls(status: TenhouUiBridgeStatus | None) -> bool:
    """Return whether a current bridge snapshot shows any call-related visible control."""

    if status is None:
        return False
    visible_call_control_ids = (
        set(BRIDGE_NAKI_CONTROL_IDS)
        | set(BRIDGE_PON_CONTROL_IDS)
        | set(BRIDGE_CHI_CONTROL_IDS)
    )
    return (
        _select_visible_bridge_control_id(
            status,
            visible_call_control_ids,
            text_hints=("鳴き", "chi", "pon", "チー", "ポン"),
        )
        is not None
    )


def _is_pon_lag_likely_discard(
    player: Player,
    discard: Discard,
    multi_player_lag_tiles_34: Collection[int],
    *,
    bridge_status: TenhouUiBridgeStatus | None = None,
    naki_disabled_override_active: bool | None = None,
) -> bool:
    """Return whether a lag marker should be promoted into the green pon-lag-likely class."""

    if discard.called or not _is_visual_lag_flag(getattr(discard, "lagged", 0)):
        return False
    discard_tile_34 = tile37_to_tile34_index(getattr(discard, "tile_id", None))
    if discard_tile_34 is None:
        return False
    if 27 <= discard_tile_34 <= 33:
        return True
    if discard_tile_34 in multi_player_lag_tiles_34:
        return True
    if player != Player.KAMICHA:
        return False
    if bridge_status is None:
        return False
    if _bridge_naki_disabled_active_for_lag(
        bridge_status,
        override_active=naki_disabled_override_active,
    ):
        return True
    if _bridge_has_visible_lag_call_controls(bridge_status):
        return False
    return _self_cannot_call_lagged_discard(player, discard)


def _lag_marker_color(
    player: Player,
    discard: Discard,
    multi_player_lag_tiles_34: Collection[int],
    *,
    bridge_status: TenhouUiBridgeStatus | None = None,
    naki_disabled_override_active: bool | None = None,
) -> str:
    """Return the effective lag-marker color for one discard."""

    if _is_pon_lag_likely_discard(
        player,
        discard,
        multi_player_lag_tiles_34,
        bridge_status=bridge_status,
        naki_disabled_override_active=naki_disabled_override_active,
    ):
        return PON_LAG_LIKELY_DISCARD_MARKER
    return LAG_DISCARD_MARKER


def _thinking_time_tint_step(thinking_time_ms: float | None) -> int:
    """Quantize one thinking-time segment into a bounded overlay step."""

    if thinking_time_ms is None or thinking_time_ms <= 0.0:
        return 0
    clamped_ms = min(max(thinking_time_ms, 0.0), THINKING_TIME_MAX_MS)
    return max(1, int(round(clamped_ms / THINKING_TIME_MAX_MS * THINKING_TIME_TINT_STEPS)))


def _thinking_time_overlay_style(
    tint_step: int,
) -> tuple[tuple[int, int, int] | None, float]:
    """Map time steps to six fixed states: no change, green, blue, yellow, red, then purple."""

    if tint_step <= 0:
        return None, 0.0

    first_stage_end = max(THINKING_TIME_TINT_STEPS // 5, 1)
    second_stage_end = max((THINKING_TIME_TINT_STEPS * 2) // 5, first_stage_end + 1)
    third_stage_end = max((THINKING_TIME_TINT_STEPS * 3) // 5, second_stage_end + 1)
    fourth_stage_end = max((THINKING_TIME_TINT_STEPS * 4) // 5, third_stage_end + 1)
    fourth_stage_end = min(fourth_stage_end, THINKING_TIME_TINT_STEPS)

    if tint_step <= first_stage_end:
        return THINKING_TIME_GREEN_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND

    if tint_step <= second_stage_end:
        return THINKING_TIME_BLUE_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND

    if tint_step <= third_stage_end:
        return THINKING_TIME_YELLOW_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND

    if tint_step <= fourth_stage_end:
        return THINKING_TIME_RED_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND

    return THINKING_TIME_PURPLE_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND


def _thinking_time_overlay_band(
    tint_step: int,
    *,
    band_start_ratio: float,
    band_end_ratio: float,
) -> tuple[float, float, tuple[int, int, int], tuple[int, int, int], float] | None:
    """Build one unrotated tile overlay band for the given thinking-time step."""

    overlay_color, overlay_strength = _thinking_time_overlay_style(tint_step)
    if overlay_color is None or overlay_strength <= 0.0:
        return None
    return (
        band_start_ratio,
        band_end_ratio,
        overlay_color,
        overlay_color,
        overlay_strength,
    )


def _scaled_tile_size(width: int, height: int, scale_multiplier: float) -> tuple[int, int]:
    """Scale one already-oriented tile size by a tuning multiplier."""

    return (
        max(1, int(round(width * scale_multiplier))),
        max(1, int(round(height * scale_multiplier))),
    )


def _is_sequence_blocked_by_four_visible(
    tile_34_index: int | None,
    visible_summary: VisibleTileSummary,
) -> bool:
    """Return whether the shared 4-visible blocker set kills every 3-sequence through the tile."""

    try:
        normalized_tile_34_index = int(tile_34_index)
    except (TypeError, ValueError):
        return False
    blocked_sequence_tile34_index_set = getattr(
        visible_summary,
        "blocked_sequence_tile34_index_set",
        frozenset(),
    )
    return normalized_tile_34_index in blocked_sequence_tile34_index_set


def _visible_count_kind_for_tile34_index(
    tile_34_index: int | None,
    visible_summary: VisibleTileSummary,
) -> str:
    """Return `four` / `three` / `none` using canonical 0..33 tile indexes."""

    try:
        normalized_tile_34_index = int(tile_34_index)
    except (TypeError, ValueError):
        return "none"
    if normalized_tile_34_index < 0:
        return "none"
    four_visible_tile34_index_set = getattr(
        visible_summary,
        "four_visible_tile34_index_set",
        frozenset(),
    )
    if normalized_tile_34_index in four_visible_tile34_index_set:
        return "four"
    visible_counts_34_index = tuple(
        int(count) for count in getattr(visible_summary, "visible_counts_34_index", ())
    )
    if normalized_tile_34_index >= len(visible_counts_34_index):
        return "none"
    visible_count = max(0, int(visible_counts_34_index[normalized_tile_34_index]))
    if visible_count == 3:
        return "three"
    return "none"


def _discard_tile_tint_kind(
    discard: object,
    tile_34_index: int | None,
    *,
    should_red_tint: bool,
    visible_summary: VisibleTileSummary,
) -> str:
    """Return the final river tint using `purple > brown > red > none` priority."""

    # `called` is orthogonal to discard type: a later-called discard still stays tedashi/tsumogiri.
    # Prefer `draw_type` when available so tint logic matches the actual river tile image variant.
    is_tedashi = _is_table_situation_tedashi_discard(discard)
    if is_tedashi:
        visible_count_kind = _visible_count_kind_for_tile34_index(tile_34_index, visible_summary)
        if visible_count_kind == "four":
            return "four_visible"
        if _is_sequence_blocked_by_four_visible(tile_34_index, visible_summary):
            return "brown"
    if not should_red_tint:
        return "none"
    return "red"


def _discard_tint_overlay_band(
    tint_kind: str,
) -> tuple[float, float, tuple[int, int, int], tuple[int, int, int], float] | None:
    """Map semantic river tint kinds to one full-tile overlay palette."""

    if tint_kind == "red":
        overlay_color = DISCARD_RED_TINT_COLOR
        overlay_strength = DISCARD_RED_TINT_BLEND
    elif tint_kind == "brown":
        overlay_color = DISCARD_BROWN_TINT_COLOR
        overlay_strength = DISCARD_BROWN_TINT_BLEND
    elif tint_kind == "four_visible":
        overlay_color = DISCARD_FOUR_VISIBLE_TINT_COLOR
        overlay_strength = DISCARD_FOUR_VISIBLE_TINT_BLEND
    else:
        return None
    return (0.0, 1.0, overlay_color, overlay_color, overlay_strength)


def _discard_tint_brighten_overlay_band(
    tint_kind: str,
) -> tuple[float, float, tuple[int, int, int], tuple[int, int, int], float] | None:
    """Return a white full-tile brighten overlay used before discard tint colors."""

    if tint_kind == "none":
        return None
    return (
        0.0,
        1.0,
        DISCARD_TINT_BRIGHTEN_COLOR,
        DISCARD_TINT_BRIGHTEN_COLOR,
        DISCARD_TINT_BRIGHTEN_BLEND,
    )


def _discard_tint_base_overlay_bands(
    tint_kind: str,
) -> tuple[tuple[float, float, tuple[int, int, int], tuple[int, int, int], float], ...]:
    """Return the cached full-tile base overlays for one semantic discard tint."""

    return tuple(
        band
        for band in (
            _discard_tint_brighten_overlay_band(tint_kind),
            _discard_tint_overlay_band(tint_kind),
        )
        if band is not None
    )


def _ensure_discard_tint_base_prewarm(
    canvas: tkinter.Canvas,
    discard_tile_scale: float,
) -> None:
    """Prewarm the unrotated discard-tint bases once per effective discard tile scale."""

    scale_key = round(float(discard_tile_scale), 3)
    warmed_scale_keys = set(getattr(canvas, "discard_tint_base_prewarm_scale_keys", set()))
    if scale_key in warmed_scale_keys:
        return
    warm_unrotated_tile_overlay_bases(
        {
            tint_kind: _discard_tint_base_overlay_bands(tint_kind)
            for tint_kind in ("red", "brown", "four_visible")
        },
        tile_scale=discard_tile_scale,
    )
    warmed_scale_keys.add(scale_key)
    canvas.discard_tint_base_prewarm_scale_keys = warmed_scale_keys


def _discard_tile_image(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    player: Player,
    discard: Discard,
    *,
    tint_kind: str = "none",
) -> ImageTk.PhotoImage:
    """Return the discard image with post-REACH and pre-REACH thinking-time overlay bands."""

    tuning = _current_layout_tuning(canvas)
    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    discard_tile_scale = current_ui_scale * float(tuning.discard_tile_scale)
    base_overlay_bands = _discard_tint_base_overlay_bands(tint_kind)
    if _is_riseki_completion_discard(discard):
        lower_band_tint_step = 0
        upper_band_tint_step = 0
    else:
        lower_band_tint_step = _thinking_time_tint_step(discard.thinking_time_ms)
        upper_band_tint_step = _thinking_time_tint_step(discard.thinking_time_before_reach_ms)
    if (
        lower_band_tint_step <= 0
        and upper_band_tint_step <= 0
        and tint_kind == "none"
        and abs(discard_tile_scale - current_ui_scale) < 0.001
    ):
        return img_table[player][discard.draw_type][discard.tile_id]

    overlay_bands = tuple(
        band
        for band in (
            _thinking_time_overlay_band(
                lower_band_tint_step,
                band_start_ratio=THINKING_TIME_LOWER_BAND_START_RATIO,
                band_end_ratio=THINKING_TIME_LOWER_BAND_END_RATIO,
            ),
            _thinking_time_overlay_band(
                upper_band_tint_step,
                band_start_ratio=THINKING_TIME_UPPER_BAND_START_RATIO,
                band_end_ratio=THINKING_TIME_UPPER_BAND_END_RATIO,
            ),
        )
        if band is not None
    )
    if not base_overlay_bands and not overlay_bands:
        return img_table[player][discard.draw_type][discard.tile_id]

    cache_key = (
        player,
        discard.draw_type,
        discard.tile_id,
        lower_band_tint_step,
        upper_band_tint_step,
        tint_kind,
        round(discard_tile_scale, 3),
    )
    cache: dict[tuple[Player, DrawType, int, int, int, str, float], ImageTk.PhotoImage] = getattr(
        canvas,
        "thinking_tile_image_cache",
        {},
    )
    cached_image = cache.get(cache_key)
    if cached_image is not None:
        return cached_image

    _ensure_discard_tint_base_prewarm(canvas, discard_tile_scale)
    tinted_image = build_tile_photoimage_from_base_overlay(
        canvas,
        discard.tile_id,
        player,
        discard.draw_type,
        base_overlay_bands=base_overlay_bands,
        overlay_bands=overlay_bands,
        tile_scale=discard_tile_scale,
    )
    cache[cache_key] = tinted_image
    canvas.thinking_tile_image_cache = cache
    return tinted_image


def _meld_tile_image(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    player: Player,
    tile_id: int,
    *,
    tile_scale_multiplier: float = 1.0,
) -> ImageTk.PhotoImage:
    """Return one meld tile image scaled by the current LAYOUT tuning multiplier."""

    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    meld_tile_scale = current_ui_scale * float(tile_scale_multiplier)
    if abs(meld_tile_scale - current_ui_scale) < 0.001:
        return img_table[player][DrawType.TEDASHI][tile_id]

    cache_key = (player, tile_id, round(meld_tile_scale, 3))
    cache: dict[tuple[Player, int, float], ImageTk.PhotoImage] = getattr(
        canvas,
        "meld_tile_image_cache",
        {},
    )
    cached_image = cache.get(cache_key)
    if cached_image is not None:
        return cached_image

    scaled_image = build_tile_photoimage(
        canvas,
        tile_id,
        player,
        DrawType.TEDASHI,
        tile_scale=meld_tile_scale,
    )
    cache[cache_key] = scaled_image
    canvas.meld_tile_image_cache = cache
    return scaled_image


def _meld_rotation_quadrants(player: Player) -> int:
    """自家向きを基準に何回 90 度回すかを返す。"""

    return {
        Player.JICHA: 0,
        Player.SHIMOCHA: 3,
        Player.TOIMEN: 2,
        Player.KAMICHA: 1,
    }[player]


def _meld_image_quadrants(player: Player) -> int:
    """Return the image-rotation quadrants for meld tiles at each seat."""

    return {
        Player.JICHA: 0,
        Player.SHIMOCHA: 1,
        Player.TOIMEN: 2,
        Player.KAMICHA: 3,
    }[player]


def _rotate_player(player: Player, quadrants: int) -> Player:
    """牌画像の向きを 90 度単位で回した座席 enum を返す。"""

    return Player((int(player) + quadrants) % len(Player))


def _meld_called_slot(from_player: str, tile_count: int) -> int | None:
    """誰から鳴いたかに応じて横向き牌を置くスロットを返す。"""

    if from_player == "kamicha":
        return 0
    if from_player == "toimen":
        return 1 if tile_count >= 3 else 0
    if from_player == "shimocha":
        return tile_count - 1
    return None


def _arrange_meld_tiles(meld: Meld) -> list[tuple[int, bool]]:
    """表示順へ並べ替えた `(tile_id, is_called_tile)` 配列を返す。"""

    tiles = list(meld.tiles_37)
    if not tiles:
        return []
    called_slot = _meld_called_slot(meld.from_player, len(tiles))
    called_index = meld.called_index
    if called_slot is None or called_index is None or not 0 <= called_index < len(tiles):
        return [(tile_id, False) for tile_id in tiles]

    called_tile = tiles[called_index]
    remaining_tiles = [tile_id for index, tile_id in enumerate(tiles) if index != called_index]
    arranged_tiles: list[tuple[int, bool]] = []
    remaining_index = 0
    for slot in range(len(tiles)):
        if slot == called_slot:
            arranged_tiles.append((called_tile, True))
        else:
            arranged_tiles.append((remaining_tiles[remaining_index], False))
            remaining_index += 1
    return arranged_tiles


def _meld_tile34_values(meld: Meld) -> list[int]:
    """Return canonical 0..33 tile ids for one meld, tolerating UI-only test data."""

    tiles_34 = [
        int(tile_34)
        for tile_34 in (getattr(meld, "tiles_34", None) or ())
        if tile_34 is not None
    ]
    if tiles_34:
        return tiles_34

    tiles_136 = [
        tile136_to_tile34_index(tile_136)
        for tile_136 in (getattr(meld, "tiles_136", None) or ())
    ]
    tiles_34 = [int(tile_34) for tile_34 in tiles_136 if tile_34 is not None]
    if tiles_34:
        return tiles_34

    tiles_37 = [
        tile37_to_tile34_index(tile_37)
        for tile_37 in (getattr(meld, "tiles_37", None) or ())
    ]
    return [int(tile_34) for tile_34 in tiles_37 if tile_34 is not None]


def _meld_called_tile34(meld: Meld, tiles_34: Sequence[int]) -> int | None:
    """Return the canonical 0..33 id of the called tile for one meld."""

    called_tile_136 = getattr(meld, "called_tile_id", None)
    if called_tile_136 is None:
        called_tile_136 = getattr(meld, "called_tile_136", None)
    called_tile_34 = tile136_to_tile34_index(called_tile_136)
    if called_tile_34 is not None:
        return int(called_tile_34)

    called_index = getattr(meld, "called_index", None)
    try:
        called_index = int(called_index)
    except (TypeError, ValueError):
        return None
    if 0 <= called_index < len(tiles_34):
        return int(tiles_34[called_index])
    return None


def _tile34_to_meld_suit_and_number(tile_34: int | None) -> tuple[int, int] | None:
    """Return `(suit_index, number)` for suited canonical tile ids."""

    if tile_34 is None or not 0 <= int(tile_34) < 27:
        return None
    normalized_tile = int(tile_34)
    return normalized_tile // 9, normalized_tile % 9 + 1


def _is_ryanmen_chi_meld(meld: Meld) -> bool:
    """Return whether one chi was called from a two-sided sequence wait."""

    if getattr(meld, "meld_type", None) != "chi":
        return False

    tiles_34 = _meld_tile34_values(meld)
    if len(tiles_34) != 3:
        return False

    suited_tiles = [_tile34_to_meld_suit_and_number(tile_34) for tile_34 in tiles_34]
    if any(suited_tile is None for suited_tile in suited_tiles):
        return False

    suit_index = suited_tiles[0][0]
    if any(suited_tile[0] != suit_index for suited_tile in suited_tiles):
        return False

    sorted_numbers = sorted(suited_tile[1] for suited_tile in suited_tiles)
    start_number = sorted_numbers[0]
    if sorted_numbers != [start_number, start_number + 1, start_number + 2]:
        return False

    called_tile_34 = _meld_called_tile34(meld, tiles_34)
    called_tile = _tile34_to_meld_suit_and_number(called_tile_34)
    if called_tile is None or called_tile[0] != suit_index:
        return False

    called_offset = called_tile[1] - start_number
    if called_offset not in (0, 1, 2):
        return False
    if called_offset == 1:
        return False
    if (start_number == 1 and called_offset == 2) or (start_number == 7 and called_offset == 0):
        return False
    return True


def _build_base_meld_group_layout(
    img_table: TileImageTable,
    meld: Meld,
    *,
    tile_scale_multiplier: float = 1.0,
) -> tuple[float, float, list[tuple[int, bool, float, float, int, int]]]:
    """自家向き基準で 1 面子分の牌配置を返す。"""

    arranged_tiles = _arrange_meld_tiles(meld)
    if not arranged_tiles:
        return 0.0, 0.0, []

    total_width = 0.0
    max_height = 0.0
    tile_layouts: list[tuple[int, bool, float, float, int, int]] = []
    for index, (tile_id, is_called_tile) in enumerate(arranged_tiles):
        image_player = Player.SHIMOCHA if is_called_tile else Player.JICHA
        tile_width, tile_height = _scaled_tile_size(
            *_tile_size(img_table, image_player, tile_id=tile_id),
            tile_scale_multiplier,
        )
        if index > 0:
            total_width += MELD_TILE_GAP
        tile_layouts.append((tile_id, is_called_tile, total_width, 0.0, tile_width, tile_height))
        total_width += tile_width
        max_height = max(max_height, tile_height)

    normalized_layouts = [
        (tile_id, is_called_tile, x, (max_height - tile_height) / 2, tile_width, tile_height)
        for tile_id, is_called_tile, x, _y, tile_width, tile_height in tile_layouts
    ]
    return total_width, max_height, normalized_layouts


def _build_rotated_meld_group_layout(
    img_table: TileImageTable,
    player: Player,
    meld: Meld,
    *,
    tile_scale_multiplier: float = 1.0,
) -> tuple[float, float, list[tuple[int, Player, float, float]]]:
    """回転後の実画像サイズ込みで、1 面子分の tight な描画レイアウトを返す。"""

    base_width, base_height, tile_layouts = _build_base_meld_group_layout(
        img_table,
        meld,
        tile_scale_multiplier=tile_scale_multiplier,
    )
    if not tile_layouts:
        return 0.0, 0.0, []

    quadrants = _meld_rotation_quadrants(player)
    image_quadrants = _meld_image_quadrants(player)
    rotated_layouts: list[tuple[int, Player, float, float, int, int]] = []
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    # 面子全体を回したあとで、実際に使う画像の幅高さを取り直して tight bbox を作る。
    for tile_id, is_called_tile, tile_x, tile_y, tile_width, tile_height in tile_layouts:
        base_player = Player.SHIMOCHA if is_called_tile else Player.JICHA
        image_player = _rotate_player(base_player, image_quadrants)
        image_width, image_height = _scaled_tile_size(
            *_tile_size(img_table, image_player, tile_id=tile_id),
            tile_scale_multiplier,
        )
        draw_x, draw_y = _rotate_meld_tile_rect(
            base_width,
            base_height,
            tile_x,
            tile_y,
            tile_width,
            tile_height,
            quadrants,
        )
        rotated_layouts.append((tile_id, image_player, draw_x, draw_y, image_width, image_height))
        min_x = min(min_x, draw_x)
        min_y = min(min_y, draw_y)
        max_x = max(max_x, draw_x + image_width)
        max_y = max(max_y, draw_y + image_height)

    group_width = max_x - min_x
    group_height = max_y - min_y
    normalized_layouts = [
        (tile_id, image_player, draw_x - min_x, draw_y - min_y)
        for tile_id, image_player, draw_x, draw_y, _image_width, _image_height in rotated_layouts
    ]
    return group_width, group_height, normalized_layouts


def _measure_meld_group(
    img_table: TileImageTable,
    player: Player,
    meld: Meld,
    *,
    tile_scale_multiplier: float = 1.0,
) -> tuple[float, float]:
    """座席向きへ回転後の 1 面子分の描画幅と高さを返す。"""

    group_width, group_height, _tile_layouts = _build_rotated_meld_group_layout(
        img_table,
        player,
        meld,
        tile_scale_multiplier=tile_scale_multiplier,
    )
    return group_width, group_height


def _rotate_meld_tile_rect(
    base_width: float,
    base_height: float,
    x: float,
    y: float,
    width: int,
    height: int,
    quadrants: int,
) -> tuple[float, float]:
    """自家向き基準の牌矩形を座席向きへ回した左上座標へ変換する。"""

    normalized_quadrants = quadrants % 4
    if normalized_quadrants == 0:
        return x, y
    if normalized_quadrants == 1:
        return base_height - (y + height), x
    if normalized_quadrants == 2:
        return base_width - (x + width), base_height - (y + height)
    return y, base_width - (x + width)


def _draw_meld_group(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    player: Player,
    meld: Meld,
    left: float,
    top: float,
    group_width: float,
    group_height: float,
    *,
    tile_scale_multiplier: float,
) -> None:
    """1面子分の牌画像を矩形内へ描く。"""

    resolved_group_width, resolved_group_height, tile_layouts = _build_rotated_meld_group_layout(
        img_table,
        player,
        meld,
        tile_scale_multiplier=tile_scale_multiplier,
    )
    for tile_id, image_player, draw_x, draw_y in tile_layouts:
        tile_image = _meld_tile_image(
            canvas,
            img_table,
            image_player,
            tile_id,
            tile_scale_multiplier=tile_scale_multiplier,
        )
        canvas.create_image(left + draw_x, top + draw_y, image=tile_image, anchor=tkinter.NW)

    if _is_ryanmen_chi_meld(meld):
        current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
        padding = max(1.0, MELD_RYANMEN_CHI_BORDER_PADDING * current_ui_scale)
        frame_width = group_width if group_width > 0 else resolved_group_width
        frame_height = group_height if group_height > 0 else resolved_group_height
        canvas.create_rectangle(
            left - padding,
            top - padding,
            left + frame_width + padding,
            top + frame_height + padding,
            outline=MELD_RYANMEN_CHI_BORDER,
            width=MELD_RYANMEN_CHI_BORDER_WIDTH,
        )


def _resolve_meld_fit(
    measured_primary_spans: Sequence[float],
    available_primary_span: float,
    base_tile_scale_multiplier: float,
) -> tuple[float, float]:
    """Return a fitted tile scale and group gap so all meld groups stay visible inside the zone."""

    if not measured_primary_spans:
        return base_tile_scale_multiplier, MELD_GROUP_GAP
    total_primary_span = sum(float(span) for span in measured_primary_spans)
    total_gap_span = MELD_GROUP_GAP * max(len(measured_primary_spans) - 1, 0)
    full_span = total_primary_span + total_gap_span
    if available_primary_span <= 0 or full_span <= 0 or full_span <= available_primary_span:
        return base_tile_scale_multiplier, MELD_GROUP_GAP
    fit_ratio = max(0.0, min(1.0, available_primary_span / full_span))
    return (
        base_tile_scale_multiplier * fit_ratio,
        MELD_GROUP_GAP * fit_ratio,
    )


def _draw_horizontal_melds(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    rect: tuple[float, float, float, float],
    melds: Sequence[Meld],
    player: Player,
    align: str,
) -> None:
    """横長帯に面子を横並びで描く。"""

    if rect[2] - rect[0] <= MELD_ZONE_MARGIN * 2 or rect[3] <= rect[1]:
        return
    valid_melds = [meld for meld in melds if meld.tiles_37]
    if not valid_melds:
        return

    base_tile_scale_multiplier = float(_current_layout_tuning(canvas).meld_tile_scale)
    measured_groups = [
        (
            _measure_meld_group(
                img_table,
                player,
                meld,
                tile_scale_multiplier=base_tile_scale_multiplier,
            ),
            meld,
        )
        for meld in valid_melds
    ]
    available_width = max(rect[2] - rect[0] - MELD_ZONE_MARGIN * 2, 0)
    tile_scale_multiplier, group_gap = _resolve_meld_fit(
        [group_width for (group_width, _group_height), _meld in measured_groups],
        available_width,
        base_tile_scale_multiplier,
    )
    if abs(tile_scale_multiplier - base_tile_scale_multiplier) > 0.001:
        measured_groups = [
            (
                _measure_meld_group(
                    img_table,
                    player,
                    meld,
                    tile_scale_multiplier=tile_scale_multiplier,
                ),
                meld,
            )
            for meld in valid_melds
        ]
    total_width = sum(group_size[0] for group_size, _meld in measured_groups)
    total_width += group_gap * max(len(measured_groups) - 1, 0)
    if align == "right":
        cursor_x = max(rect[0] + MELD_ZONE_MARGIN, rect[2] - MELD_ZONE_MARGIN - total_width)
    else:
        cursor_x = rect[0] + MELD_ZONE_MARGIN
    for (group_width, group_height), meld in measured_groups:
        group_top = rect[1] + max((rect[3] - rect[1] - group_height) / 2, 0)
        _draw_meld_group(
            canvas,
            img_table,
            player,
            meld,
            cursor_x,
            group_top,
            group_width,
            group_height,
            tile_scale_multiplier=tile_scale_multiplier,
        )
        cursor_x += group_width + group_gap


def _draw_vertical_melds(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    rect: tuple[float, float, float, float],
    melds: Sequence[Meld],
    player: Player,
    align: str,
) -> None:
    """縦帯に面子を縦方向へ積んで描く。"""

    if rect[2] - rect[0] <= MELD_ZONE_MARGIN * 2 or rect[3] <= rect[1]:
        return
    valid_melds = [meld for meld in melds if meld.tiles_37]
    if not valid_melds:
        return

    base_tile_scale_multiplier = float(_current_layout_tuning(canvas).meld_tile_scale)
    measured_groups = [
        (
            _measure_meld_group(
                img_table,
                player,
                meld,
                tile_scale_multiplier=base_tile_scale_multiplier,
            ),
            meld,
        )
        for meld in valid_melds
    ]
    available_height = max(rect[3] - rect[1] - MELD_ZONE_MARGIN * 2, 0)
    tile_scale_multiplier, group_gap = _resolve_meld_fit(
        [group_height for (_group_width, group_height), _meld in measured_groups],
        available_height,
        base_tile_scale_multiplier,
    )
    if abs(tile_scale_multiplier - base_tile_scale_multiplier) > 0.001:
        measured_groups = [
            (
                _measure_meld_group(
                    img_table,
                    player,
                    meld,
                    tile_scale_multiplier=tile_scale_multiplier,
                ),
                meld,
            )
            for meld in valid_melds
        ]
    total_height = sum(group_size[1] for group_size, _meld in measured_groups)
    total_height += group_gap * max(len(measured_groups) - 1, 0)
    if align == "bottom":
        cursor_y = max(rect[1] + MELD_ZONE_MARGIN, rect[3] - MELD_ZONE_MARGIN - total_height)
    else:
        cursor_y = rect[1] + MELD_ZONE_MARGIN

    for (group_width, group_height), meld in measured_groups:
        if player == Player.SHIMOCHA:
            group_left = max(rect[0] + MELD_ZONE_MARGIN, rect[2] - MELD_ZONE_MARGIN - group_width)
        else:
            group_left = rect[0] + MELD_ZONE_MARGIN
        _draw_meld_group(
            canvas,
            img_table,
            player,
            meld,
            group_left,
            cursor_y,
            group_width,
            group_height,
            tile_scale_multiplier=tile_scale_multiplier,
        )
        cursor_y += group_height + group_gap


def _draw_melds(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    melds_by_player: SeatMeldMap,
    layout: dict[str, object],
) -> None:
    """4方向の鳴き情報を専用帯へ描く。"""

    meld_rects = layout["meld_rects"]
    _draw_horizontal_melds(
        canvas,
        img_table,
        meld_rects[Player.TOIMEN],
        list(melds_by_player.get(Player.TOIMEN, [])),
        Player.TOIMEN,
        align="left",
    )
    _draw_horizontal_melds(
        canvas,
        img_table,
        meld_rects[Player.JICHA],
        list(melds_by_player.get(Player.JICHA, [])),
        Player.JICHA,
        align="right",
    )
    _draw_vertical_melds(
        canvas,
        img_table,
        meld_rects[Player.SHIMOCHA],
        list(melds_by_player.get(Player.SHIMOCHA, [])),
        Player.SHIMOCHA,
        align="top",
    )
    _draw_vertical_melds(
        canvas,
        img_table,
        meld_rects[Player.KAMICHA],
        list(melds_by_player.get(Player.KAMICHA, [])),
        Player.KAMICHA,
        align="bottom",
    )


def _draw_discards(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    discard_map: Mapping[Player, Iterable[Discard]],
    discard_red_tint_indices_by_seat: Mapping[int, frozenset[int]],
    layout: dict[str, object],
    visible_summary: VisibleTileSummary,
    player_push_alert_percentages: Mapping[int, Mapping[str, object]] | None = None,
    melds_by_player: Mapping[Player, Iterable[Meld]] | None = None,
    round_events: Sequence[object] | None = None,
) -> None:
    """4方向の捨て牌を、それぞれの向きに合わせて並べる。"""
    canvas.discard_tile_selection_click_specs = []
    # 自家向き牌と横向き牌のサイズから、並べるピッチを作る。
    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    tuning = _current_layout_tuning(canvas)
    effective_discard_ui_scale = current_ui_scale * float(tuning.discard_tile_scale)
    tighten_x = _scaled_length(DISCARD_X_TIGHTEN, effective_discard_ui_scale, minimum=2)
    tighten_y = _scaled_length(DISCARD_Y_TIGHTEN, effective_discard_ui_scale, minimum=2)
    bottom_width, bottom_height = _scaled_tile_size(
        *_tile_size(img_table, Player.JICHA),
        float(tuning.discard_tile_scale),
    )
    side_width, side_height = _scaled_tile_size(
        *_tile_size(img_table, Player.SHIMOCHA),
        float(tuning.discard_tile_scale),
    )
    # 捨て牌画像の透明余白ぶんだけピッチを詰めて、河の見た目を少し密にする。
    bottom_col_step = max(1, bottom_width - tighten_x)
    bottom_row_step = max(1, bottom_height - tighten_y)
    side_col_step = max(1, side_height - tighten_y)
    side_row_step = max(1, side_width - tighten_x)

    # 座席ごとに「どこから」「どちら向きへ」牌を並べるかを定義する。
    discard_rects = layout["discard_rects"]
    layouts = {
        Player.JICHA: {
            "origin": (discard_rects[Player.JICHA][0], discard_rects[Player.JICHA][1]),
            "col_step": (bottom_col_step, 0),
            "row_step": (0, bottom_row_step),
            "anchor": tkinter.NW,
        },
        Player.TOIMEN: {
            "origin": (discard_rects[Player.TOIMEN][2], discard_rects[Player.TOIMEN][3]),
            "col_step": (-bottom_col_step, 0),
            "row_step": (0, -bottom_row_step),
            "anchor": tkinter.SE,
        },
        Player.SHIMOCHA: {
            "origin": (discard_rects[Player.SHIMOCHA][0], discard_rects[Player.SHIMOCHA][3]),
            "col_step": (0, -side_col_step),
            "row_step": (side_row_step, 0),
            "anchor": tkinter.SW,
        },
        Player.KAMICHA: {
            "origin": (discard_rects[Player.KAMICHA][2], discard_rects[Player.KAMICHA][1]),
            "col_step": (0, side_col_step),
            "row_step": (-side_row_step, 0),
            "anchor": tkinter.NE,
        },
    }

    visible_count_tiles_34 = (
        {
            tile_34: "three" for tile_34 in visible_summary.three_visible_tiles
        }
        if THREE_VISIBLE_MARKERS_ENABLED
        else {}
    )
    visible_count_tiles_34.update(
        {tile_34: "four" for tile_34 in visible_summary.four_visible_tiles}
    )
    multi_player_lag_tiles_34 = _collect_multi_player_lag_tiles_34(discard_map)
    bridge_status = _bridge_status_snapshot(canvas)
    bridge_toggle_overrides = dict(getattr(canvas, "bridge_toggle_active_overrides", {}))
    naki_disabled_override_active = bridge_toggle_overrides.get(BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID)
    # Awaseuchi flags depend only on public river/meld/dora state. Cache the result per live
    # refresh token so resize and idle redraws do not rebuild/sort the entire event stream.
    same_jun_match_indices_by_seat: dict[int, frozenset[int]] = {}
    if AWASEUCHI_MARKERS_ENABLED:
        same_jun_match_indices_by_seat = _same_jun_marker_indices_by_seat(
            canvas,
            discard_map,
            melds_by_player,
            round_events,
        )
    push_marker_indices_by_seat = _push_discard_marker_indices_by_seat(player_push_alert_percentages)

    # 各座席について、最大18枚までの捨て牌を 6x3 ベースで配置する。
    for player, layout in layouts.items():
        discards = list(discard_map.get(player, []))
        highlighted_indices = discard_red_tint_indices_by_seat.get(int(player), frozenset())
        peak_thinking_time_index = _peak_thinking_time_discard_local_index(discards)
        same_jun_match_indices = same_jun_match_indices_by_seat.get(int(player), frozenset())
        for idx, discard in enumerate(discards[:18]):
            # 6枚ごとに折り返すため、列と行へ変換する。
            col = idx % 6
            row = idx // 6
            x = layout["origin"][0] + layout["col_step"][0] * col + layout["row_step"][0] * row
            y = layout["origin"][1] + layout["col_step"][1] * col + layout["row_step"][1] * row
            discard_tile_34_index = tile37_to_tile34_index(discard.tile_id)
            discard_tint_kind = _discard_tile_tint_kind(
                discard,
                discard_tile_34_index,
                should_red_tint=idx in highlighted_indices,
                visible_summary=visible_summary,
            )
            tile_image = _discard_tile_image(
                canvas,
                img_table,
                player,
                discard,
                tint_kind=discard_tint_kind,
            )
            canvas.create_image(
                x,
                y,
                image=tile_image,
                anchor=layout["anchor"],
            )
            left, top, right, bottom = _image_bounds_from_anchor(
                x,
                y,
                tile_image.width(),
                tile_image.height(),
                layout["anchor"],
            )
            if discard_tile_34_index is not None:
                canvas.discard_tile_selection_click_specs.append(
                    DiscardTileSelectionClickSpec(
                        tile_34_index=int(discard_tile_34_index),
                        tile_37=int(discard.tile_id),
                        rect=(left, top, right, bottom),
                    )
                )
            discard_tile_34 = tile37_to_tile34(discard.tile_id)
            visible_count_marker_kind = visible_count_tiles_34.get(discard_tile_34, "none")
            should_draw_visible_count_marker = (
                _visible_count_marker_style(visible_count_marker_kind) is not None
                and _should_draw_discard_visible_count_marker(discard)
            )
            should_draw_lag_marker = (
                not _is_riseki_completion_discard(discard)
                and _is_visual_lag_flag(discard.lagged)
                and not discard.called
            )
            should_draw_push_marker = (
                _discard_global_index(discard, idx)
                in push_marker_indices_by_seat.get(int(player), frozenset())
            )
            should_draw_same_jun_match_marker = idx in same_jun_match_indices
            should_draw_peak_thinking_time_marker = idx == peak_thinking_time_index
            discard_border_kind = _discard_border_kind(discard)
            lag_marker_color = _lag_marker_color(
                player,
                discard,
                multi_player_lag_tiles_34,
                bridge_status=bridge_status,
                naki_disabled_override_active=naki_disabled_override_active,
            )
            lag_marker_entry_key = _lag_marker_reference_entry_key(
                getattr(canvas, "current_round_identity", None),
                player,
                discard,
                idx,
            )
            lag_marker_base_kind = _lag_marker_base_kind_from_color(lag_marker_color)
            if (
                discard_border_kind != "none"
                or should_draw_visible_count_marker
                or should_draw_lag_marker
                or should_draw_push_marker
                or should_draw_same_jun_match_marker
                or should_draw_peak_thinking_time_marker
            ):
                if discard_border_kind == "called":
                    _draw_called_discard_border(canvas, left, top, right, bottom)
                elif discard_border_kind == "post_call_tedashi":
                    _draw_post_call_tedashi_discard_border(canvas, left, top, right, bottom)
                if should_draw_visible_count_marker:
                    _draw_visible_count_marker(
                        canvas,
                        player,
                        left,
                        top,
                        right,
                        bottom,
                        visible_count_marker_kind,
                    )
                if should_draw_lag_marker:
                    _draw_lag_marker(
                        canvas,
                        player,
                        left,
                        top,
                        right,
                        bottom,
                        entry_key=lag_marker_entry_key,
                        base_kind=lag_marker_base_kind,
                        color=lag_marker_color,
                    )
                if should_draw_push_marker:
                    _draw_push_discard_marker(
                        canvas,
                        player,
                        left,
                        top,
                        right,
                        bottom,
                    )
                if should_draw_same_jun_match_marker:
                    _draw_same_jun_match_marker(
                        canvas,
                        player,
                        left,
                        top,
                        right,
                        bottom,
                    )
                if should_draw_peak_thinking_time_marker:
                    _draw_peak_thinking_time_marker(
                        canvas,
                        player,
                        left,
                        top,
                        right,
                        bottom,
                    )
            if getattr(discard, "riichi_marker_before", False):
                _draw_riichi_stick_marker(
                    canvas,
                    player,
                    left,
                    top,
                    right,
                    bottom,
                )


def _draw_hand(
    canvas: tkinter.Canvas,
    img_table: TileImageTable,
    rect: tuple[float, float, float, float],
    hand_tiles: Sequence[int],
    hand_draw_tile: int | None,
    dora_indicator_tiles: Sequence[int],
    hand_recommendation_panel: HandRecommendationPanelData,
    hand_response_panel_state: HandResponsePanelState,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    visible_summary: VisibleTileSummary,
    self_hand_value_alert: SelfHandValueAlertState,
) -> None:
    """自家手牌エリアに13枚手牌と14枚目ツモ牌を描く。"""
    left, top, right, bottom = rect
    hand_bridge_click_specs: list[SelfHandBridgeClickSpec] = []
    tile_width, tile_height = _tile_size(img_table, Player.JICHA)
    gap = HAND_TILE_GAP
    has_draw_tile = bool(hand_tiles) and hand_draw_tile is not None and hand_tiles[-1] == hand_draw_tile
    concealed_tiles = list(hand_tiles[:-1]) if has_draw_tile else list(hand_tiles)
    draw_tile = hand_tiles[-1] if has_draw_tile else None
    normalized_hand_danger_percentages = [
        _normalize_hand_danger_percentages(percentages)
        for percentages in hand_danger_percentages
    ]
    while len(normalized_hand_danger_percentages) < len(hand_tiles):
        normalized_hand_danger_percentages.append(_normalize_hand_danger_percentages(None))
    canvas.current_hand_danger_percentages_for_response = tuple(normalized_hand_danger_percentages)
    concealed_danger_percentages = (
        normalized_hand_danger_percentages[:-1]
        if has_draw_tile
        else normalized_hand_danger_percentages
    )
    draw_danger_percentages = (
        normalized_hand_danger_percentages[-1]
        if has_draw_tile
        else _normalize_hand_danger_percentages(None)
    )
    # 手牌列は左端を固定し、ツモ牌が増えても既存13枚の位置がずれないようにする。
    start_x = left
    baseline_y = bottom - HAND_DANGER_BAR_BLOCK_HEIGHT
    hand_visual_top = baseline_y - tile_height
    visible_count_tiles_34 = (
        {
            tile_34: "three" for tile_34 in visible_summary.three_visible_tiles
        }
        if THREE_VISIBLE_MARKERS_ENABLED
        else {}
    )
    visible_count_tiles_34.update(
        {tile_34: "four" for tile_34 in visible_summary.four_visible_tiles}
    )
    hand_visual_right = start_x

    # ツモ牌以外は理牌済みの通常手牌列として描く。
    for idx, tile_id in enumerate(concealed_tiles):
        x = start_x + idx * (tile_width + gap)
        tile_image = _hand_tile_image(
            canvas,
            img_table,
            tile_id,
            (
                concealed_danger_percentages[idx]
                if idx < len(concealed_danger_percentages)
                else _normalize_hand_danger_percentages(None)
            ),
        )
        canvas.create_image(
            x,
            baseline_y,
            image=tile_image,
            anchor=tkinter.SW,
        )
        hand_visual_right = max(hand_visual_right, x + tile_image.width())
        visible_count_marker_kind = visible_count_tiles_34.get(tile37_to_tile34(tile_id), "none")
        if _visible_count_marker_style(visible_count_marker_kind) is not None:
            left, top, right, bottom = _image_bounds_from_anchor(
                x,
                baseline_y,
                tile_image.width(),
                tile_image.height(),
                tkinter.SW,
            )
            _draw_visible_count_marker(
                canvas,
                Player.JICHA,
                left,
                top,
                right,
                bottom,
                visible_count_marker_kind,
            )
        left, top, right, bottom = _image_bounds_from_anchor(
            x,
            baseline_y,
            tile_image.width(),
            tile_image.height(),
            tkinter.SW,
        )
        hand_bridge_click_specs.append(
            SelfHandBridgeClickSpec(
                rect=(left, top, right, bottom),
                hand_index=idx,
                tile_37=int(tile_id),
            )
        )
        _draw_self_hand_honor_visible_count(
            canvas,
            left,
            top,
            right,
            bottom,
            _self_hand_honor_visible_count(tile_id, visible_summary),
        )
        _draw_hand_danger_bars(
            canvas,
            x,
            tile_image.width(),
            baseline_y,
            (
                concealed_danger_percentages[idx]
                if idx < len(concealed_danger_percentages)
                else _normalize_hand_danger_percentages(None)
            ),
        )
    # ツモ牌があれば、常に一番右へ少し離して描く。
    if draw_tile is not None:
        draw_x = start_x + len(concealed_tiles) * (tile_width + gap) + (16 if concealed_tiles else 0)
        draw_image = _hand_tile_image(
            canvas,
            img_table,
            draw_tile,
            draw_danger_percentages,
        )
        canvas.create_image(
            draw_x,
            baseline_y,
            image=draw_image,
            anchor=tkinter.SW,
        )
        hand_visual_right = max(hand_visual_right, draw_x + draw_image.width())
        visible_count_marker_kind = visible_count_tiles_34.get(tile37_to_tile34(draw_tile), "none")
        if _visible_count_marker_style(visible_count_marker_kind) is not None:
            left, top, right, bottom = _image_bounds_from_anchor(
                draw_x,
                baseline_y,
                draw_image.width(),
                draw_image.height(),
                tkinter.SW,
            )
            _draw_visible_count_marker(
                canvas,
                Player.JICHA,
                left,
                top,
                right,
                bottom,
                visible_count_marker_kind,
            )
        left, top, right, bottom = _image_bounds_from_anchor(
            draw_x,
            baseline_y,
            draw_image.width(),
            draw_image.height(),
            tkinter.SW,
        )
        hand_bridge_click_specs.append(
            SelfHandBridgeClickSpec(
                rect=(left, top, right, bottom),
                hand_index=len(concealed_tiles),
                tile_37=int(draw_tile),
            )
        )
        _draw_self_hand_honor_visible_count(
            canvas,
            left,
            top,
            right,
            bottom,
            _self_hand_honor_visible_count(draw_tile, visible_summary),
        )
        _draw_hand_danger_bars(
            canvas,
            draw_x,
            draw_image.width(),
            baseline_y,
            draw_danger_percentages,
        )

    canvas.self_hand_bridge_click_specs = hand_bridge_click_specs
    button_anchor_right = hand_visual_right
    if draw_tile is None:
        button_anchor_right += tile_width + HAND_RESPONSE_RESERVED_DRAW_SLOT_GAP
    canvas.hand_response_render_state = HandResponseRenderState(
        hand_rect=(float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])),
        button_anchor_right=float(button_anchor_right),
        hand_visual_top=float(hand_visual_top),
        baseline_y=float(baseline_y),
        dora_indicator_tiles=tuple(int(tile) for tile in dora_indicator_tiles),
        visible_summary=visible_summary,
        recommendation_request_tiles=tuple(
            int(tile)
            for tile in getattr(canvas, "current_recommendation_request_tiles", tuple(hand_tiles))
        ),
        hand_danger_percentages=tuple(normalized_hand_danger_percentages),
        round_identity=getattr(canvas, "current_round_identity", None),
        self_melds=tuple(getattr(canvas, "current_self_melds_for_hand_response", ())),
    )

    _draw_hand_response_button_and_panel(
        canvas,
        rect,
        button_anchor_right,
        hand_visual_top,
        baseline_y,
        dora_indicator_tiles,
        visible_summary,
        hand_recommendation_panel,
        hand_response_panel_state,
        self_hand_value_alert,
        canvas_tag=_HAND_RESPONSE_UI_TAG,
    )


def _draw_hand_response_button_and_panel(
    canvas: tkinter.Canvas,
    hand_rect: tuple[float, float, float, float],
    button_anchor_right: float,
    hand_visual_top: float,
    baseline_y: float,
    dora_indicator_tiles: Sequence[int],
    visible_summary: VisibleTileSummary | None,
    hand_recommendation_panel: HandRecommendationPanelData,
    hand_response_panel_state: HandResponsePanelState,
    self_hand_value_alert: SelfHandValueAlertState,
    *,
    canvas_tag: str | None = None,
    draw_common_table_situation_panel: bool = True,
) -> None:
    """Draw the hand-side button and, when toggled, the compact top-3 response panel."""

    item_tags = (str(canvas_tag),) if str(canvas_tag or "").strip() else ()

    def _create_rectangle(*args: object, **kwargs: object) -> int:
        if item_tags:
            kwargs["tags"] = item_tags
        return int(canvas.create_rectangle(*args, **kwargs))

    def _create_text(*args: object, **kwargs: object) -> int:
        if item_tags:
            kwargs["tags"] = item_tags
        return int(canvas.create_text(*args, **kwargs))

    def _create_image(*args: object, **kwargs: object) -> int:
        if item_tags:
            kwargs["tags"] = item_tags
        return int(canvas.create_image(*args, **kwargs))

    def _create_oval(*args: object, **kwargs: object) -> int:
        if item_tags:
            kwargs["tags"] = item_tags
        return int(canvas.create_oval(*args, **kwargs))

    left, top, right, bottom = hand_rect
    tuning = _current_layout_tuning(canvas)
    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    button_offset_x = _scaled_length(tuning.hand_response_button_offset_x, current_ui_scale)
    button_offset_y = _scaled_length(tuning.hand_response_button_offset_y, current_ui_scale)
    alert_gap = _scaled_length(HAND_SELF_ALERT_GAP, current_ui_scale, minimum=4)
    alert_width = _scaled_length(HAND_SELF_ALERT_WIDTH, current_ui_scale, minimum=56)
    dora_visible_gap = _scaled_length(HAND_SELF_DORA_VISIBLE_GAP, current_ui_scale, minimum=4)
    dora_visible_width = _scaled_length(HAND_SELF_DORA_VISIBLE_WIDTH, current_ui_scale, minimum=26)
    button_left = button_anchor_right + HAND_RESPONSE_PANEL_MARGIN + button_offset_x
    button_right = button_left + HAND_RESPONSE_BUTTON_WIDTH
    button_band_height = max(baseline_y - hand_visual_top, HAND_RESPONSE_BUTTON_HEIGHT)
    button_top = hand_visual_top + max(
        (button_band_height - HAND_RESPONSE_BUTTON_HEIGHT) / 2,
        0,
    )
    button_top += button_offset_y
    canvas_width = max(canvas.winfo_width(), WINDOW_MIN_WIDTH)
    canvas_height = max(canvas.winfo_height(), WINDOW_MIN_HEIGHT)
    button_left = max(
        2,
        min(
            button_left,
            canvas_width
            - HAND_RESPONSE_BUTTON_WIDTH
            - HAND_RESPONSE_BUTTON_GAP
            - HAND_BETAORI_RESPONSE_BUTTON_WIDTH
            - alert_gap
            - alert_width
            - dora_visible_gap
            - dora_visible_width
            - 2,
        ),
    )
    button_right = button_left + HAND_RESPONSE_BUTTON_WIDTH
    button_top = max(
        top + 2,
        min(button_top, min(bottom - HAND_RESPONSE_BUTTON_HEIGHT - 2, canvas_height - HAND_RESPONSE_BUTTON_HEIGHT - 2)),
    )
    button_bottom = button_top + HAND_RESPONSE_BUTTON_HEIGHT
    betaori_button_left = button_right + HAND_RESPONSE_BUTTON_GAP
    betaori_button_right = betaori_button_left + HAND_BETAORI_RESPONSE_BUTTON_WIDTH
    button_fill = (
        HAND_RESPONSE_BUTTON_ACTIVE_FILL
        if hand_response_panel_state.visible
        else HAND_RESPONSE_BUTTON_FILL
    )
    _create_rectangle(
        button_left,
        button_top,
        button_right,
        button_bottom,
        fill=button_fill,
        outline=HAND_RESPONSE_OUTLINE,
        width=1,
    )
    _create_text(
        (button_left + button_right) / 2,
        (button_top + button_bottom) / 2,
        text="AI TOP3",
        fill=HAND_RESPONSE_TEXT,
        font=HAND_RESPONSE_BUTTON_FONT,
    )
    canvas.hand_response_button_spec = HandResponseButtonSpec(
        rect=(button_left, button_top, button_right, button_bottom)
    )

    betaori_button_fill = (
        HAND_RESPONSE_BUTTON_ACTIVE_FILL
        if hand_response_panel_state.betaori_visible
        else HAND_RESPONSE_BUTTON_FILL
    )
    _create_rectangle(
        betaori_button_left,
        button_top,
        betaori_button_right,
        button_bottom,
        fill=betaori_button_fill,
        outline=HAND_RESPONSE_OUTLINE,
        width=1,
    )
    _create_text(
        (betaori_button_left + betaori_button_right) / 2,
        (button_top + button_bottom) / 2,
        text="ベタオリ",
        fill=HAND_RESPONSE_TEXT,
        font=HAND_RESPONSE_BUTTON_FONT,
    )
    canvas.hand_betaori_response_button_spec = HandResponseButtonSpec(
        rect=(betaori_button_left, button_top, betaori_button_right, button_bottom)
    )

    alert_left = betaori_button_right + alert_gap
    alert_right = alert_left + alert_width
    alert_fill = self_hand_value_alert.fill_color
    alert_outline = self_hand_value_alert.outline_color
    alert_text = self_hand_value_alert.label
    alert_text_fill = self_hand_value_alert.text_color
    _create_rectangle(
        alert_left,
        button_top,
        alert_right,
        button_bottom,
        fill=alert_fill,
        outline=alert_outline,
        width=1,
    )
    if self_hand_value_alert.dot_color:
        dot_center_x = alert_left + 10
        dot_center_y = (button_top + button_bottom) / 2
        _create_oval(
            dot_center_x - HAND_SELF_ALERT_DOT_RADIUS,
            dot_center_y - HAND_SELF_ALERT_DOT_RADIUS,
            dot_center_x + HAND_SELF_ALERT_DOT_RADIUS,
            dot_center_y + HAND_SELF_ALERT_DOT_RADIUS,
            fill=self_hand_value_alert.dot_color,
            outline="",
        )
        text_left = alert_left + 18
        text_anchor = tkinter.W
    else:
        text_left = (alert_left + alert_right) / 2
        text_anchor = tkinter.CENTER
    _create_text(
        text_left,
        (button_top + button_bottom) / 2,
        text=alert_text,
        fill=alert_text_fill,
        font=HAND_SELF_ALERT_FONT,
        anchor=text_anchor,
    )
    visible_dora_tile_count = _visible_dora_tile_count(dora_indicator_tiles, visible_summary)
    dora_fill, dora_outline, dora_text_fill = _self_hand_visible_dora_alert_colors(
        visible_dora_tile_count
    )
    dora_dot_color = _self_hand_visible_dora_alert_dot_color(visible_dora_tile_count)
    dora_left = alert_right + dora_visible_gap
    dora_right = dora_left + dora_visible_width
    _create_rectangle(
        dora_left,
        button_top,
        dora_right,
        button_bottom,
        fill=dora_fill,
        outline=dora_outline,
        width=1,
    )
    if dora_dot_color:
        dora_dot_center_x = dora_left + 10
        dora_dot_center_y = (button_top + button_bottom) / 2
        _create_oval(
            dora_dot_center_x - HAND_SELF_ALERT_DOT_RADIUS,
            dora_dot_center_y - HAND_SELF_ALERT_DOT_RADIUS,
            dora_dot_center_x + HAND_SELF_ALERT_DOT_RADIUS,
            dora_dot_center_y + HAND_SELF_ALERT_DOT_RADIUS,
            fill=dora_dot_color,
            outline="",
        )
        dora_text_left = dora_left + 18
        dora_text_anchor = tkinter.W
    else:
        dora_text_left = (dora_left + dora_right) / 2
        dora_text_anchor = tkinter.CENTER
    _create_text(
        dora_text_left,
        (button_top + button_bottom) / 2,
        text=_format_visible_dora_tile_count_label(visible_dora_tile_count),
        fill=dora_text_fill,
        font=HAND_SELF_DORA_VISIBLE_FONT,
        anchor=dora_text_anchor,
    )
    if draw_common_table_situation_panel:
        _draw_table_situation_common_panel(
            canvas,
            anchor_left=button_left,
            anchor_right=button_right,
            preferred_top=button_bottom + _scaled_length(TABLE_SITUATION_PANEL_GAP, current_ui_scale, minimum=4),
            fallback_bottom=button_top - _scaled_length(TABLE_SITUATION_PANEL_GAP, current_ui_scale, minimum=4),
        )

    if not hand_response_panel_state.visible and not hand_response_panel_state.betaori_visible:
        return

    def _draw_top3_panel(
        *,
        panel_right: float,
        panel_data: HandRecommendationPanelData,
        title: str,
        stack_index: int = 0,
    ) -> None:
        # ポップアップ本体はボタン上側を優先し、手牌帯への侵入を避ける。
        resolved_panel_right = min(canvas_width - 2, panel_right)
        panel_left = max(2, resolved_panel_right - HAND_RESPONSE_PANEL_WIDTH)
        panel_bottom = (
            button_top
            - HAND_RESPONSE_PANEL_MARGIN
            - HAND_RESPONSE_PANEL_RAISE
            - stack_index * (HAND_RESPONSE_PANEL_HEIGHT + 4)
        )
        panel_top = panel_bottom - HAND_RESPONSE_PANEL_HEIGHT
        if panel_top < 2:
            panel_top = button_bottom + HAND_RESPONSE_PANEL_MARGIN + stack_index * (HAND_RESPONSE_PANEL_HEIGHT + 4)
            panel_bottom = panel_top + HAND_RESPONSE_PANEL_HEIGHT
        if panel_bottom > canvas_height - 2:
            panel_bottom = canvas_height - 2
            panel_top = panel_bottom - HAND_RESPONSE_PANEL_HEIGHT

        _create_rectangle(
            panel_left,
            panel_top,
            resolved_panel_right,
            panel_bottom,
            fill=HAND_RESPONSE_FILL,
            outline=HAND_RESPONSE_OUTLINE,
            width=1,
        )

        rows = list(panel_data.items[:3])
        if rows:
            # 成功時は順位と期待値だけを上から詰めて表示する。
            for index, recommendation in enumerate(rows):
                row_y = panel_top + 12 + index * HAND_RESPONSE_ROW_GAP
                accent_color = (
                    HAND_RESPONSE_HIGHLIGHT
                    if _should_highlight_hand_recommendation_row(
                        panel_data,
                        recommendation,
                        index,
                    )
                    else HAND_RESPONSE_TEXT
                )
                _create_text(
                    panel_left + 8,
                    row_y,
                    text=f"{recommendation.rank}.",
                    fill=accent_color,
                    font=HAND_RESPONSE_ROW_FONT,
                    anchor=tkinter.NW,
                )
                tile_image = _hand_response_tile_image(canvas, recommendation.tile_37)
                image_left = panel_left + 28
                image_center_y = row_y + 7
                if tile_image is not None:
                    _create_image(
                        image_left,
                        image_center_y,
                        image=tile_image,
                        anchor=tkinter.W,
                    )
                    value_left = image_left + tile_image.width() + 8
                else:
                    _create_text(
                        image_left,
                        row_y,
                        text=recommendation.tile_text,
                        fill=accent_color,
                        font=HAND_RESPONSE_ROW_FONT,
                        anchor=tkinter.NW,
                    )
                    value_left = image_left + 26
                _create_text(
                    value_left,
                    row_y,
                    text=_format_hand_recommendation_value_text(recommendation),
                    fill=accent_color,
                    font=HAND_RESPONSE_ROW_FONT,
                    anchor=tkinter.NW,
                )
            return

        _create_text(
            panel_left + 8,
            panel_top + 8,
            text=title,
            fill=HAND_RESPONSE_TEXT,
            font=HAND_RESPONSE_TITLE_FONT,
            anchor=tkinter.NW,
        )
        _create_text(
            panel_left + 8,
            panel_top + 24,
            text=panel_data.subtitle_text,
            fill=HAND_RESPONSE_MUTED_TEXT,
            font=HAND_RESPONSE_SUBTITLE_FONT,
            anchor=tkinter.NW,
            width=max(HAND_RESPONSE_PANEL_WIDTH - 16, 1),
        )

        status_text = panel_data.status_text or "No response yet"
        _create_text(
            panel_left + 8,
            panel_top + 46,
            text=status_text,
            fill=HAND_RESPONSE_MUTED_TEXT,
            font=HAND_RESPONSE_ROW_FONT,
            anchor=tkinter.NW,
            width=max(HAND_RESPONSE_PANEL_WIDTH - 16, 1),
        )

    if hand_response_panel_state.visible:
        _draw_top3_panel(
            panel_right=button_right,
            panel_data=hand_recommendation_panel,
            title="Response Top 3",
            stack_index=0,
        )
    if hand_response_panel_state.betaori_visible:
        betaori_panel = _build_hand_betaori_top3_panel_data(
            getattr(canvas, "current_recommendation_request_tiles", ()),
            getattr(canvas, "current_hand_danger_percentages_for_response", ()),
            getattr(canvas, "current_hand_recommendation_request_context", PystyleDisplayContext()),
        )
        _draw_top3_panel(
            panel_right=betaori_button_right,
            panel_data=betaori_panel,
            title="ベタオリ Top 3",
            stack_index=(1 if hand_response_panel_state.visible else 0),
        )


def _redraw_hand_response_controls_if_possible(canvas: tkinter.Canvas) -> bool:
    """Refresh the AI TOP3 / SELF controls without rebuilding the whole board."""

    render_state = getattr(canvas, "hand_response_render_state", None)
    if not isinstance(render_state, HandResponseRenderState):
        return False
    if not canvas.winfo_exists() or bool(getattr(canvas, "redraw_in_progress", False)):
        return False
    panel_provider = getattr(canvas, "hand_recommendation_panel_provider", None)
    hand_recommendation_panel = (
        panel_provider()
        if callable(panel_provider)
        else getattr(canvas, "current_hand_recommendation_panel", HandRecommendationPanelData())
    )
    if not isinstance(hand_recommendation_panel, HandRecommendationPanelData):
        hand_recommendation_panel = HandRecommendationPanelData()
    self_hand_value_alert = _build_self_hand_value_alert_state(
        hand_recommendation_panel,
        render_state.recommendation_request_tiles,
        render_state.round_identity,
        render_state.self_melds,
    )
    if _should_evaluate_alert_audio_for_refresh_token(
        canvas,
        getattr(canvas, "current_refresh_token", None),
    ):
        _play_self_hand_value_alert_sound_if_needed(
            canvas,
            self_hand_value_alert,
        )
    canvas.current_hand_recommendation_panel = hand_recommendation_panel
    canvas.current_hand_danger_percentages_for_response = tuple(render_state.hand_danger_percentages)
    canvas.delete(_HAND_RESPONSE_UI_TAG)
    _draw_hand_response_button_and_panel(
        canvas,
        render_state.hand_rect,
        render_state.button_anchor_right,
        render_state.hand_visual_top,
        render_state.baseline_y,
        render_state.dora_indicator_tiles,
        render_state.visible_summary,
        hand_recommendation_panel,
        getattr(canvas, "hand_response_panel_state", HandResponsePanelState()),
        self_hand_value_alert,
        canvas_tag=_HAND_RESPONSE_UI_TAG,
        draw_common_table_situation_panel=False,
    )
    return True


def _redraw_live_async_regions_if_possible(
    canvas: tkinter.Canvas,
    *,
    hand_danger_percentages: Sequence[HandDangerPercentages],
    opponent_suji_panel_summaries: OpponentSujiPanelSummaries,
    player_push_alert_percentages: PlayerPushAlertPercentages,
    push_marker_alert_percentages: PlayerPushAlertPercentages,
    player_alert_indicators_by_seat: PlayerAlertIndicatorsBySeat,
    discard_red_tint_indices_by_seat: dict[int, frozenset[int]],
) -> bool:
    """Refresh the heavy live async regions without clearing the whole board."""

    render_state = getattr(canvas, "live_async_render_state", None)
    if not isinstance(render_state, LiveAsyncRenderState):
        return False
    if _inferred_visible_runtime_enabled(canvas):
        return False
    if not bool(getattr(canvas, "winfo_exists", lambda: False)()):
        return False

    visible_inference_summary, _unused_entries = _build_visible_tile_inference_summary_for_canvas(
        canvas,
        render_state.discard_map,
        render_state.visible_summary,
        getattr(canvas, "current_round_identity", None),
        discard_red_tint_indices_by_seat,
    )
    layout = render_state.layout
    detail_panel_state = getattr(canvas, "detail_panel_state", DetailPanelState())
    canvas.player_panel_button_specs = []
    canvas.lag_marker_reference_button_specs = []
    canvas.inferred_visible_tile_count_click_specs = []
    canvas.discard_tile_selection_click_specs = []
    canvas.self_hand_bridge_click_specs = []
    canvas.hand_response_button_spec = None
    canvas.hand_betaori_response_button_spec = None

    _redraw_side_panels_if_needed(
        canvas,
        getattr(canvas, "image_table", getattr(canvas, "base_image_table", None)),
        layout,
        render_state.discard_map,
        render_state.melds_by_player,
        render_state.dora_indicator_tiles,
        render_state.visible_summary,
        visible_inference_summary,
        render_state.hand_tiles,
        render_state.hand_draw_tile,
        hand_danger_percentages,
        opponent_suji_panel_summaries,
        player_push_alert_percentages,
        player_alert_indicators_by_seat,
        render_state.player_score_diffs_by_seat,
        render_state.player_names_by_seat,
        detail_panel_state,
    )

    _delete_canvas_items_by_tags(canvas, _LIVE_ASYNC_DISCARD_TAG)
    discard_previous_items = _capture_canvas_item_ids(canvas)
    _draw_discards(
        canvas,
        getattr(canvas, "image_table", getattr(canvas, "base_image_table", None)),
        render_state.discard_map,
        discard_red_tint_indices_by_seat,
        layout,
        render_state.visible_summary,
        push_marker_alert_percentages,
        render_state.melds_by_player,
        render_state.round_events,
    )
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_ASYNC_DISCARD_TAG,
        previous_item_ids=discard_previous_items,
    )

    _delete_canvas_items_by_tags(canvas, _LIVE_ASYNC_HAND_TAG, _HAND_RESPONSE_UI_TAG)
    hand_previous_items = _capture_canvas_item_ids(canvas)
    _draw_hand(
        canvas,
        getattr(canvas, "image_table", getattr(canvas, "base_image_table", None)),
        tuple(float(value) for value in layout["hand_rect"]),
        render_state.hand_tiles,
        render_state.hand_draw_tile,
        render_state.dora_indicator_tiles,
        render_state.hand_recommendation_panel,
        getattr(canvas, "hand_response_panel_state", HandResponsePanelState()),
        hand_danger_percentages,
        render_state.visible_summary,
        render_state.self_hand_value_alert,
    )
    _tag_new_canvas_items(
        canvas,
        tag=_LIVE_ASYNC_HAND_TAG,
        previous_item_ids=hand_previous_items,
    )
    canvas.current_player_names_by_seat = render_state.player_names_by_seat
    canvas.current_player_alert_indicators_by_seat = player_alert_indicators_by_seat
    return True


def _draw_table_situation_common_panel(
    canvas: tkinter.Canvas,
    *,
    anchor_left: float,
    anchor_right: float,
    preferred_top: float,
    fallback_bottom: float,
) -> None:
    """Draw the hand-side common situation table below the AI controls."""

    if not TABLE_SITUATION_ENABLED or not bool(getattr(canvas, "table_situation_panels_visible", True)):
        return

    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    panel_width = _scaled_length(TABLE_SITUATION_COMMON_PANEL_WIDTH, current_ui_scale, minimum=108)
    panel_height = _scaled_length(TABLE_SITUATION_COMMON_PANEL_HEIGHT, current_ui_scale, minimum=74)
    right_shift = _scaled_length(TABLE_SITUATION_COMMON_PANEL_RIGHT_SHIFT, current_ui_scale, minimum=12)
    canvas_width = max(canvas.winfo_width(), WINDOW_MIN_WIDTH)
    canvas_height = max(canvas.winfo_height(), WINDOW_MIN_HEIGHT)
    total_width = panel_width
    total_height = panel_height
    block_right = max(total_width + 2.0, min(float(anchor_right) + right_shift, canvas_width - 2.0))
    block_left = max(2.0, block_right - total_width)
    block_top = float(preferred_top)
    if block_top + total_height > canvas_height - 2:
        block_top = max(2.0, float(fallback_bottom) - total_height)

    resolved_scores = _normalize_table_situation_display_scores_by_seat(
        getattr(canvas, "table_situation_resolved_scores_by_seat", {})
    )
    common_scores = _aggregate_table_situation_scores(resolved_scores)
    panel_rect = (
        block_left,
        block_top,
        block_left + panel_width,
        block_top + panel_height,
    )
    _draw_table_situation_panel(
        canvas,
        rect=panel_rect,
        title=TABLE_SITUATION_COMMON_LABEL,
        scores=common_scores,
        seat=None,
    )


def _draw_table_situation_seat_panels(
    canvas: tkinter.Canvas,
    layout: Mapping[str, object],
) -> None:
    """Draw one compact manual situation table between each opponent panel and meld area."""

    if not TABLE_SITUATION_ENABLED or not bool(getattr(canvas, "table_situation_panels_visible", True)):
        return

    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    panel_width = _scaled_length(TABLE_SITUATION_SEAT_PANEL_WIDTH, current_ui_scale, minimum=88)
    panel_height = _scaled_length(TABLE_SITUATION_SEAT_PANEL_HEIGHT, current_ui_scale, minimum=84)
    inference_rects = layout.get("player_inference_rects", {})
    resolved_scores = _normalize_table_situation_display_scores_by_seat(
        getattr(canvas, "table_situation_resolved_scores_by_seat", {})
    )

    canvas_width = max(canvas.winfo_width(), WINDOW_MIN_WIDTH)
    canvas_height = max(canvas.winfo_height(), WINDOW_MIN_HEIGHT)
    for seat in HAND_DANGER_BAR_SEAT_ORDER:
        inference_rect = inference_rects.get(int(seat))
        if inference_rect is None:
            continue
        available_left, available_top, available_right, available_bottom = (
            float(inference_rect[0]),
            float(inference_rect[1]),
            float(inference_rect[2]),
            float(inference_rect[3]),
        )
        available_width = available_right - available_left
        available_height = available_bottom - available_top
        if available_width <= 10 or available_height <= 10:
            continue
        resolved_panel_width = min(panel_width, max(available_width, 48.0))
        resolved_panel_height = min(panel_height, max(available_height, 44.0))
        rect = (
            available_left + (available_width - resolved_panel_width) / 2,
            available_top + (available_height - resolved_panel_height) / 2,
            available_left + (available_width + resolved_panel_width) / 2,
            available_top + (available_height + resolved_panel_height) / 2,
        )
        if rect is None:
            continue
        left, top, right, bottom = rect
        clamped_rect = (
            max(2.0, min(left, canvas_width - resolved_panel_width - 2.0)),
            max(2.0, min(top, canvas_height - resolved_panel_height - 2.0)),
            0.0,
            0.0,
        )
        clamped_rect = (
            clamped_rect[0],
            clamped_rect[1],
            clamped_rect[0] + resolved_panel_width,
            clamped_rect[1] + resolved_panel_height,
        )
        _draw_table_situation_panel(
            canvas,
            rect=clamped_rect,
            title="",
            scores=resolved_scores.get(
                int(seat),
                tuple(0.0 for _unused_index in range(TABLE_SITUATION_BLOCK_COUNT)),
            ),
            seat=int(seat),
        )


def _draw_table_situation_panel(
    canvas: tkinter.Canvas,
    *,
    rect: tuple[float, float, float, float],
    title: str,
    scores: Sequence[object],
    seat: int | None,
) -> None:
    """Draw one compact 3x3+honor manual situation table."""

    left, top, right, bottom = rect
    if right <= left or bottom <= top:
        return
    current_ui_scale = float(getattr(canvas, "current_ui_scale", 1.0))
    padding = _scaled_length(6, current_ui_scale, minimum=4)
    cell_gap = _scaled_length(TABLE_SITUATION_CELL_GAP, current_ui_scale, minimum=2)
    row_label_width = _scaled_length(12, current_ui_scale, minimum=10)
    has_title = bool(str(title).strip())
    title_is_common = str(title).strip() == TABLE_SITUATION_COMMON_LABEL
    title_height = (
        _scaled_length(8 if title_is_common else 12, current_ui_scale, minimum=6 if title_is_common else 10)
        if has_title
        else 0
    )
    title_font = (
        TABLE_SITUATION_COMMON_TITLE_FONT
        if title_is_common
        else TABLE_SITUATION_TITLE_FONT
    )
    show_decimal_scores = seat is None or _table_situation_scores_have_fractional_component(scores)
    header_height = _scaled_length(10, current_ui_scale, minimum=8)
    bottom_row_height = _scaled_length(20, current_ui_scale, minimum=18)
    canvas.create_rectangle(
        left,
        top,
        right,
        bottom,
        fill=TABLE_SITUATION_FILL,
        outline=TABLE_SITUATION_OUTLINE,
        width=1,
    )
    if has_title:
        title_top = top + max(1.0, padding - (_scaled_length(3, current_ui_scale, minimum=2) if title_is_common else 0.0))
        canvas.create_text(
            left + padding,
            title_top,
            text=title,
            anchor=tkinter.NW,
            fill=TABLE_SITUATION_TEXT,
            font=title_font,
        )

    grid_left = left + padding + row_label_width
    grid_top = top + padding + title_height + header_height
    grid_width = max(right - grid_left - padding, 48)
    cell_width = max((grid_width - cell_gap * 2) / 3, 16.0)
    cell_height = max(
        (bottom - grid_top - bottom_row_height - padding - cell_gap * 2) / 3,
        15.0,
    )
    normalized_scores = [
        (
            _clamp_table_situation_display_score(scores[block_index] if block_index < len(scores) else 0)
            if show_decimal_scores
            else _clamp_table_situation_score(scores[block_index] if block_index < len(scores) else 0)
        )
        for block_index in range(TABLE_SITUATION_BLOCK_COUNT)
    ]

    for col_index, col_label in enumerate(TABLE_SITUATION_COL_LABELS):
        cell_left = grid_left + col_index * (cell_width + cell_gap)
        canvas.create_text(
            cell_left + cell_width / 2,
            top + padding + title_height + header_height / 2,
            text=col_label,
            anchor=tkinter.CENTER,
            fill=TABLE_SITUATION_MUTED_TEXT,
            font=TABLE_SITUATION_HEADER_FONT,
        )
    for row_index, row_label in enumerate(TABLE_SITUATION_ROW_LABELS):
        cell_top = grid_top + row_index * (cell_height + cell_gap)
        canvas.create_text(
            left + padding + row_label_width / 2,
            cell_top + cell_height / 2,
            text=row_label,
            anchor=tkinter.CENTER,
            fill=TABLE_SITUATION_MUTED_TEXT,
            font=TABLE_SITUATION_HEADER_FONT,
        )
        for col_index in range(3):
            block_index = row_index * 3 + col_index
            cell_left = grid_left + col_index * (cell_width + cell_gap)
            current_rect = (
                cell_left,
                cell_top,
                cell_left + cell_width,
                cell_top + cell_height,
            )
            _draw_table_situation_score_box(
                canvas,
                rect=current_rect,
                value=normalized_scores[block_index],
                force_decimal=show_decimal_scores,
            )
            if seat is not None:
                canvas.table_situation_cell_click_specs.append(
                    TableSituationCellClickSpec(
                        rect=current_rect,
                        seat=int(seat),
                        block_index=block_index,
                    )
                )

    honor_top = grid_top + 3 * (cell_height + cell_gap)
    honor_rect = (
        grid_left,
        honor_top,
        grid_left + cell_width * 2 + cell_gap,
        honor_top + bottom_row_height,
    )
    _draw_table_situation_score_box(
        canvas,
        rect=honor_rect,
        value=normalized_scores[9],
        label="字",
        force_decimal=show_decimal_scores,
    )
    if seat is not None:
        canvas.table_situation_cell_click_specs.append(
            TableSituationCellClickSpec(
                rect=honor_rect,
                seat=int(seat),
                block_index=9,
            )
        )

    total_rect = (
        honor_rect[2] + cell_gap,
        honor_top,
        right - padding,
        honor_top + bottom_row_height,
    )
    total_score = _table_situation_total(normalized_scores)
    total_fill, total_outline, total_text = _table_situation_total_colors(total_score)
    canvas.create_rectangle(
        total_rect[0],
        total_rect[1],
        total_rect[2],
        total_rect[3],
        fill=total_fill if seat is None else TABLE_SITUATION_TOTAL_FILL,
        outline=total_outline,
        width=1,
    )
    if seat is None:
        zero_suited_division = _table_situation_zero_suited_division(normalized_scores)
        total_mid_y = total_rect[1] + bottom_row_height / 2
        canvas.create_text(
            total_rect[0] + 4,
            total_mid_y - 5,
            text="Σ",
            anchor=tkinter.W,
            fill=total_text,
            font=TABLE_SITUATION_HEADER_FONT,
        )
        canvas.create_text(
            total_rect[2] - 4,
            total_mid_y - 5,
            text=_format_table_situation_total_text(total_score, force_decimal=True),
            anchor=tkinter.E,
            fill=total_text,
            font=TABLE_SITUATION_HEADER_FONT,
        )
        canvas.create_text(
            total_rect[0] + 4,
            total_mid_y + 5,
            text="Σ/n",
            anchor=tkinter.W,
            fill=TABLE_SITUATION_MUTED_TEXT,
            font=TABLE_SITUATION_HEADER_FONT,
        )
        canvas.create_text(
            total_rect[2] - 4,
            total_mid_y + 5,
            text=_format_table_situation_total_text(zero_suited_division, force_decimal=True),
            anchor=tkinter.E,
            fill=total_text,
            font=TABLE_SITUATION_HEADER_FONT,
        )
    else:
        canvas.create_text(
            total_rect[0] + 4,
            total_rect[1] + bottom_row_height / 2,
            text="Σ",
            anchor=tkinter.W,
            fill=TABLE_SITUATION_MUTED_TEXT,
            font=TABLE_SITUATION_HEADER_FONT,
        )
        canvas.create_text(
            total_rect[2] - 4,
            total_rect[1] + bottom_row_height / 2,
            text=_format_table_situation_total_text(total_score, force_decimal=show_decimal_scores),
            anchor=tkinter.E,
            fill=total_text,
            font=TABLE_SITUATION_TOTAL_FONT,
        )


def _draw_table_situation_score_box(
    canvas: tkinter.Canvas,
    *,
    rect: tuple[float, float, float, float],
    value: object,
    label: str = "",
    force_decimal: bool = False,
) -> None:
    """Draw one compact signed score cell used by the manual situation tables."""

    left, top, right, bottom = rect
    fill, outline, text_color = _table_situation_cell_colors(value)
    canvas.create_rectangle(
        left,
        top,
        right,
        bottom,
        fill=fill,
        outline=outline,
        width=1,
    )
    if label:
        canvas.create_text(
            left + 4,
            (top + bottom) / 2,
            text=label,
            anchor=tkinter.W,
            fill=TABLE_SITUATION_MUTED_TEXT,
            font=TABLE_SITUATION_HEADER_FONT,
        )
        text_anchor = tkinter.E
        text_x = right - 4
    else:
        text_anchor = tkinter.CENTER
        text_x = (left + right) / 2
    canvas.create_text(
        text_x,
        (top + bottom) / 2,
        text=_format_table_situation_total_text(value, force_decimal=force_decimal),
        anchor=text_anchor,
        fill=text_color,
        font=TABLE_SITUATION_CELL_FONT,
    )


def _hand_response_tile_image(
    canvas: tkinter.Canvas,
    tile_37: int | None,
) -> tkinter.PhotoImage | None:
    """Return one compact self-hand tile image for the AI recommendation popup."""

    if tile_37 is None or not (1 <= tile_37 <= N_TILES):
        return None

    # レスポンス欄は本文より少し小さい牌に固定し、再描画ごとにキャッシュ再利用する。
    tile_scale = max(
        0.5,
        min(1.0, getattr(canvas, "current_ui_scale", 1.0) * HAND_RESPONSE_TILE_SCALE),
    )
    cache_key = (tile_37, round(tile_scale, 3))
    cache: dict[tuple[int, float], tkinter.PhotoImage] = getattr(
        canvas,
        "hand_response_tile_image_cache",
        {},
    )
    cached_image = cache.get(cache_key)
    if cached_image is not None:
        return cached_image

    compact_image = build_tile_photoimage(
        canvas,
        tile_37,
        Player.JICHA,
        DrawType.TEDASHI,
        tile_scale=tile_scale,
    )
    cache[cache_key] = compact_image
    canvas.hand_response_tile_image_cache = cache
    return compact_image


def _draw_hand_danger_bars(
    canvas: tkinter.Canvas,
    tile_left: float,
    tile_width: int,
    baseline_y: float,
    danger_percentages: HandDangerPercentages,
) -> None:
    """Draw kamicha/toimen/shimocha danger percentages as colored bars below one tile."""

    if not any(danger_percentages.get(seat, {}).get("percentage", 0) > 0 for seat in HAND_DANGER_BAR_SEAT_ORDER):
        return

    total_bar_width = (
        len(HAND_DANGER_BAR_SEAT_ORDER) * HAND_DANGER_BAR_WIDTH
        + max(len(HAND_DANGER_BAR_SEAT_ORDER) - 1, 0) * HAND_DANGER_BAR_GAP
    )
    start_x = tile_left + (tile_width - total_bar_width) / 2
    bar_top = baseline_y + HAND_DANGER_BAR_TOP_MARGIN
    displayed_percentages: list[int] = []
    for index, seat in enumerate(HAND_DANGER_BAR_SEAT_ORDER):
        seat_metrics = danger_percentages.get(
            seat,
            {
                "percentage": 0,
                "numerator_count": 0.0,
                "denominator_count": 0.0,
            },
        )
        percentage = max(0, min(100, int(seat_metrics.get("percentage", 0))))
        displayed_percentages.append(percentage)
        if percentage <= 0:
            continue
        bar_percentage = min(percentage, HAND_DANGER_BAR_MAX_PERCENT)
        fill_height = max(
            HAND_DANGER_BAR_MIN_VISIBLE_HEIGHT,
            int(round(HAND_DANGER_BAR_MAX_HEIGHT * bar_percentage / HAND_DANGER_BAR_MAX_PERCENT)),
        )
        fill_height = min(fill_height, HAND_DANGER_BAR_MAX_HEIGHT)
        bar_left = start_x + index * (HAND_DANGER_BAR_WIDTH + HAND_DANGER_BAR_GAP)
        canvas.create_rectangle(
            bar_left,
            bar_top,
            bar_left + HAND_DANGER_BAR_WIDTH,
            bar_top + fill_height,
            fill=HAND_DANGER_BAR_COLOR_BY_SEAT[seat],
            outline="",
        )
    percentage_text_y = bar_top + HAND_DANGER_BAR_MAX_HEIGHT + HAND_DANGER_PERCENT_TEXT_TOP_MARGIN
    canvas.create_text(
        tile_left + tile_width / 2,
        percentage_text_y,
        text="/".join(str(percentage) for percentage in displayed_percentages),
        fill=TEXT_SECONDARY,
        font=HAND_DANGER_PERCENT_TEXT_FONT,
        anchor=tkinter.N,
    )
    numerator_text_y = percentage_text_y + HAND_DANGER_NUMERATOR_TEXT_TOP_MARGIN
    displayed_numerators = [
        _format_hand_danger_numerator(
            float(
                danger_percentages.get(
                    seat,
                    {
                        "percentage": 0,
                        "numerator_count": 0.0,
                        "denominator_count": 0.0,
                    },
                ).get("numerator_count", 0.0)
            )
        )
        for seat in HAND_DANGER_BAR_SEAT_ORDER
    ]
    canvas.create_text(
        tile_left + tile_width / 2,
        numerator_text_y,
        text="/".join(displayed_numerators),
        fill=TEXT_SECONDARY,
        font=HAND_DANGER_NUMERATOR_TEXT_FONT,
        anchor=tkinter.N,
    )


def initialize_game() -> None:
    """Placeholder for future round reset logic."""

    # 将来、局開始時の初期化処理をここに集約する想定。
    pass
