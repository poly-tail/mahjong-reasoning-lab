from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Optional
from urllib.parse import unquote

from sutehai import SutehaiTracker

# Legacy UI rendering still expects the 1..37 tile-id space backed by assets/tiles/{id}.png.
# The parser layer now also exposes spec-oriented zero-based helpers for normalised storage.
RED_TILE_IDS_136 = frozenset((16, 52, 88))
# RED_TILE_INDEX_BY_136 の対応表。
RED_TILE_INDEX_BY_136 = {
    16: 34,
    52: 35,
    88: 36,
}
# RED_TILE_MAP_136_TO_37 の対応表。
RED_TILE_MAP_136_TO_37 = {
    16: 10,
    52: 20,
    88: 30,
}
# SEAT_COUNT の定義。
SEAT_COUNT = 4
# LOCAL_RELATIVE_SEAT の定義。
LOCAL_RELATIVE_SEAT = 0
# RELATIVE_SEAT_LABELS の対応表。
RELATIVE_SEAT_LABELS = {
    0: "self",
    1: "shimocha",
    2: "toimen",
    3: "kamicha",
}
# UNRESOLVED_SPEC_TODOS の並びを定義する。
UNRESOLVED_SPEC_TODOS = (
    "LN / REJOIN semantics are unknown and intentionally not interpreted.",
    "REINIT marker 255 is treated as the next discard's riichi marker; other marker ordering is unresolved.",
    "Lowercase discard semantics are only partially inferred and marked as estimated.",
)
# LIVE_MAX_ROUND_HISTORY の定義。
LIVE_MAX_ROUND_HISTORY = 4
# LIVE_MAX_EVENT_HISTORY の定義。
LIVE_MAX_EVENT_HISTORY = 4096
# LIVE_MAX_UNKNOWN_TAG_HISTORY の定義。
LIVE_MAX_UNKNOWN_TAG_HISTORY = 256
# LIVE_MAX_DIAGNOSTIC_HISTORY の定義。
LIVE_MAX_DIAGNOSTIC_HISTORY = 256
# LIVE_MAX_CHAT_HISTORY の定義。
LIVE_MAX_CHAT_HISTORY = 128
# Short unresolved lag below this threshold is treated as system-side delay instead of a real skip window.
TENHOU_ROOM_CLASS_RULES: tuple[tuple[int, str, str], ...] = (
    (0x80, "houou", "鳳凰卓"),
    (0x20, "tokujou", "特上卓"),
    (0x08, "joukyuu", "上級卓"),
)
LAG_SYSTEM_DELAY_MAX_MS = 550.0
# Live packet timing emits unresolved lag flags directly:
# 1 = unresolved lag candidate, 2 = actually called, 6 = short delay likely caused by system-side latency.
# XML/manual refinement upgrades only unresolved `1` into:
# 3 = call was possible but did not happen, 4 = reserved/unused, 5 = likely false lag.
LAG_FLAG_UNKNOWN = 0
# LAG_FLAG_UNCONFIRMED の定義。
LAG_FLAG_UNCONFIRMED = 1
# LAG_FLAG_TRUE_CALLED の定義。
LAG_FLAG_TRUE_CALLED = 2
# LAG_FLAG_TRUE_UNCALLED_PROBABLE の定義。
LAG_FLAG_TRUE_UNCALLED_PROBABLE = 3
# LAG_FLAG_FALSE_PROBABLE の定義。欠番で、現行実装では使わない。
LAG_FLAG_FALSE_PROBABLE = 4
# LAG_FLAG_FALSE_CONFIRMED の定義。偽ラグの可能性が高い。
LAG_FLAG_FALSE_CONFIRMED = 5
# LAG_FLAG_SYSTEM_DELAY の定義。
LAG_FLAG_SYSTEM_DELAY = 6

# Tenhou stores meld source seats as relative positions from the acting player.
MELD_FROM_PLAYER_BY_CODE = {
    0: "self",
    1: "shimocha",
    2: "toimen",
    3: "kamicha",
}
# MELD_FROM_PLAYER_TO_CODE の対応表。
MELD_FROM_PLAYER_TO_CODE = {label: code for code, label in MELD_FROM_PLAYER_BY_CODE.items()}

# LEGACY_MELD_TYPE_BY_CANONICAL の対応表。
LEGACY_MELD_TYPE_BY_CANONICAL = {
    "chi": "chi",
    "pon": "pon",
    "daiminkan": "kan_open",
    "ankan": "kan_closed",
    "kakan": "kan_added",
}
# CANONICAL_MELD_TYPE_BY_ALIAS の対応表。
CANONICAL_MELD_TYPE_BY_ALIAS = {
    "chi": "chi",
    "pon": "pon",
    "daiminkan": "daiminkan",
    "kan_open": "daiminkan",
    "ankan": "ankan",
    "kan_closed": "ankan",
    "kakan": "kakan",
    "kan_added": "kakan",
}


def decode_player_name(value: Optional[str]) -> Optional[str]:
    """Decode URL-encoded player names when possible."""

    if value is None:
        return None
    return unquote(value)


def _default_seat_map(factory: Callable[[], Any]) -> dict[int, Any]:
    """Build a 0..3 keyed dictionary using the provided factory."""

    return {seat: factory() for seat in range(SEAT_COUNT)}


def _default_player_map() -> dict[int, "PlayerInfo"]:
    """Build a 0..3 keyed PlayerInfo dictionary."""

    return {seat: PlayerInfo(seat=seat) for seat in range(SEAT_COUNT)}


def default_seat_order() -> list[int]:
    """Return the canonical local-relative seat order: self, shimocha, toimen, kamicha."""

    return list(range(SEAT_COUNT))


def _trim_list_in_place(items: list[Any], limit: int) -> None:
    """Keep only the newest `limit` items of a mutable list."""

    if limit < 0:
        return
    overflow = len(items) - limit
    if overflow > 0:
        del items[:overflow]


def build_round_key(
    game_id: Optional[str],
    kyoku_index: Optional[int],
    honba: Optional[int],
    kyotaku: Optional[int],
    oya: Optional[int],
) -> tuple[str, Optional[int], Optional[int], Optional[int], Optional[int]]:
    """Build the tuple identity used to track the current round."""

    return (game_id or "unknown", kyoku_index, honba, kyotaku, oya)


def build_round_id(
    game_id: Optional[str],
    kyoku_index: Optional[int],
    honba: Optional[int],
    kyotaku: Optional[int],
    oya: Optional[int],
) -> str:
    """Build the string identity used to label a round snapshot."""

    return f"{game_id or 'unknown'}:{kyoku_index}:{honba}:{kyotaku}:{oya}"


def absolute_to_relative_seat(abs_seat: int, self_abs_seat: int) -> int:
    """Convert an absolute XML seat into the project's self-relative seat."""

    return (abs_seat - self_abs_seat) % SEAT_COUNT


def relative_to_absolute_seat(rel_seat: int, self_abs_seat: int) -> int:
    """Convert a self-relative seat into Tenhou's absolute XML seat."""

    return (rel_seat + self_abs_seat) % SEAT_COUNT


# PlayerInfo を表すデータクラス。
@dataclass
class PlayerInfo:
    # seat を保持する。
    seat: int
    # name を保持する。
    name: Optional[str] = None
    # dan を保持する。
    dan: Optional[str] = None
    # rate を保持する。
    rate: Optional[str] = None
    # sx を保持する。
    sx: Optional[str] = None

    @property
    def seat_rel(self) -> int:
        """Return the local-relative seat index used by this project."""

        return self.seat

    @seat_rel.setter
    def seat_rel(self, value: int) -> None:
        self.seat = value

    @property
    def sex(self) -> Optional[str]:
        """Compatibility alias used by the older parser code."""

        return self.sx

    @sex.setter
    def sex(self, value: Optional[str]) -> None:
        self.sx = value


# Event を表すデータクラス。
@dataclass
class Event:
    # timestamp を保持する。
    timestamp: Optional[float]
    # event_type を保持する。
    event_type: str
    # seat を保持する。
    seat: Optional[int] = None
    # raw_tag を保持する。
    raw_tag: str = ""
    # tile_136 を保持する。
    tile_136: Optional[int] = None
    # attrs の対応表。
    attrs: dict[str, Any] = field(default_factory=dict)
    # delta_time を保持する。
    delta_time: Optional[float] = None
    # action_delay_ms を保持する。
    action_delay_ms: Optional[int] = None
    # delay_source を保持する。
    delay_source: Optional[str] = None
    # delay_confidence を保持する。
    delay_confidence: Literal["confirmed", "heuristic", "unknown"] = "unknown"
    # thinking_time_ms を保持する。
    thinking_time_ms: Optional[float] = None
    # thinking_time_source を保持する。
    thinking_time_source: Optional[str] = None
    # thinking_time_before_reach_ms を保持する。
    thinking_time_before_reach_ms: Optional[float] = None
    # thinking_time_before_reach_source を保持する。
    thinking_time_before_reach_source: Optional[str] = None
    # lagged を保持する。
    lagged: int = LAG_FLAG_UNKNOWN
    # lag_delay_ms を保持する。
    lag_delay_ms: Optional[float] = None


# Discard を表すデータクラス。
@dataclass
class Discard:
    # tile_136 を保持する。
    tile_136: int
    # tile_34 を保持する。
    tile_34: Optional[int] = None
    # tile_37 を保持する。
    tile_37: Optional[int] = None
    # round_discard_index を保持する。
    round_discard_index: Optional[int] = None
    # Concealed-hand snapshot immediately before the discard. Closed hands are usually 14 tiles,
    # one open meld leaves 11, two leave 8, and so on. Kakan is the only exception pattern.
    hand_tiles_before_discard_136: list[int] = field(default_factory=list)
    # Self concealed-hand snapshot at the same discard timing. UI lag markers use this seat-0-only
    # snapshot to highlight lag where someone else likely had the actual call window.
    self_hand_tiles_before_discard_136: list[int] = field(default_factory=list)
    # tsumogiri を保持する。
    tsumogiri: bool = False
    # is_tsumogiri_estimated を保持する。
    is_tsumogiri_estimated: bool = False
    # riichi_marker_before を保持する。
    riichi_marker_before: bool = False
    # raw_tag を保持する。
    raw_tag: str = ""
    # called を保持する。これは「後で鳴かれたか」の結果フラグであり、
    # tsumogiri / tedashi の打牌種別とは独立に扱う。
    called: bool = False
    # thinking_time_ms を保持する。
    thinking_time_ms: Optional[float] = None
    # thinking_time_source を保持する。
    thinking_time_source: Optional[str] = None
    # thinking_time_before_reach_ms を保持する。
    thinking_time_before_reach_ms: Optional[float] = None
    # thinking_time_before_reach_source を保持する。
    thinking_time_before_reach_source: Optional[str] = None
    # lagged を保持する。
    lagged: int = LAG_FLAG_UNKNOWN
    # lag_delay_ms を保持する。
    lag_delay_ms: Optional[float] = None
    # event_index を保持する。
    event_index: int = -1

    def __post_init__(self) -> None:
        if self.tile_34 is None:
            self.tile_34 = tile136_to_tile34_index(self.tile_136)
        if self.tile_37 is None:
            self.tile_37 = tile136_to_tile37_index(self.tile_136)

    @property
    def ui_tile_37(self) -> Optional[int]:
        """Return the legacy 1..37 tile id used by the existing UI."""

        return tile136_to_tile37(self.tile_136)

    @property
    def tsumogiri_flag(self) -> str:
        """Return the DB / CSV discard-style label without any `confirmed_*` prefix."""

        if self.tsumogiri and self.is_tsumogiri_estimated:
            return "risekichu_hokan_tsumogiri"
        if self.tsumogiri:
            return "tsumogiri"
        return "tedashi"


# Meld を表すデータクラス。
@dataclass
class Meld:
    # who を保持する。
    who: int
    # raw_m を保持する。
    raw_m: int
    # meld_type を保持する。
    meld_type: str
    # tile_34 を保持する。
    tile_34: Optional[int] = None
    # tile_37 を保持する。
    tile_37: Optional[int] = None
    # from_who を保持する。
    from_who: int = 0
    # consumed_tile_ids の一覧。
    consumed_tile_ids: list[int] = field(default_factory=list)
    # called_tile_id を保持する。
    called_tile_id: Optional[int] = None
    # called_tile_136 を保持する。
    called_tile_136: Optional[int] = None
    # from_seat を保持する。
    from_seat: Optional[int] = None
    # is_open を保持する。
    is_open: bool = False
    # upgraded_from を保持する。
    upgraded_from: Optional[str] = None
    # tiles_136 の一覧。
    tiles_136: list[int] = field(default_factory=list)
    # tiles_34 の一覧。
    tiles_34: list[int] = field(default_factory=list)
    # tiles_37 の一覧。
    tiles_37: list[int] = field(default_factory=list)
    # from_player を保持する。
    from_player: str = "self"
    # called_index を保持する。
    called_index: Optional[int] = None
    # rotate_index を保持する。
    rotate_index: Optional[int] = None
    # meld_id を保持する。
    meld_id: str = ""
    # event_index を保持する。
    event_index: int = -1

    def __post_init__(self) -> None:
        canonical = CANONICAL_MELD_TYPE_BY_ALIAS.get(self.meld_type, self.meld_type)
        self.meld_type = canonical
        if self.from_player not in MELD_FROM_PLAYER_TO_CODE:
            self.from_player = MELD_FROM_PLAYER_BY_CODE.get(self.from_who, "self")
        if not 0 <= self.from_who <= 3:
            self.from_who = MELD_FROM_PLAYER_TO_CODE.get(self.from_player, 0)
        if self.called_tile_id is None and self.called_index is not None:
            if 0 <= self.called_index < len(self.tiles_136):
                self.called_tile_id = self.tiles_136[self.called_index]
        if self.called_tile_136 is None:
            self.called_tile_136 = self.called_tile_id
        elif self.called_tile_id is None:
            self.called_tile_id = self.called_tile_136
        if self.from_seat is None:
            self.from_seat = meld_from_who_to_seat(self.who, self.from_who)
        if not self.tiles_34:
            self.tiles_34 = [
                tile_34
                for tile_34 in (tile136_to_tile34_index(tile_136) for tile_136 in self.tiles_136)
                if tile_34 is not None
            ]
        if not self.tiles_37:
            self.tiles_37 = [
                tile_id
                for tile_id in (tile136_to_tile37(tile_136) for tile_136 in self.tiles_136)
                if tile_id is not None
            ]
        representative_tile = self.called_tile_id
        if representative_tile is None and self.tiles_136:
            representative_tile = self.tiles_136[0]
        if self.tile_34 is None:
            self.tile_34 = tile136_to_tile34_index(representative_tile)
        if self.tile_37 is None:
            self.tile_37 = tile136_to_tile37_index(representative_tile)

    @property
    def actor(self) -> int:
        """Compatibility alias used by the old parser/UI code."""

        return self.who

    @property
    def type(self) -> str:
        """Compatibility alias returning the legacy meld type labels."""

        return LEGACY_MELD_TYPE_BY_CANONICAL.get(self.meld_type, self.meld_type)

    @property
    def target_tile_136(self) -> Optional[int]:
        return self.called_tile_136

    @property
    def target_tile_37(self) -> Optional[int]:
        return tile136_to_tile37(self.called_tile_id)

    @property
    def consumed_from_hand_136(self) -> list[int]:
        return self.consumed_tile_ids

    @property
    def opened(self) -> bool:
        return self.is_open

    @property
    def source_meld_id(self) -> Optional[str]:
        return self.upgraded_from

    @property
    def hand_tiles_136(self) -> list[int]:
        return self.consumed_tile_ids

    @property
    def called_tile_index(self) -> Optional[int]:
        return self.called_index

    @property
    def kind(self) -> str:
        return self.type

    @property
    def raw_code(self) -> int:
        return self.raw_m


# RoundState を表すデータクラス。
@dataclass
class RoundState:
    # kyoku_index を保持する。
    kyoku_index: Optional[int] = None
    # honba を保持する。
    honba: Optional[int] = None
    # kyotaku を保持する。
    kyotaku: Optional[int] = None
    # dice_1_minus_1 を保持する。
    dice_1_minus_1: Optional[int] = None
    # dice_2_minus_1 を保持する。
    dice_2_minus_1: Optional[int] = None
    # oya を保持する。
    oya: Optional[int] = None
    # oya_abs を保持する。
    oya_abs: Optional[int] = None
    # oya_rel を保持する。
    oya_rel: Optional[int] = None
    # seat_order の一覧。
    seat_order: list[int] = field(default_factory=default_seat_order)
    # round_key を保持する。
    round_key: tuple[str, Optional[int], Optional[int], Optional[int], Optional[int]] | None = None
    # round_id を保持する。
    round_id: Optional[str] = None
    # scores の一覧。
    scores: list[int] = field(default_factory=lambda: [25000, 25000, 25000, 25000])
    # dora_indicators_136 の一覧。
    dora_indicators_136: list[int] = field(default_factory=list)
    # initial_self_hand_136 の一覧。
    initial_self_hand_136: list[int] = field(default_factory=list)
    # initial_hands_136 の対応表。
    initial_hands_136: dict[int, list[int]] = field(default_factory=lambda: _default_seat_map(list))
    # initial_hands_abs_136 の対応表。
    initial_hands_abs_136: dict[int, list[int]] = field(default_factory=lambda: _default_seat_map(list))
    # initial_hands_rel_136 の対応表。
    initial_hands_rel_136: dict[int, list[int]] = field(default_factory=lambda: _default_seat_map(list))
    # current_hands_136 の対応表。
    current_hands_136: dict[int, list[int]] = field(default_factory=lambda: _default_seat_map(list))
    # snapshot_is_partial を保持する。
    snapshot_is_partial: bool = True
    # started_from_init_like を保持する。
    started_from_init_like: bool = False
    # snapshot_bootstrap_sequence increments on INIT/REINIT-style snapshot rebuilds.
    snapshot_bootstrap_sequence: int = 0
    # discards の対応表。
    discards: dict[int, list[Discard]] = field(default_factory=lambda: _default_seat_map(list))
    # melds の対応表。
    melds: dict[int, list[Meld]] = field(default_factory=lambda: _default_seat_map(list))
    # reach_state の対応表。
    reach_state: dict[int, str] = field(
        default_factory=lambda: {seat: "none" for seat in range(SEAT_COUNT)}
    )
    # events の一覧。
    events: list[Event] = field(default_factory=list)
    # draws の対応表。
    draws: dict[int, list[int]] = field(default_factory=lambda: _default_seat_map(list))
    # last_draw_tiles_136 の対応表。
    last_draw_tiles_136: dict[int, int | None] = field(
        default_factory=lambda: {seat: None for seat in range(SEAT_COUNT)}
    )
    # pending_riichi_markers の対応表。
    pending_riichi_markers: dict[int, bool] = field(
        default_factory=lambda: {seat: False for seat in range(SEAT_COUNT)}
    )
    # discard_thinking_starts の対応表。
    discard_thinking_starts: dict[int, tuple[Optional[float], str] | None] = field(
        default_factory=lambda: {seat: None for seat in range(SEAT_COUNT)}
    )
    # discard_thinking_before_reach の対応表。
    discard_thinking_before_reach: dict[int, tuple[Optional[float], Optional[str]] | None] = field(
        default_factory=lambda: {seat: None for seat in range(SEAT_COUNT)}
    )
    # pending_response_discard を保持する。
    pending_response_discard: tuple[int, int, Optional[float]] | None = None
    # raw_attrs の対応表。
    raw_attrs: dict[str, Any] = field(default_factory=dict)
    # raw_init_attrs の対応表。
    raw_init_attrs: dict[str, Any] = field(default_factory=dict)
    # raw_reinit_attrs の対応表。
    raw_reinit_attrs: dict[str, Any] = field(default_factory=dict)
    # result を保持する。
    result: Optional[dict[str, Any]] = None
    # reinit_kawa_raw の対応表。
    reinit_kawa_raw: dict[int, list[int]] = field(default_factory=lambda: _default_seat_map(list))
    # validation_issues の一覧。
    validation_issues: list[str] = field(default_factory=list)

    @property
    def hands_136(self) -> dict[int, list[int]]:
        """Return current hands keyed by the active seat view."""

        return self.current_hands_136

    @hands_136.setter
    def hands_136(self, value: dict[int, list[int]]) -> None:
        self.current_hands_136 = value

    @property
    def kawa_raw(self) -> dict[int, list[int]]:
        """Return REINIT raw rivers keyed by the active seat view."""

        return self.reinit_kawa_raw

    @kawa_raw.setter
    def kawa_raw(self, value: dict[int, list[int]]) -> None:
        self.reinit_kawa_raw = value

    @property
    def riichi_sticks(self) -> Optional[int]:
        return self.kyotaku

    @riichi_sticks.setter
    def riichi_sticks(self, value: Optional[int]) -> None:
        self.kyotaku = value

    @property
    def reach_declared(self) -> set[int]:
        return {
            seat
            for seat, state in self.reach_state.items()
            if state in {"declared", "accepted"}
        }

    @property
    def reach_accepted(self) -> set[int]:
        return {seat for seat, state in self.reach_state.items() if state == "accepted"}


# GameState を表すデータクラス。
@dataclass
class GameState:
    # players の対応表。
    players: dict[int, PlayerInfo] = field(default_factory=_default_player_map)
    # players_abs の対応表。
    players_abs: dict[int, PlayerInfo] = field(default_factory=_default_player_map)
    # players_rel の対応表。
    players_rel: dict[int, PlayerInfo] = field(default_factory=_default_player_map)
    # seat_order の一覧。
    seat_order: list[int] = field(default_factory=default_seat_order)
    # game_id を保持する。
    game_id: Optional[str] = None
    # go_type を保持する。
    go_type: Optional[int] = None
    # room_class_code を保持する。
    room_class_code: Optional[str] = None
    # room_class_label を保持する。
    room_class_label: Optional[str] = None
    # rounds の一覧。
    rounds: list[RoundState] = field(default_factory=list)
    # current_round を保持する。
    current_round: Optional[RoundState] = None
    # current_dealer_seat を保持する。
    current_dealer_seat: Optional[int] = None
    # round_key を保持する。
    round_key: tuple[str, Optional[int], Optional[int], Optional[int], Optional[int]] | None = None
    # round_id を保持する。
    round_id: Optional[str] = None
    # raw_events の一覧。
    raw_events: list[Event] = field(default_factory=list)
    # unknown_tags の一覧。
    unknown_tags: list[dict[str, Any]] = field(default_factory=list)
    # tracker を保持する。
    tracker: SutehaiTracker = field(default_factory=SutehaiTracker)
    # live_hand_tiles_136 の一覧。
    live_hand_tiles_136: list[int] = field(default_factory=list)
    # live_last_draw_tile_136 を保持する。
    live_last_draw_tile_136: Optional[int] = None
    # live_meld_tiles_136 の一覧。
    live_meld_tiles_136: list[int] = field(default_factory=list)
    # live_dora_indicator_tiles_136 の一覧。
    live_dora_indicator_tiles_136: list[int] = field(default_factory=list)
    # chats の一覧。
    chats: list[dict[str, Any]] = field(default_factory=list)
    # diagnostics の一覧。
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    # unresolved_spec_todos の並びを保持する。
    unresolved_spec_todos: tuple[str, ...] = UNRESOLVED_SPEC_TODOS
    # last_timestamp を保持する。
    last_timestamp: Optional[float] = None
    # Internal seat indices are local-relative. The live player is always seat 0.
    self_seat: int = 0
    # parser_mode を保持する。
    parser_mode: Literal["player_live", "spectator_live", "xml_log"] = "player_live"
    # self_abs_seat を保持する。
    self_abs_seat: Optional[int] = None
    # self_player_name を保持する。
    self_player_name: Optional[str] = None
    # seat_mapping_resolved を保持する。
    seat_mapping_resolved: bool = True
    # source_fragments の一覧。
    source_fragments: list[tuple[Optional[float], str]] = field(default_factory=list)
    # AI TOP3 を表示した自家手牌ごとの top3 履歴。key は `(round_id, next_discard_index, hand_key)`。
    pystyle_self_history_by_round_hand: dict[tuple[str, int, tuple[int, ...]], dict[str, str]] = field(
        default_factory=dict
    )
    # Live capture thread と UI redraw thread の共有 state を同期する。
    state_lock: Any = field(default_factory=threading.RLock, repr=False)
    # live_update_sequence を保持する。
    live_update_sequence: int = 0
    # live_snapshot_bootstrap_sequence increments when INIT/REINIT-style snapshots rebuild the table.
    live_snapshot_bootstrap_sequence: int = 0

    def __post_init__(self) -> None:
        self.refresh_player_views()

    def mark_live_update(self) -> None:
        """Advance the live-update token so the UI can redraw on capture events."""

        self.live_update_sequence += 1

    @property
    def source_kind(self) -> str:
        """Compatibility alias kept for older callers and exports."""

        return self.parser_mode

    @source_kind.setter
    def source_kind(self, value: str) -> None:
        self.parser_mode = value  # type: ignore[assignment]

    @property
    def events(self) -> list[Event]:
        """Compatibility alias for the older capture state."""

        return self.raw_events

    def refresh_player_views(self) -> None:
        """Point the legacy `players` view at the active seat interpretation."""

        if self.parser_mode == "xml_log" and not self.seat_mapping_resolved:
            self.players = self.players_abs
            return
        self.players = self.players_rel

    def sync_current_round_context(self) -> None:
        """Mirror the current round identifiers onto the game-level view."""

        if self.current_round is None:
            self.current_dealer_seat = None
            self.round_key = None
            self.round_id = None
            return

        self.current_round.seat_order = list(self.seat_order)
        self.current_dealer_seat = self.current_round.oya
        self.round_key = self.current_round.round_key
        self.round_id = self.current_round.round_id

    @property
    def current_dealer_seat_rel(self) -> Optional[int]:
        """Return dealer seat in the currently active seat view."""

        return self.current_dealer_seat

    def begin_round(self, *, started_from_init_like: bool = False) -> RoundState:
        """Create and register a fresh current round."""

        self.current_round = RoundState(
            seat_order=list(self.seat_order),
            started_from_init_like=started_from_init_like,
        )
        self.rounds.append(self.current_round)
        self.sync_current_round_context()
        self.prune_live_history()
        return self.current_round

    def ensure_round(self) -> RoundState:
        """Return the current round, creating one only when necessary."""

        if self.current_round is None:
            return self.begin_round()
        self.sync_current_round_context()
        return self.current_round

    def reset_live_session(self, *, preserve_player_metadata: bool = True) -> None:
        """Clear in-memory live capture state in place without replacing the tracker object."""

        self.game_id = None
        self.go_type = None
        self.room_class_code = None
        self.room_class_label = None
        self.rounds.clear()
        self.current_round = None
        self.current_dealer_seat = None
        self.round_key = None
        self.round_id = None
        self.raw_events.clear()
        self.unknown_tags.clear()
        self.chats.clear()
        self.last_timestamp = None
        self.seat_order = default_seat_order()

        for discards in self.tracker.discards.values():
            discards.clear()

        self.live_hand_tiles_136.clear()
        self.live_last_draw_tile_136 = None
        self.live_meld_tiles_136.clear()
        self.live_dora_indicator_tiles_136.clear()
        self.pystyle_self_history_by_round_hand.clear()

        if not preserve_player_metadata:
            self.players_abs = _default_player_map()
            self.players_rel = _default_player_map()
            if self.parser_mode != "xml_log":
                self.seat_mapping_resolved = True

        self.refresh_player_views()
        self.sync_current_round_context()
        self.mark_live_update()

    def add_event(
        self,
        timestamp: Optional[float],
        event_type: str,
        seat: Optional[int] = None,
        tile_136: Optional[int] = None,
        raw_tag: str = "",
        attrs: Optional[dict[str, Any]] = None,
        action_delay_ms: Optional[int] = None,
        delay_source: Optional[str] = None,
        delay_confidence: Literal["confirmed", "heuristic", "unknown"] = "unknown",
        thinking_time_ms: Optional[float] = None,
        thinking_time_source: Optional[str] = None,
        thinking_time_before_reach_ms: Optional[float] = None,
        thinking_time_before_reach_source: Optional[str] = None,
    ) -> Event:
        """Append a normalised event to the global and round-local histories."""

        delta_time = None
        if timestamp is not None and self.last_timestamp is not None:
            delta_time = timestamp - self.last_timestamp
        if timestamp is not None:
            self.last_timestamp = timestamp

        event = Event(
            timestamp=timestamp,
            event_type=event_type,
            seat=seat,
            raw_tag=raw_tag,
            tile_136=tile_136,
            attrs=attrs or {},
            delta_time=delta_time,
            action_delay_ms=action_delay_ms,
            delay_source=delay_source,
            delay_confidence=delay_confidence,
            thinking_time_ms=thinking_time_ms,
            thinking_time_source=thinking_time_source,
            thinking_time_before_reach_ms=thinking_time_before_reach_ms,
            thinking_time_before_reach_source=thinking_time_before_reach_source,
        )
        self.raw_events.append(event)
        if self.current_round is not None:
            self.current_round.events.append(event)
        self.mark_live_update()
        self.prune_live_history()
        return event

    def prune_live_history(self) -> None:
        """Bound in-memory history for long-running live capture sessions."""

        if self.parser_mode not in {"player_live", "spectator_live"}:
            return

        _trim_list_in_place(self.raw_events, LIVE_MAX_EVENT_HISTORY)
        _trim_list_in_place(self.unknown_tags, LIVE_MAX_UNKNOWN_TAG_HISTORY)
        _trim_list_in_place(self.diagnostics, LIVE_MAX_DIAGNOSTIC_HISTORY)
        _trim_list_in_place(self.chats, LIVE_MAX_CHAT_HISTORY)

        overflow_rounds = len(self.rounds) - LIVE_MAX_ROUND_HISTORY
        if overflow_rounds > 0:
            del self.rounds[:overflow_rounds]


# Backward-compatible aliases used by the rest of the application.
CaptureState = GameState
# CaptureDiscard の型定義。
CaptureDiscard = Discard


def _ensure_runtime_progress_state(state: CaptureState) -> tuple[Any, dict[str, dict[str, Any]]]:
    """Return the watchdog lock/map stored on one live state, creating them lazily."""

    progress_lock = getattr(state, "_runtime_progress_lock", None)
    if progress_lock is None:
        progress_lock = threading.Lock()
        setattr(state, "_runtime_progress_lock", progress_lock)
    progress_by_thread = getattr(state, "_runtime_progress_by_thread", None)
    if progress_by_thread is None:
        progress_by_thread = {}
        setattr(state, "_runtime_progress_by_thread", progress_by_thread)
    return progress_lock, progress_by_thread


def mark_runtime_thread_progress(
    state: CaptureState,
    thread_name: str,
    stage: str,
    *,
    detail: str = "",
    blocked_hint: str = "",
    stale_after_s: float = 10.0,
    repeat_after_s: float = 15.0,
) -> None:
    """Record one thread's latest progress marker for watchdog reporting."""

    progress_lock, progress_by_thread = _ensure_runtime_progress_state(state)
    now_monotonic = time.monotonic()
    with progress_lock:
        previous = dict(progress_by_thread.get(thread_name, {}))
        progress_by_thread[thread_name] = {
            "thread_name": thread_name,
            "stage": str(stage or "").strip() or "unknown",
            "detail": str(detail or "").strip(),
            "blocked_hint": str(blocked_hint or "").strip(),
            "updated_monotonic": now_monotonic,
            "stale_after_s": max(0.5, float(stale_after_s)),
            "repeat_after_s": max(1.0, float(repeat_after_s)),
            "sequence": int(previous.get("sequence", 0) or 0) + 1,
        }


def snapshot_runtime_thread_progress(
    state: CaptureState,
) -> dict[str, dict[str, Any]]:
    """Return an immutable snapshot of the watchdog progress markers."""

    progress_lock, progress_by_thread = _ensure_runtime_progress_state(state)
    with progress_lock:
        return {
            str(thread_name): dict(progress)
            for thread_name, progress in progress_by_thread.items()
        }


def tile136_to_tile34_index(tile_136: Optional[int]) -> Optional[int]:
    """Convert a raw 136-tile id into the spec-oriented 0..33 tile index."""

    if tile_136 is None or not 0 <= tile_136 <= 135:
        return None
    return tile_136 // 4


def tile136_to_tile37_index(tile_136: Optional[int]) -> Optional[int]:
    """Convert a raw 136-tile id into the spec-oriented 0..36 tile index."""

    tile_34 = tile136_to_tile34_index(tile_136)
    if tile_34 is None:
        return None
    if tile_136 in RED_TILE_INDEX_BY_136:
        return RED_TILE_INDEX_BY_136[tile_136]
    return tile_34


def tile136_to_tile37(tile_136: Optional[int]) -> Optional[int]:
    """Convert a raw 136-tile id into the legacy 1..37 UI tile id."""

    if tile_136 is None or not 0 <= tile_136 <= 135:
        return None
    if tile_136 in RED_TILE_MAP_136_TO_37:
        return RED_TILE_MAP_136_TO_37[tile_136]

    tile34 = tile_136 // 4
    if 0 <= tile34 <= 8:
        return tile34 + 1
    if 9 <= tile34 <= 17:
        return tile34 + 2
    if 18 <= tile34 <= 26:
        return tile34 + 3
    if 27 <= tile34 <= 33:
        return tile34 + 4
    return None


def tile136_to_tile34(tile_136: Optional[int]) -> Optional[int]:
    """Convert a raw 136-tile id into the legacy 34-kind display id."""

    tile_37 = tile136_to_tile37(tile_136)
    if tile_37 is None:
        return None
    if tile_37 == 10:
        return 5
    if tile_37 == 20:
        return 15
    if tile_37 == 30:
        return 25
    return tile_37


def normalize_tile136_id(tile_136: Optional[int], *, one_based: bool = False) -> Optional[int]:
    """Normalize raw tile ids into the canonical internal 0..135 space.

    Automatic 0/1-based detection is intentionally not implemented because it would
    silently guess on ambiguous values such as 1..135.
    """

    if tile_136 is None:
        return None
    try:
        tile_value = int(tile_136)
    except (TypeError, ValueError):
        return None
    normalized = tile_value - 1 if one_based else tile_value
    if not 0 <= normalized <= 135:
        return None
    return normalized


def tile136_to_tile37_spec(tile_136: Optional[int]) -> Optional[int]:
    """Public spec-oriented 0..36 conversion helper."""

    return tile136_to_tile37_index(tile_136)


def tile136_to_tile37_ui(tile_136: Optional[int]) -> Optional[int]:
    """Public UI-oriented 1..37 conversion helper."""

    return tile136_to_tile37(tile_136)


def tile136_to_tile37_text(tile_136: Optional[int]) -> Optional[str]:
    """Convert a raw 136-tile id into compact text such as `3p` or `r5p`."""

    tile_34 = tile136_to_tile34_index(tile_136)
    if tile_34 is None:
        return None
    if tile_34 < 27:
        suit = "mps"[tile_34 // 9]
        rank = (tile_34 % 9) + 1
        prefix = "r" if tile_136 in RED_TILE_IDS_136 else ""
        return f"{prefix}{rank}{suit}"
    return f"{tile_34 - 26}z"


def parse_csv_int_list(value: Optional[Any]) -> list[int]:
    """Parse CSV-like integer fields from XML/JSON payloads."""

    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [int(item) for item in stripped.split(",") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return [int(item) for item in value]
    return [int(value)]


def parse_tenhou_game_type(value: Any) -> int | None:
    """Parse Tenhou `GO.type` values into one canonical integer bitmask."""

    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.lower().startswith("0x"):
            return int(text, 16)
        return int(text, 10)
    except ValueError:
        return None


def parse_tenhou_game_type_hex(value: Any) -> int | None:
    """Parse the `gm-XXXX` URL fragment into the same integer game-type bitmask."""

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


def tenhou_game_type_hex(game_type: int | None) -> str | None:
    """Return the zero-padded 4-hex-digit form used in Tenhou log URLs."""

    if game_type is None:
        return None
    return f"{int(game_type) & 0xFFFF:04x}"


def tenhou_room_class_code(game_type: int | None) -> str | None:
    """Return `ippan` / `joukyuu` / `tokujou` / `houou` from one game-type bitmask."""

    if game_type is None:
        return None
    for bitmask, code, _label in TENHOU_ROOM_CLASS_RULES:
        if int(game_type) & bitmask:
            return code
    return "ippan"


def tenhou_room_class_label(game_type: int | None) -> str | None:
    """Return the Japanese room label for one Tenhou game-type bitmask."""

    room_code = tenhou_room_class_code(game_type)
    if room_code is None:
        return None
    if room_code == "ippan":
        return "一般卓"
    for _bitmask, code, label in TENHOU_ROOM_CLASS_RULES:
        if code == room_code:
            return label
    return None


def meld_from_player_to_seat(actor: int, from_player: str) -> int | None:
    """Convert actor-relative meld source labels into local-relative seat indices."""

    from_code = MELD_FROM_PLAYER_TO_CODE.get(from_player)
    if from_code is None:
        return None
    return (actor + from_code) % SEAT_COUNT


def meld_from_who_to_seat(actor: int, from_who: int | None) -> int | None:
    """Convert actor-relative meld source codes into local-relative seat indices."""

    if from_who is None or not 0 <= from_who < SEAT_COUNT:
        return None
    return (actor + from_who) % SEAT_COUNT
