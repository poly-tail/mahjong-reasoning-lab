from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from capture.state import tile136_to_tile37

DEFAULT_TENHOU_UI_BRIDGE_HOST = "127.0.0.1"
DEFAULT_TENHOU_UI_BRIDGE_PORT = 8765
DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S = 2.5
# Bridge transport defaults intentionally stay localhost-only. The extension is not meant to become
# a remotely reachable automation server; it is just the browser-side executor for this local app.

# The extension only snapshots this curated list so its responsibility stays limited to
# "what buttons are currently visible on the Tenhou page" instead of trying to interpret game state.
TENHOU_UI_BRIDGE_CONTROL_IDS: tuple[int, ...] = (
    2360326,
    2098693,
    3670533,
    3671045,
    409606,
    409607,
    409604,
    409610,
    409609,
    409608,
    409614,
    409613,
    409612,
    401412,
    401416,
    401417,
    401414,
    401415,
    401418,
    401419,
    2359814,
    2359815,
    2359816,
    2360328,
    1574917,
    1574918,
    1572868,
)

TENHOU_UI_BRIDGE_APP_TOGGLE_CONTROL_IDS: tuple[int, ...] = (
    1183750,
    1183752,
    1183753,
    1183749,
)

# These labels are only local-side fallbacks. The extension prefers the live DOM text returned by
# `ui_snapshot`, because Tenhou may vary wording or visibility by mode.
TENHOU_UI_BRIDGE_CONTROL_LABELS: dict[int, str] = {
    2360326: "スキップ",
    2098693: "実行候補",
    3670533: "候補選択",
    3671045: "鳴き",
    409606: "ポン候補",
    409607: "ポン候補",
    409604: "カン候補",
    409610: "チー候補",
    409609: "チー候補",
    409608: "チー候補",
    409614: "チー候補",
    409613: "チー候補",
    409612: "チー候補",
    401412: "カン候補",
    401416: "カン候補",
    401417: "カン候補",
    401414: "カン候補",
    401415: "カン候補",
    401418: "カン候補",
    401419: "カン候補",
    2359814: "リーチ候補",
    2359815: "リーチ候補",
    2359816: "リーチ候補",
    2360328: "ロン",
    1574917: "候補",
    1574918: "候補",
    1572868: "候補",
}


TENHOU_UI_BRIDGE_APP_TOGGLE_CONTROL_LABELS: dict[int, str] = {
    1183750: "自動理牌",
    1183752: "自動和了",
    1183753: "ツモ切り",
    1183749: "鳴き無し",
}


def build_tenhou_ui_bridge_ws_url(
    host: str = DEFAULT_TENHOU_UI_BRIDGE_HOST,
    port: int = DEFAULT_TENHOU_UI_BRIDGE_PORT,
) -> str:
    """Return the ws:// URL shared by the local app and the MV3 service worker."""

    return f"ws://{str(host).strip()}:{int(port)}"


@dataclass(frozen=True)
class TenhouUiBridgeControl:
    """One visible candidate button returned by the extension snapshot."""

    # `text` is the raw label read from the DOM. `label` is the local app's normalized display text
    # so debug UIs can keep showing something even when Tenhou changes a caption or the DOM is blank.
    control_id: int
    visible: bool
    text: str = ""
    label: str = ""


@dataclass(frozen=True)
class TenhouUiBridgeToggleControl:
    """One persistent app-side bridge toggle mirrored from the page state."""

    control_id: int
    visible: bool = False
    available: bool = False
    active: bool = False
    text: str = ""
    label: str = ""


@dataclass(frozen=True)
class VisibleHandState:
    """Current self-hand order as shown on screen.

    `displayed_tiles_37` is enough for the current hand-index based executor.
    `displayed_tiles_136` is kept as an optional future hook so tile136-based callers can still map
    into the same displayed index without pushing that responsibility into the extension.
    """

    displayed_tiles_37: tuple[int, ...] = ()
    displayed_tiles_136: tuple[int | None, ...] = ()


@dataclass(frozen=True)
class TenhouUiBridgeStatus:
    """Current local-bridge status snapshot for diagnostics and optional debug UI."""

    # This status object is intentionally transport-only. It must not pretend to be the current
    # game state, because game-state truth still belongs to the packet-capture side of the app.
    ws_url: str
    listening: bool = False
    connected: bool = False
    extension_ready: bool = False
    last_error: str = ""
    last_event: str = ""
    last_sent_command: Mapping[str, Any] | None = None
    last_result: Mapping[str, Any] | None = None
    visible_controls: tuple[TenhouUiBridgeControl, ...] = ()
    toggle_controls: tuple[TenhouUiBridgeToggleControl, ...] = field(
        default_factory=lambda: normalize_bridge_toggle_controls(None)
    )


def control_id_to_label(control_id: int) -> str:
    """Return a stable local fallback label for one Tenhou control id."""

    normalized_control_id = int(control_id)
    return TENHOU_UI_BRIDGE_CONTROL_LABELS.get(
        normalized_control_id,
        f"control:{normalized_control_id}",
    )


def toggle_control_id_to_label(control_id: int) -> str:
    """Return a stable local fallback label for one persistent toggle control id."""

    normalized_control_id = int(control_id)
    return TENHOU_UI_BRIDGE_APP_TOGGLE_CONTROL_LABELS.get(
        normalized_control_id,
        f"toggle:{normalized_control_id}",
    )


def normalize_bridge_controls(raw_controls: Sequence[Mapping[str, Any]] | None) -> tuple[TenhouUiBridgeControl, ...]:
    """Normalize one extension-side `controls` payload into typed local records."""

    if not raw_controls:
        return ()
    normalized: list[TenhouUiBridgeControl] = []
    for raw_control in raw_controls:
        # The extension returns camelCase, but local tests and future tooling may pass snake_case.
        # Accept both so the protocol helper stays tolerant while the on-wire shape remains stable.
        try:
            control_id = int(raw_control.get("controlId", raw_control.get("control_id")))
        except (TypeError, ValueError):
            continue
        if control_id in TENHOU_UI_BRIDGE_APP_TOGGLE_CONTROL_LABELS:
            continue
        visible = bool(raw_control.get("visible", False))
        text = str(raw_control.get("text", "") or "").strip()
        normalized.append(
            TenhouUiBridgeControl(
                control_id=control_id,
                visible=visible,
                text=text,
                label=text or control_id_to_label(control_id),
            )
        )
    return tuple(normalized)


def _coerce_bridge_toggle_bool(raw_value: Any, *, default: bool = False) -> bool:
    """Parse one bridge toggle flag into a deterministic bool."""

    if raw_value is None:
        return bool(default)
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, (int, float)):
        return bool(raw_value)
    normalized_text = str(raw_value).strip().lower()
    if normalized_text in {"1", "true", "on", "yes", "enabled", "active"}:
        return True
    if normalized_text in {"0", "false", "off", "no", "disabled", "inactive"}:
        return False
    return bool(default)


def normalize_bridge_toggle_controls(
    raw_controls: Sequence[Mapping[str, Any]] | None,
) -> tuple[TenhouUiBridgeToggleControl, ...]:
    """Normalize persistent toggle state in the fixed app-side button order."""

    raw_by_id: dict[int, Mapping[str, Any]] = {}
    for raw_control in raw_controls or ():
        try:
            control_id = int(raw_control.get("controlId", raw_control.get("control_id")))
        except (AttributeError, TypeError, ValueError):
            continue
        if control_id not in TENHOU_UI_BRIDGE_APP_TOGGLE_CONTROL_LABELS:
            continue
        raw_by_id[control_id] = raw_control

    normalized: list[TenhouUiBridgeToggleControl] = []
    for control_id in TENHOU_UI_BRIDGE_APP_TOGGLE_CONTROL_IDS:
        raw_control = raw_by_id.get(control_id, {})
        text = str(raw_control.get("text", "") or "").strip()
        normalized.append(
            TenhouUiBridgeToggleControl(
                control_id=control_id,
                visible=bool(raw_control.get("visible", False)),
                available=_coerce_bridge_toggle_bool(raw_control.get("available"), default=False),
                active=_coerce_bridge_toggle_bool(raw_control.get("active"), default=False),
                text=text,
                label=toggle_control_id_to_label(control_id),
            )
        )
    return tuple(normalized)


def build_visible_hand_state(
    hand_tiles_37: Sequence[int] | None,
    hand_draw_tile_37: int | None = None,
    *,
    hand_tiles_136: Sequence[int] | None = None,
    hand_draw_tile_136: int | None = None,
) -> VisibleHandState:
    """Build one visible-hand snapshot in the same order the local UI renders it."""

    # The bridge executor clicks "what is currently shown at slot N". Because of that, the local
    # app has to preserve on-screen order here instead of sorting or normalizing the hand.
    displayed_tiles_37 = [int(tile) for tile in (hand_tiles_37 or ())]
    displayed_tiles_136 = [int(tile) for tile in (hand_tiles_136 or ())]
    # The renderer shows the draw tile at the end when present, so append it only when it is not
    # already included in the visible concealed-hand list.
    if hand_draw_tile_37 is not None and (
        not displayed_tiles_37 or displayed_tiles_37[-1] != int(hand_draw_tile_37)
    ):
        displayed_tiles_37.append(int(hand_draw_tile_37))
    if hand_draw_tile_136 is not None and (
        not displayed_tiles_136 or displayed_tiles_136[-1] != int(hand_draw_tile_136)
    ):
        displayed_tiles_136.append(int(hand_draw_tile_136))
    return VisibleHandState(
        displayed_tiles_37=tuple(displayed_tiles_37),
        displayed_tiles_136=tuple(displayed_tiles_136),
    )


def resolve_hand_index_by_tile37(
    visible_hand: VisibleHandState,
    tile_37: int,
    *,
    occurrence: int = 0,
) -> int | None:
    """Resolve one displayed hand index from a 37-id tile value and duplicate occurrence."""

    # Duplicate tiles are expected, so callers can specify which occurrence they want inside the
    # current left-to-right display order.
    target_tile = int(tile_37)
    target_occurrence = int(occurrence)
    if target_occurrence < 0:
        return None
    matched_indexes = [
        index
        for index, current_tile in enumerate(visible_hand.displayed_tiles_37)
        if int(current_tile) == target_tile
    ]
    # Pystyle recommendations can collapse red fives into their normal-five tile ids, while the
    # visible hand order in this app keeps red fives distinct. When the exact tile id is missing,
    # fall back within the same displayed five group so AUTO mode can still click the correct slot
    # without pushing tile-identity interpretation into the extension.
    if not matched_indexes:
        equivalent_tiles = _tile37_equivalent_display_ids(target_tile)
        matched_indexes = [
            index
            for index, current_tile in enumerate(visible_hand.displayed_tiles_37)
            if int(current_tile) in equivalent_tiles
        ]
    if target_occurrence >= len(matched_indexes):
        return None
    return matched_indexes[target_occurrence]


def _tile37_equivalent_display_ids(tile_37: int) -> tuple[int, ...]:
    """Return tile ids that share one displayed five slot group.

    Only the three five groups have relaxed matching. Every other tile must remain exact so the
    local app does not silently change the intended discard identity.
    """

    normalized_tile = int(tile_37)
    if normalized_tile in {5, 10}:
        return (5, 10)
    if normalized_tile in {15, 20}:
        return (15, 20)
    if normalized_tile in {25, 30}:
        return (25, 30)
    return (normalized_tile,)


def resolve_hand_index_by_tile136(
    visible_hand: VisibleHandState,
    tile_136: int,
) -> int | None:
    """Resolve one displayed hand index from an exact 136-id when available.

    If the 136-order is unavailable, the resolver falls back to tile37 so callers can still keep
    the same app-side API across mock/XML/live modes.
    """

    normalized_tile_136 = int(tile_136)
    if visible_hand.displayed_tiles_136:
        # Prefer exact 136 identity when the app knows it. This avoids ambiguity across duplicate
        # tiles and keeps future tile136-driven commands deterministic without changing the wire API.
        for index, current_tile in enumerate(visible_hand.displayed_tiles_136):
            if current_tile is not None and int(current_tile) == normalized_tile_136:
                return index
    tile_37 = tile136_to_tile37(normalized_tile_136)
    if tile_37 is None:
        return None
    return resolve_hand_index_by_tile37(visible_hand, tile_37)
