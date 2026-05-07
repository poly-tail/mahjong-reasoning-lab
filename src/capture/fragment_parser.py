from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
from io import StringIO
import json
import logging
import re
import xml.etree.ElementTree as et
from typing import Any, Iterable, Literal, Optional

from capture.meld_decoder import decode_meld
from capture.state import (
    CaptureState,
    Discard,
    Event,
    GameState,
    LAG_FLAG_SYSTEM_DELAY,
    LAG_SYSTEM_DELAY_MAX_MS,
    LAG_FLAG_UNKNOWN,
    LAG_FLAG_TRUE_CALLED,
    LAG_FLAG_UNCONFIRMED,
    LOCAL_RELATIVE_SEAT,
    Meld,
    PlayerInfo,
    RoundState,
    SEAT_COUNT,
    absolute_to_relative_seat,
    build_round_id,
    build_round_key,
    decode_player_name,
    meld_from_who_to_seat,
    parse_csv_int_list,
    parse_tenhou_game_type,
    tenhou_room_class_code,
    tenhou_room_class_label,
    tile136_to_tile37,
)
from sutehai import Player

# logger の定義。
logger = logging.getLogger(__name__)

# XML-style mjlog fragments can appear concatenated in a single websocket payload.
MARKUP_TAG_PATTERN = re.compile(r"(<[^<>]+?>)")
# XMLISH_START_TAG_PATTERN の定義。
XMLISH_START_TAG_PATTERN = re.compile(r"<\s*([A-Za-z][A-Za-z0-9]*)\b([^<>]*)")
# XMLISH_ATTR_PATTERN の定義。
XMLISH_ATTR_PATTERN = re.compile(r'([A-Za-z_:][A-Za-z0-9_:\-]*)="([^"]*)"')
# EMBEDDED_BARE_TAG_PATTERN の定義。
EMBEDDED_BARE_TAG_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])("
    r"(?:\d+)?[DEFG]\d+|[TUVW]\d+|INITBYLOG|RYUUKYOKU|TAIKYOKU|REACH|REINIT|AGARI|DORA|"
    r"SAIKAI|REJOIN|HELO|BYE|GOK|GO|UN|INIT|WGC|LN"
    r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)
# Server-facing draw/discard tags are either bare mjlog-style names or wrapped in JSON/XML.
DRAW_TAG_NAME_PATTERN = re.compile(r"^([TUVW])(\d+)?$", re.IGNORECASE)
# DISCARD_TAG_NAME_PATTERN の定義。
DISCARD_TAG_NAME_PATTERN = re.compile(r"^(?:(\d+))?([DEFG])(\d+)$", re.IGNORECASE)

# Live websocket packets use the project's local-relative seat indexing:
# 0=self, 1=shimocha, 2=toimen, 3=kamicha.
# Offline XML mjlog packets use Tenhou absolute seat indexing.
DRAW_SEAT_MAP = {
    "T": 0,
    "U": 1,
    "V": 2,
    "W": 3,
}
# DISCARD_SEAT_MAP の対応表。
DISCARD_SEAT_MAP = {
    "D": 0,
    "E": 1,
    "F": 2,
    "G": 3,
}
# SIMPLE_EVENT_TAGS の集合。
SIMPLE_EVENT_TAGS = {
    "BYE",
    "GOK",
    "GO",
    "HELO",
    "SAIKAI",
    "TAIKYOKU",
    "Z",
}
# PARSER_MODE_PLAYER_LIVE の定義。
PARSER_MODE_PLAYER_LIVE = "player_live"
# PARSER_MODE_SPECTATOR_LIVE の定義。
PARSER_MODE_SPECTATOR_LIVE = "spectator_live"
# PARSER_MODE_XML の定義。
PARSER_MODE_XML = "xml_log"
# SPECTATOR_INIT_TAGS の集合。
SPECTATOR_INIT_TAGS = {"INITBYLOG", "WGC"}
# SNAPSHOT_ROUND_REUSE_MIN_DISCARD_MATCH_RATIO の定義。
SNAPSHOT_ROUND_REUSE_MIN_DISCARD_MATCH_RATIO = 0.8
# LAG_THRESHOLD_SECONDS の定義。
LAG_THRESHOLD_SECONDS = 0.005
CLIENT_DISCARD_REQUEST_RAW_TAG_PREFIX = "CLIENT_DISCARD_REQUEST:"


@dataclass(frozen=True)
class ParsedTag:
    """Normalised representation of a single extracted tag fragment."""

    # tag_name を保持する。
    tag_name: str
    # raw_tag を保持する。
    raw_tag: str
    # attrs の対応表。
    attrs: dict[str, Any]
    # source_format を保持する。
    source_format: str

    @property
    def normalized_tag(self) -> str:
        return self.tag_name.upper()


@dataclass(frozen=True)
class HandSnapshot:
    """Structured hand extraction that keeps `hai` separate from `hai0..hai3`."""

    # seat_hands の対応表。
    seat_hands: dict[int, list[int]]
    # self_hand_136 の一覧。
    self_hand_136: list[int]
    # explicit_seat_count を保持する。
    explicit_seat_count: int = 0

    @property
    def has_any_seat_hands(self) -> bool:
        return self.explicit_seat_count > 0

    @property
    def has_full_seat_hands(self) -> bool:
        return self.explicit_seat_count == SEAT_COUNT

    @property
    def has_self_hand(self) -> bool:
        return bool(self.self_hand_136)

    @property
    def is_partial(self) -> bool:
        return not self.has_full_seat_hands


@dataclass(frozen=True)
class XmlDiscardSnapshot:
    """Discard-time concealed-hand snapshot extracted from an offline XML replay."""

    # kyoku_index を保持する。
    kyoku_index: Optional[int]
    # honba を保持する。
    honba: Optional[int]
    # discard_index を保持する。
    discard_index: int
    # player_rel_seat を保持する。
    player_rel_seat: int
    # discard_tile_136 を保持する。
    discard_tile_136: int
    # hand_tiles_by_seat_136 の対応表。
    hand_tiles_by_seat_136: dict[int, tuple[int, ...]]


@dataclass(frozen=True)
class SnapshotDiscardComparison:
    """Compare current visible rivers against one INIT/REINIT snapshot."""

    # matched_prefix_discards を保持する。
    matched_prefix_discards: int
    # current_total_visible_discards を保持する。
    current_total_visible_discards: int
    # snapshot_total_visible_discards を保持する。
    snapshot_total_visible_discards: int
    # is_append_only_extension を保持する。
    is_append_only_extension: bool

    @property
    def match_ratio(self) -> float:
        comparison_total = max(
            self.current_total_visible_discards,
            self.snapshot_total_visible_discards,
        )
        if comparison_total <= 0:
            return 1.0
        return self.matched_prefix_discards / comparison_total


def split_tshark_line(line: str) -> tuple[Optional[float], str]:
    """Split a raw tshark `-T fields` line into timestamp and payload text."""

    parts = line.rstrip("\n").split("\t")
    if not parts:
        return None, ""

    try:
        timestamp = float(parts[0])
    except ValueError:
        return None, ""

    payload_candidates = [_normalize_tshark_payload_field(part) for part in parts[1:] if part]
    preferred_payload = _select_preferred_tshark_payload(payload_candidates)
    return timestamp, preferred_payload


def _normalize_tshark_payload_field(field_text: str) -> str:
    """Strip tshark display prefixes that are not part of the websocket payload."""

    normalized = field_text.strip()
    if normalized == "Timestamps":
        return ""
    if normalized.startswith("Timestamps,"):
        normalized = normalized[len("Timestamps,") :].lstrip()
    return normalized


def _select_preferred_tshark_payload(payload_candidates: list[str]) -> str:
    """Choose the best payload field emitted by tshark for packet parsing."""

    if not payload_candidates:
        return ""

    for candidate in payload_candidates:
        stripped = candidate.strip()
        if not stripped:
            continue
        if stripped[0] in {"{", "<"} or "<" in stripped or "{" in stripped:
            return stripped
        if EMBEDDED_BARE_TAG_PATTERN.search(stripped):
            return stripped

    for candidate in payload_candidates:
        stripped = candidate.strip()
        if stripped:
            return stripped
    return ""


def _extract_json_objects(text: str) -> list[str]:
    """Extract JSON object fragments from a websocket payload."""

    decoder = json.JSONDecoder()
    fragments: list[str] = []
    index = 0
    while index < len(text):
        brace_index = text.find("{", index)
        if brace_index < 0:
            break
        candidate = text[brace_index:]
        try:
            _payload, consumed = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            index = brace_index + 1
            continue
        fragments.append(candidate[:consumed])
        index = brace_index + consumed
    return fragments


def extract_tag_fragments(text: str) -> list[str]:
    """Extract XML or JSON tag payloads from a decrypted websocket text blob."""

    stripped = text.strip()
    if not stripped:
        return []

    xml_fragments = MARKUP_TAG_PATTERN.findall(stripped)
    if xml_fragments:
        return xml_fragments

    json_fragments = _extract_json_objects(stripped)
    if json_fragments:
        return json_fragments

    xmlish_start = stripped.find("<")
    if xmlish_start >= 0:
        xmlish_fragment = stripped[xmlish_start:].strip()
        if xmlish_fragment:
            return [xmlish_fragment]

    bare_tag_fragments = [match.group(1) for match in EMBEDDED_BARE_TAG_PATTERN.finditer(stripped)]
    if bare_tag_fragments:
        return bare_tag_fragments

    # Some offline inputs already provide a single bare tag such as `D60`.
    return [stripped]


def extract_html_xml_fragments(text: str) -> list[str]:
    """Backward-compatible wrapper used by the capture modules."""

    return extract_tag_fragments(text)


def try_parse_xml(fragment: str) -> Optional[et.Element]:
    """Parse a single XML fragment when it is valid XML."""

    try:
        return et.fromstring(fragment)
    except et.ParseError:
        return None


def parse_tag_fragment(fragment: str) -> ParsedTag:
    """Parse a single raw tag fragment into a normalized ParsedTag."""

    raw_tag = fragment.strip()
    if not raw_tag:
        return ParsedTag(tag_name="", raw_tag="", attrs={}, source_format="empty")

    xmlish_fragment = raw_tag[raw_tag.find("<") :].strip() if "<" in raw_tag else ""
    if xmlish_fragment.startswith("<"):
        elem = try_parse_xml(xmlish_fragment)
        if elem is not None:
            return ParsedTag(
                tag_name=str(elem.tag),
                raw_tag=xmlish_fragment,
                attrs=dict(elem.attrib),
                source_format="xml",
            )
        xmlish_match = XMLISH_START_TAG_PATTERN.search(xmlish_fragment)
        if xmlish_match is not None:
            attrs = {
                key: value
                for key, value in XMLISH_ATTR_PATTERN.findall(xmlish_match.group(2))
            }
            return ParsedTag(
                tag_name=xmlish_match.group(1),
                raw_tag=xmlish_fragment,
                attrs=attrs,
                source_format="xmlish",
            )

    if raw_tag.startswith("{"):
        payload = json.loads(raw_tag)
        if isinstance(payload, dict):
            tag_name = str(payload.get("tag", ""))
            attrs = {key: value for key, value in payload.items() if key != "tag"}
            return ParsedTag(tag_name=tag_name, raw_tag=raw_tag, attrs=attrs, source_format="json")

    bare_match = EMBEDDED_BARE_TAG_PATTERN.search(raw_tag)
    if bare_match is not None:
        bare_tag = bare_match.group(1)
        return ParsedTag(tag_name=bare_tag, raw_tag=bare_tag, attrs={}, source_format="bare_embedded")

    return ParsedTag(tag_name=raw_tag, raw_tag=raw_tag, attrs={}, source_format="bare")


def _safe_int(value: Any) -> Optional[int]:
    """Best-effort integer conversion used across XML and JSON payloads."""

    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _copy_attr_dict(attrs: dict[str, Any]) -> dict[str, Any]:
    """Create a shallow copy so stored raw attrs are not mutated later."""

    return dict(attrs)


def _empty_player_map() -> dict[int, PlayerInfo]:
    """Build a fresh 0..3 keyed PlayerInfo map."""

    return {seat: PlayerInfo(seat=seat) for seat in range(SEAT_COUNT)}


def _clone_player_info(player: PlayerInfo, *, seat: Optional[int] = None) -> PlayerInfo:
    """Copy PlayerInfo while optionally rewriting the seat index."""

    return PlayerInfo(
        seat=player.seat if seat is None else seat,
        name=player.name,
        dan=player.dan,
        rate=player.rate,
        sx=player.sx,
    )


def _is_player_live_mode(state: GameState) -> bool:
    """Return whether the parser is currently in player live websocket mode."""

    return state.parser_mode == PARSER_MODE_PLAYER_LIVE


def _is_spectator_live_mode(state: GameState) -> bool:
    """Return whether the parser is currently in spectator live websocket mode."""

    return state.parser_mode == PARSER_MODE_SPECTATOR_LIVE


def _is_xml_log_source(state: GameState) -> bool:
    """Return whether the parser is currently reading an offline XML mjlog."""

    return state.parser_mode == PARSER_MODE_XML


def _promote_parser_mode(
    state: GameState,
    parser_mode: Literal["player_live", "spectator_live", "xml_log"],
    *,
    reason: str,
) -> None:
    """Promote the parser into a more specific mode and record the transition."""

    if _is_xml_log_source(state):
        return
    if state.parser_mode == parser_mode:
        return

    previous_mode = state.parser_mode
    state.parser_mode = parser_mode
    state.diagnostics.append(
        {
            "level": "info",
            "code": "parser_mode_switch",
            "from_mode": previous_mode,
            "to_mode": parser_mode,
            "reason": reason,
        }
    )
    state.prune_live_history()


def _has_resolved_xml_seat_mapping(state: GameState) -> bool:
    """Return whether XML absolute seats can already be converted to relative seats."""

    return _is_xml_log_source(state) and state.seat_mapping_resolved and state.self_abs_seat is not None


def _source_seat_to_storage_seat(state: GameState, source_seat: int) -> int:
    """Map an incoming seat number onto the currently active storage view."""

    if _has_resolved_xml_seat_mapping(state):
        return absolute_to_relative_seat(source_seat, state.self_abs_seat)
    return source_seat


def _reorder_seat_ordered_values_to_relative(values: list[Any], self_abs_seat: int) -> list[Any]:
    """Reorder a four-seat absolute-order list into self-relative order."""

    reordered = list(values)
    for abs_seat, value in enumerate(values[:SEAT_COUNT]):
        reordered[absolute_to_relative_seat(abs_seat, self_abs_seat)] = value
    return reordered


def _normalize_player_name_for_matching(name: Optional[str]) -> Optional[str]:
    """Normalize player names before exact UN-name matching."""

    if name is None:
        return None
    normalized = decode_player_name(name)
    if normalized is None:
        return None
    stripped = normalized.strip()
    return stripped or None


def _relative_player_signature(state: GameState) -> tuple[str, str, str, str]:
    """Return the normalized relative-seat player signature used for live hanchan changes."""

    return tuple(
        _normalize_player_name_for_matching(state.players_rel[seat].name) or ""
        for seat in range(SEAT_COUNT)
    )


def _signature_has_known_names(signature: tuple[str, str, str, str]) -> bool:
    """Return whether at least one seat already has a resolved player name."""

    return any(name.strip() for name in signature)


def _merged_relative_player_signature_from_un(
    state: GameState,
    attrs: dict[str, Any],
) -> tuple[tuple[str, str, str, str], bool]:
    """Return the relative-seat player signature after applying the incoming UN payload."""

    current_signature = list(_relative_player_signature(state))
    saw_name_key = False
    for seat in range(SEAT_COUNT):
        key = f"n{seat}"
        if key not in attrs:
            continue
        saw_name_key = True
        current_signature[seat] = _normalize_player_name_for_matching(str(attrs[key])) or ""
    return tuple(current_signature), saw_name_key


def _has_live_session_payload(state: GameState) -> bool:
    """Return whether the live state currently holds a meaningful in-memory game snapshot."""

    return (
        state.current_round is not None
        or bool(state.rounds)
        or bool(state.raw_events)
        or any(state.tracker.discards[player] for player in Player)
        or bool(state.live_hand_tiles_136)
        or state.live_last_draw_tile_136 is not None
        or bool(state.live_meld_tiles_136)
        or bool(state.live_dora_indicator_tiles_136)
    )


def _reset_live_hanchan_state(
    state: GameState,
    *,
    reason: str,
    preserve_player_metadata: bool,
    previous_signature: tuple[str, str, str, str] | None = None,
    next_signature: tuple[str, str, str, str] | None = None,
    next_game_id: Optional[str] = None,
) -> None:
    """Reset live in-memory state when capture moves onto a different hanchan or seat view."""

    if state.parser_mode not in {PARSER_MODE_PLAYER_LIVE, PARSER_MODE_SPECTATOR_LIVE}:
        return
    if not _has_live_session_payload(state):
        return

    previous_game_id = state.game_id
    previous_round_id = state.round_id
    state.reset_live_session(preserve_player_metadata=preserve_player_metadata)
    if next_game_id:
        state.game_id = next_game_id
    state.diagnostics.append(
        {
            "level": "info",
            "code": "live_hanchan_reset",
            "reason": reason,
            "previous_game_id": previous_game_id,
            "next_game_id": next_game_id,
            "previous_round_id": previous_round_id,
            "previous_signature": list(previous_signature) if previous_signature is not None else None,
            "next_signature": list(next_signature) if next_signature is not None else None,
        }
    )
    state.prune_live_history()


def _rebind_live_game_id(state: GameState, next_game_id: str, *, reason: str) -> None:
    """Rewrite the in-memory live rounds onto the new authoritative game id.

    Browser reloads can deliver a usable `REINIT` before the later `TAIKYOKU` carries the new
    `log` id. In that ordering, resetting the live session would incorrectly erase the snapshot
    we already reconstructed. Instead, keep the current round and rewrite its identity fields.
    """

    previous_game_id = state.game_id
    state.game_id = next_game_id
    for round_state in state.rounds:
        round_state.round_key = build_round_key(
            state.game_id,
            round_state.kyoku_index,
            round_state.honba,
            round_state.kyotaku,
            _round_identity_oya_value(state, round_state),
        )
        round_state.round_id = build_round_id(
            state.game_id,
            round_state.kyoku_index,
            round_state.honba,
            round_state.kyotaku,
            _round_identity_oya_value(state, round_state),
        )
    state.sync_current_round_context()
    state.diagnostics.append(
        {
            "level": "info",
            "code": "live_game_id_rebound",
            "reason": reason,
            "previous_game_id": previous_game_id,
            "next_game_id": next_game_id,
        }
    )
    state.prune_live_history()


def _apply_player_metadata(players: dict[int, PlayerInfo], attrs: dict[str, Any]) -> None:
    """Apply UN metadata onto a seat-keyed PlayerInfo map."""

    for seat in range(SEAT_COUNT):
        player = players[seat]
        player.seat = seat
        name_key = f"n{seat}"
        if name_key in attrs:
            player.name = decode_player_name(str(attrs[name_key]))
    if "dan" in attrs:
        for seat, value in enumerate(str(attrs["dan"]).split(",")[:SEAT_COUNT]):
            players[seat].dan = value
    if "rate" in attrs:
        for seat, value in enumerate(str(attrs["rate"]).split(",")[:SEAT_COUNT]):
            players[seat].rate = value
    if "sx" in attrs:
        for seat, value in enumerate(str(attrs["sx"]).split(",")[:SEAT_COUNT]):
            players[seat].sx = value


def _sync_players_rel_from_players_abs(state: GameState) -> None:
    """Rebuild the relative player map from absolute XML player metadata."""

    if state.self_abs_seat is None:
        state.players_rel = _empty_player_map()
        state.refresh_player_views()
        return

    players_rel = _empty_player_map()
    for abs_seat in range(SEAT_COUNT):
        rel_seat = absolute_to_relative_seat(abs_seat, state.self_abs_seat)
        players_rel[rel_seat] = _clone_player_info(state.players_abs[abs_seat], seat=rel_seat)
    state.players_rel = players_rel
    state.refresh_player_views()


def _infer_self_abs_seat_from_players(state: GameState, player_name: Optional[str]) -> Optional[int]:
    """Infer self absolute seat by exact matching against decoded UN names."""

    normalized_name = _normalize_player_name_for_matching(player_name)
    if normalized_name is None:
        return None

    matching_seats = [
        abs_seat
        for abs_seat, player in state.players_abs.items()
        if _normalize_player_name_for_matching(player.name) == normalized_name
    ]
    if len(matching_seats) == 1:
        return matching_seats[0]
    return None


def _set_xml_self_abs_seat(state: GameState, self_abs_seat: Optional[int]) -> None:
    """Apply the resolved XML self seat and refresh relative player metadata."""

    if self_abs_seat is None:
        state.self_abs_seat = None
        state.seat_mapping_resolved = False
        state.players_rel = _empty_player_map()
        state.refresh_player_views()
        return
    if not 0 <= self_abs_seat < SEAT_COUNT:
        raise ValueError(f"self_abs_seat must be in 0..{SEAT_COUNT - 1}: {self_abs_seat}")

    state.self_abs_seat = self_abs_seat
    state.seat_mapping_resolved = True
    _sync_players_rel_from_players_abs(state)


def _maybe_resolve_xml_self_abs_seat(state: GameState) -> None:
    """Resolve XML self_abs_seat from explicit input or known self player name."""

    if not _is_xml_log_source(state):
        return
    if state.self_abs_seat is not None:
        _set_xml_self_abs_seat(state, state.self_abs_seat)
        return

    inferred_self_abs_seat = _infer_self_abs_seat_from_players(state, state.self_player_name)
    _set_xml_self_abs_seat(state, inferred_self_abs_seat)


def _normalize_ten_scores_for_state(state: GameState, score_values: list[int]) -> list[int]:
    """Normalize and reorder score arrays into the active seat view."""

    normalized_scores = _normalize_ten_scores(score_values)
    if _has_resolved_xml_seat_mapping(state):
        return _reorder_seat_ordered_values_to_relative(normalized_scores, state.self_abs_seat)
    return normalized_scores


def _set_round_oya_from_source(state: GameState, round_state: RoundState, source_oya: Optional[int]) -> None:
    """Store dealer seat in both absolute and relative fields when available."""

    if source_oya is None:
        return

    if _is_xml_log_source(state):
        round_state.oya_abs = source_oya
        if _has_resolved_xml_seat_mapping(state):
            round_state.oya_rel = absolute_to_relative_seat(source_oya, state.self_abs_seat)
            round_state.oya = round_state.oya_rel
        else:
            round_state.oya_rel = None
            round_state.oya = source_oya
        return

    round_state.oya = source_oya
    round_state.oya_rel = source_oya


def _round_identity_oya_value(state: GameState, round_state: RoundState) -> Optional[int]:
    """Return the dealer seat value used for round identity tracking."""

    if _is_xml_log_source(state) and round_state.oya_abs is not None:
        return round_state.oya_abs
    return round_state.oya


def _copy_attrs_with_mapped_seats(
    state: GameState,
    attrs: dict[str, Any],
    *seat_keys: str,
) -> dict[str, Any]:
    """Copy attrs while rewriting explicit seat fields into the active seat view."""

    copied_attrs = _copy_attr_dict(attrs)
    for seat_key in seat_keys:
        seat_value = _safe_int(attrs.get(seat_key))
        if seat_value is None:
            continue
        if _is_xml_log_source(state):
            copied_attrs[f"{seat_key}_abs"] = seat_value
            copied_attrs[seat_key] = _source_seat_to_storage_seat(state, seat_value)
        else:
            copied_attrs[seat_key] = seat_value
    return copied_attrs


def _remap_seat_keyed_attrs(
    state: GameState,
    attrs: dict[str, Any],
    *prefixes: str,
) -> dict[str, Any]:
    """Remap seat-suffixed XML attribute keys into the active seat view when possible."""

    copied_attrs = _copy_attr_dict(attrs)
    if not _has_resolved_xml_seat_mapping(state):
        return copied_attrs

    remapped_items: dict[str, Any] = {}
    for prefix in prefixes:
        for abs_seat in range(SEAT_COUNT):
            key = f"{prefix}{abs_seat}"
            if key not in copied_attrs:
                continue
            rel_seat = absolute_to_relative_seat(abs_seat, state.self_abs_seat)
            remapped_items[f"{prefix}{rel_seat}"] = copied_attrs.pop(key)
    copied_attrs.update(remapped_items)
    return copied_attrs


def _extract_discard_delay_metadata(
    state: GameState,
    delay_prefix: Optional[str],
) -> tuple[Optional[int], Optional[str], Literal["confirmed", "heuristic", "unknown"]]:
    """Decode spectator discard timing prefixes without treating them as tile ids."""

    if delay_prefix is None:
        return None, None, "unknown"

    delay_ms = _safe_int(delay_prefix)
    if delay_ms is None:
        return None, None, "unknown"

    if not _is_spectator_live_mode(state):
        _promote_parser_mode(
            state,
            PARSER_MODE_SPECTATOR_LIVE,
            reason="Observed discard tag with numeric prefix before DEFG",
        )
    return delay_ms, "discard_prefix_ms", "heuristic"


def _normalize_ten_scores(score_values: list[int]) -> list[int]:
    """Convert observed packet `ten` values from 100-point units into actual points."""

    return [value * 100 for value in score_values[:SEAT_COUNT]]


def _empty_seat_list_map() -> dict[int, list[Any]]:
    return {seat: [] for seat in range(SEAT_COUNT)}


def _extract_hand_snapshot(attrs: dict[str, Any]) -> HandSnapshot:
    """Extract `hai` / `hai0..hai3` using the source packet's native seat indexing."""

    seat_hands = _empty_seat_list_map()
    explicit_seat_count = 0
    for seat in range(SEAT_COUNT):
        key = f"hai{seat}"
        if key not in attrs:
            continue
        seat_hands[seat] = parse_csv_int_list(attrs.get(key))
        explicit_seat_count += 1

    self_hand_136: list[int] = []
    if "hai" in attrs:
        self_hand_136 = parse_csv_int_list(attrs.get("hai"))

    return HandSnapshot(
        seat_hands=seat_hands,
        self_hand_136=self_hand_136,
        explicit_seat_count=explicit_seat_count,
    )


def _apply_round_header(
    state: GameState,
    round_state: RoundState,
    attrs: dict[str, Any],
    *,
    reset_dora: bool,
) -> None:
    """Apply shared INIT/REINIT header fields using the active seat interpretation."""

    seed = parse_csv_int_list(attrs.get("seed"))
    ten = parse_csv_int_list(attrs.get("ten"))

    if len(seed) >= 1:
        round_state.kyoku_index = seed[0]
    if len(seed) >= 2:
        round_state.honba = seed[1]
    if len(seed) >= 3:
        round_state.kyotaku = seed[2]
    if len(seed) >= 4:
        round_state.dice_1_minus_1 = seed[3]
    if len(seed) >= 5:
        round_state.dice_2_minus_1 = seed[4]
    if len(seed) >= 6:
        seed_dora_indicators = list(seed[5:])
        if reset_dora:
            round_state.dora_indicators_136 = []
        for tile_136 in seed_dora_indicators:
            if tile_136 not in round_state.dora_indicators_136:
                round_state.dora_indicators_136.append(tile_136)

    if len(ten) >= SEAT_COUNT:
        round_state.scores = _normalize_ten_scores_for_state(state, ten)
    if "oya" in attrs:
        _set_round_oya_from_source(state, round_state, _safe_int(attrs.get("oya")))


def _sync_round_identity(
    state: GameState,
    round_state: RoundState,
    *,
    preserve_existing: bool,
) -> None:
    """Populate round/game identity fields from the current round header."""

    round_state.seat_order = list(state.seat_order)
    if not preserve_existing or round_state.round_key is None:
        round_state.round_key = build_round_key(
            state.game_id,
            round_state.kyoku_index,
            round_state.honba,
            round_state.kyotaku,
            _round_identity_oya_value(state, round_state),
        )
    if not preserve_existing or round_state.round_id is None:
        round_state.round_id = build_round_id(
            state.game_id,
            round_state.kyoku_index,
            round_state.honba,
            round_state.kyotaku,
            _round_identity_oya_value(state, round_state),
        )
    state.sync_current_round_context()


def _apply_init_hand_snapshot(
    state: GameState,
    round_state: RoundState,
    hand_snapshot: HandSnapshot,
) -> None:
    """Apply INIT hand payloads and preserve absolute/relative XML views."""

    round_state.initial_self_hand_136 = list(hand_snapshot.self_hand_136)
    round_state.snapshot_is_partial = hand_snapshot.is_partial
    round_state.initial_hands_136 = _empty_seat_list_map()
    round_state.initial_hands_abs_136 = _empty_seat_list_map()
    round_state.initial_hands_rel_136 = _empty_seat_list_map()
    round_state.current_hands_136 = _empty_seat_list_map()

    for source_seat in range(SEAT_COUNT):
        hand_tiles = list(hand_snapshot.seat_hands[source_seat])
        if not hand_tiles:
            continue

        storage_seat = _source_seat_to_storage_seat(state, source_seat)
        round_state.initial_hands_136[storage_seat] = list(hand_tiles)
        round_state.current_hands_136[storage_seat] = list(hand_tiles)

        if _is_xml_log_source(state):
            round_state.initial_hands_abs_136[source_seat] = list(hand_tiles)
            if _has_resolved_xml_seat_mapping(state):
                rel_seat = absolute_to_relative_seat(source_seat, state.self_abs_seat)
                round_state.initial_hands_rel_136[rel_seat] = list(hand_tiles)
        else:
            round_state.initial_hands_rel_136[storage_seat] = list(hand_tiles)

    if hand_snapshot.has_self_hand:
        if not round_state.current_hands_136.get(LOCAL_RELATIVE_SEAT) and (
            not _is_xml_log_source(state) or _has_resolved_xml_seat_mapping(state)
        ):
            round_state.initial_hands_136[LOCAL_RELATIVE_SEAT] = list(hand_snapshot.self_hand_136)
            round_state.current_hands_136[LOCAL_RELATIVE_SEAT] = list(hand_snapshot.self_hand_136)
            round_state.initial_hands_rel_136[LOCAL_RELATIVE_SEAT] = list(hand_snapshot.self_hand_136)
        if _is_xml_log_source(state) and state.self_abs_seat is not None:
            if not round_state.initial_hands_abs_136.get(state.self_abs_seat):
                round_state.initial_hands_abs_136[state.self_abs_seat] = list(hand_snapshot.self_hand_136)

    if not round_state.initial_self_hand_136 and round_state.initial_hands_rel_136.get(LOCAL_RELATIVE_SEAT):
        round_state.initial_self_hand_136 = list(round_state.initial_hands_rel_136[LOCAL_RELATIVE_SEAT])


def _apply_reinit_hand_snapshot(
    state: GameState,
    round_state: RoundState,
    hand_snapshot: HandSnapshot,
) -> None:
    """Apply REINIT hand payloads as an overwrite snapshot, not round initialisation."""

    round_state.snapshot_is_partial = hand_snapshot.is_partial
    round_state.current_hands_136 = _empty_seat_list_map()

    for source_seat in range(SEAT_COUNT):
        hand_tiles = list(hand_snapshot.seat_hands[source_seat])
        if not hand_tiles:
            continue
        storage_seat = _source_seat_to_storage_seat(state, source_seat)
        round_state.current_hands_136[storage_seat] = list(hand_tiles)

    if hand_snapshot.has_self_hand and not round_state.current_hands_136.get(LOCAL_RELATIVE_SEAT) and (
        not _is_xml_log_source(state) or _has_resolved_xml_seat_mapping(state)
    ):
        round_state.current_hands_136[LOCAL_RELATIVE_SEAT] = list(hand_snapshot.self_hand_136)


def _start_round_from_init(
    state: GameState,
    attrs: dict[str, Any],
) -> RoundState:
    """Create a fresh round unconditionally when an INIT tag arrives."""

    round_state = state.begin_round(started_from_init_like=True)
    _apply_round_header(state, round_state, attrs, reset_dora=True)
    _sync_round_identity(state, round_state, preserve_existing=False)
    round_state.raw_attrs = _copy_attr_dict(attrs)
    round_state.raw_init_attrs = _copy_attr_dict(attrs)
    return round_state


def _mark_round_snapshot_bootstrap(state: GameState, round_state: RoundState) -> None:
    """Advance the live snapshot bootstrap sequence for INIT/REINIT-style table rebuilds."""

    state.live_snapshot_bootstrap_sequence += 1
    round_state.snapshot_bootstrap_sequence = state.live_snapshot_bootstrap_sequence


def _prepare_round_for_reinit(
    state: GameState,
    attrs: dict[str, Any],
) -> RoundState:
    """Return the round that should receive a REINIT overwrite snapshot."""

    created_new_round = _reinit_requires_new_round(state, state.current_round, attrs)
    if created_new_round:
        state.begin_round(started_from_init_like=True)
    round_state = state.ensure_round()
    if created_new_round or not round_state.events:
        round_state.started_from_init_like = True
    _apply_round_header(state, round_state, attrs, reset_dora=True)
    _sync_round_identity(state, round_state, preserve_existing=True)
    if not round_state.raw_attrs:
        round_state.raw_attrs = _copy_attr_dict(attrs)
    return round_state


def _reset_round_runtime_snapshot(round_state: RoundState) -> None:
    """Clear runtime-mutated fields before applying a REINIT overwrite."""

    round_state.discards = _empty_seat_list_map()
    round_state.melds = _empty_seat_list_map()
    round_state.draws = _empty_seat_list_map()
    round_state.last_draw_tiles_136 = {seat: None for seat in range(SEAT_COUNT)}
    round_state.pending_riichi_markers = {seat: False for seat in range(SEAT_COUNT)}
    round_state.discard_thinking_starts = {seat: None for seat in range(SEAT_COUNT)}
    round_state.discard_thinking_before_reach = {seat: None for seat in range(SEAT_COUNT)}
    round_state.reach_state = {seat: "none" for seat in range(SEAT_COUNT)}
    round_state.result = None
    round_state.reinit_kawa_raw = _empty_seat_list_map()
    round_state.validation_issues = []


def _remove_tile_from_hand(hand_tiles: list[int], tile_136: int) -> None:
    """Remove a single tile from a mutable hand list when it exists."""

    try:
        hand_tiles.remove(tile_136)
    except ValueError:
        pass


def _is_client_discard_request_discard(discard: Discard) -> bool:
    """Return whether one discard was created from the browser/client send packet."""

    return str(getattr(discard, "raw_tag", "") or "").startswith(
        CLIENT_DISCARD_REQUEST_RAW_TAG_PREFIX
    )


def _latest_matching_client_discard_request(
    round_state: RoundState,
    seat: int,
    tile_136: int,
) -> Discard | None:
    """Return the latest provisional self discard matching a later server confirmation."""

    if seat != LOCAL_RELATIVE_SEAT:
        return None
    discards = round_state.discards.get(seat, [])
    if not discards:
        return None
    latest_discard = discards[-1]
    if not _is_client_discard_request_discard(latest_discard):
        return None
    if int(latest_discard.tile_136) != int(tile_136):
        return None
    return latest_discard


def _update_latest_tracker_discard_from_capture_discard(
    state: GameState,
    seat: int,
    discard: Discard,
    *,
    timestamp: Optional[float],
) -> None:
    """Keep the legacy UI tracker aligned when a provisional discard is confirmed."""

    tile_37 = tile136_to_tile37(discard.tile_136)
    if tile_37 is None:
        return
    try:
        tracker_discards = state.tracker.discards[Player(seat)]
    except (KeyError, ValueError):
        return
    if not tracker_discards:
        return
    tracker_discard = tracker_discards[-1]
    if int(getattr(tracker_discard, "tile_id", -1)) != int(tile_37):
        return
    tracker_discard.tag = discard.raw_tag
    tracker_discard.timestamp = timestamp
    tracker_discard.riichi_marker_before = discard.riichi_marker_before
    tracker_discard.thinking_time_ms = discard.thinking_time_ms
    tracker_discard.thinking_time_source = discard.thinking_time_source
    tracker_discard.thinking_time_before_reach_ms = discard.thinking_time_before_reach_ms
    tracker_discard.thinking_time_before_reach_source = discard.thinking_time_before_reach_source
    tracker_discard.self_hand_tiles_before_discard_136 = list(
        discard.self_hand_tiles_before_discard_136
    )
    tracker_discard.round_discard_index = discard.round_discard_index
    tracker_discard.event_index = discard.event_index


def _sync_live_state(state: GameState) -> None:
    """Refresh the live arrays that the current UI already consumes."""

    round_state = state.current_round
    if round_state is None:
        state.live_hand_tiles_136.clear()
        state.live_last_draw_tile_136 = None
        state.live_meld_tiles_136.clear()
        state.live_dora_indicator_tiles_136.clear()
        return

    if _is_xml_log_source(state) and not state.seat_mapping_resolved:
        state.live_hand_tiles_136.clear()
        state.live_last_draw_tile_136 = None
    else:
        display_hand_tiles, display_draw_tile = _build_display_hand_tiles(
            round_state,
            LOCAL_RELATIVE_SEAT,
        )
        state.live_hand_tiles_136[:] = display_hand_tiles
        state.live_last_draw_tile_136 = display_draw_tile
    state.live_meld_tiles_136[:] = [
        tile_136
        for melds in round_state.melds.values()
        for meld in melds
        for tile_136 in meld.consumed_tile_ids
    ]
    state.live_dora_indicator_tiles_136[:] = list(round_state.dora_indicators_136)


def _build_display_hand_tiles(
    round_state: RoundState,
    seat: int,
) -> tuple[list[int], Optional[int]]:
    """Return a riipai-sorted concealed hand plus the active draw tile when present."""

    hand_tiles = list(round_state.current_hands_136.get(seat, []))
    draw_tile = round_state.last_draw_tiles_136.get(seat)
    if draw_tile is not None and draw_tile in hand_tiles:
        concealed_tiles = list(hand_tiles)
        concealed_tiles.remove(draw_tile)
        concealed_tiles.sort()
        return concealed_tiles + [draw_tile], draw_tile

    hand_tiles.sort()
    return hand_tiles, None


def _rebuild_tracker_from_round(state: GameState) -> None:
    """Rebuild the legacy discard tracker from the current round snapshot."""

    for player in Player:
        state.tracker.discards[player].clear()

    round_state = state.current_round
    if round_state is None:
        return

    for seat in range(SEAT_COUNT):
        player = Player(seat)
        for discard in round_state.discards[seat]:
            tile_id = tile136_to_tile37(discard.tile_136)
            if tile_id is None:
                continue
            state.tracker.add_discard(
                player,
                tile_id,
                tsumogiri=discard.tsumogiri,
                called=discard.called,
                tag=discard.raw_tag,
                riichi_marker_before=discard.riichi_marker_before,
            )
            tracker_discard = state.tracker.discards[player][-1]
            tracker_discard.riichi_marker_before = discard.riichi_marker_before
            tracker_discard.thinking_time_ms = discard.thinking_time_ms
            tracker_discard.thinking_time_source = discard.thinking_time_source
            tracker_discard.thinking_time_before_reach_ms = discard.thinking_time_before_reach_ms
            tracker_discard.thinking_time_before_reach_source = (
                discard.thinking_time_before_reach_source
            )
            tracker_discard.self_hand_tiles_before_discard_136 = list(
                discard.self_hand_tiles_before_discard_136
            )
            tracker_discard.lagged = discard.lagged
            tracker_discard.lag_delay_ms = discard.lag_delay_ms
            # Renderer-side river markers also read tracker discards during live redraws,
            # so snapshot rebuilds must preserve stable discard ordering metadata here too.
            tracker_discard.round_discard_index = discard.round_discard_index
            tracker_discard.event_index = discard.event_index


def _has_seat_payload(attrs: dict[str, Any], prefix: str) -> bool:
    """Return whether any seat-indexed snapshot key with the given prefix exists."""

    return any(f"{prefix}{seat}" in attrs for seat in range(SEAT_COUNT))


def _capture_discard_metadata_seed(round_state: RoundState) -> dict[int, list[Discard]]:
    """Capture the current discard objects so matching snapshot prefixes can reuse metadata."""

    return {
        seat: list(round_state.discards.get(seat, []))
        for seat in range(SEAT_COUNT)
    }


def _visible_snapshot_discards(discards: list[Discard]) -> list[Discard]:
    """Return only the discards that still remain visible in the river snapshot."""

    return [discard for discard in discards if not discard.called]


def _copy_discard_runtime_metadata(source: Discard, target: Discard) -> None:
    """Copy discard metadata that should survive snapshot refreshes."""

    target.round_discard_index = source.round_discard_index
    target.hand_tiles_before_discard_136 = list(source.hand_tiles_before_discard_136)
    target.self_hand_tiles_before_discard_136 = list(source.self_hand_tiles_before_discard_136)
    target.tsumogiri = source.tsumogiri
    target.is_tsumogiri_estimated = source.is_tsumogiri_estimated
    target.riichi_marker_before = source.riichi_marker_before
    target.raw_tag = source.raw_tag
    target.called = source.called
    target.thinking_time_ms = source.thinking_time_ms
    target.thinking_time_source = source.thinking_time_source
    target.thinking_time_before_reach_ms = source.thinking_time_before_reach_ms
    target.thinking_time_before_reach_source = source.thinking_time_before_reach_source
    target.lagged = source.lagged
    target.lag_delay_ms = source.lag_delay_ms
    target.event_index = source.event_index


def _carry_over_snapshot_discard_metadata(
    round_state: RoundState,
    previous_discards: dict[int, list[Discard]] | None,
) -> None:
    """Reuse existing discard metadata when a snapshot only appends newer discards."""

    if previous_discards is None:
        return

    for seat in range(SEAT_COUNT):
        existing_discards = _visible_snapshot_discards(previous_discards.get(seat, []))
        snapshot_discards = round_state.discards.get(seat, [])
        if not existing_discards or len(snapshot_discards) < len(existing_discards):
            continue

        expected_prefix = [discard.tile_136 for discard in existing_discards]
        actual_prefix = [discard.tile_136 for discard in snapshot_discards[: len(existing_discards)]]
        if actual_prefix != expected_prefix:
            continue

        for index, existing_discard in enumerate(existing_discards):
            _copy_discard_runtime_metadata(existing_discard, snapshot_discards[index])


def _merge_snapshot_discards_with_previous_history(
    snapshot_discards: list[Discard],
    previous_discards: list[Discard] | None,
) -> list[Discard]:
    """Keep previously called discards in history while overlaying the new visible snapshot.

    Tenhou REINIT rivers only expose still-visible discards. Previously called tiles can therefore
    disappear from `kawa0..kawa3`, but the internal round history should keep them so lag/call
    metadata and discard ordering survive browser reload recovery.
    """

    if not previous_discards:
        return snapshot_discards

    previous_visible_discards = _visible_snapshot_discards(previous_discards)
    if len(snapshot_discards) < len(previous_visible_discards):
        return snapshot_discards

    expected_prefix = [discard.tile_136 for discard in previous_visible_discards]
    actual_prefix = [discard.tile_136 for discard in snapshot_discards[: len(previous_visible_discards)]]
    if actual_prefix != expected_prefix:
        return snapshot_discards

    merged_discards: list[Discard] = []
    snapshot_index = 0

    # Rebuild the previous full discard sequence, replacing only the still-visible tiles with the
    # snapshot copies. Called tiles stay in-place even though REINIT no longer lists them in kawa.
    for previous_discard in previous_discards:
        if previous_discard.called:
            merged_discards.append(previous_discard)
            continue
        if snapshot_index >= len(snapshot_discards):
            return snapshot_discards
        merged_discards.append(snapshot_discards[snapshot_index])
        snapshot_index += 1

    while snapshot_index < len(snapshot_discards):
        merged_discards.append(snapshot_discards[snapshot_index])
        snapshot_index += 1

    return merged_discards


def _reindex_round_discards(round_state: RoundState) -> None:
    """Assign missing round-discard indices after a snapshot rebuild.

    Existing indices already came from live packets and encode the observed chronological order.
    REINIT-only tail discards do not expose cross-seat interleave timing, so they are appended
    after the known prefix in a deterministic fallback order.
    """

    existing_indices = [
        discard.round_discard_index
        for discards in round_state.discards.values()
        for discard in discards
        if discard.round_discard_index is not None
    ]
    round_discard_index = (max(existing_indices) + 1) if existing_indices else 0
    for seat in range(SEAT_COUNT):
        for discard in round_state.discards[seat]:
            if discard.round_discard_index is not None:
                continue
            discard.round_discard_index = round_discard_index
            round_discard_index += 1


def _apply_snapshot_meld_payload(
    state: GameState,
    round_state: RoundState,
    attrs: dict[str, Any],
    *,
    timestamp: Optional[float],
    raw_tag: str,
    clear_existing: bool,
) -> None:
    """Apply seat-indexed `m0..m3` payloads onto the active round snapshot."""

    if not _has_seat_payload(attrs, "m"):
        return
    if clear_existing:
        round_state.melds = _empty_seat_list_map()

    for source_seat in range(SEAT_COUNT):
        key = f"m{source_seat}"
        if key not in attrs:
            continue
        storage_seat = _source_seat_to_storage_seat(state, source_seat)
        for meld_code in parse_csv_int_list(attrs.get(key)):
            try:
                meld = decode_meld(storage_seat, meld_code)
            except ValueError as exc:
                _record_unknown(
                    state,
                    timestamp,
                    raw_tag,
                    f"Failed to decode snapshot meld {key}={meld_code}: {exc}",
                    attrs,
                )
                continue
            _assign_meld_id(meld, f"snapshot-{len(state.rounds) - 1}-{storage_seat}")
            _upsert_meld(round_state, meld)


def _apply_snapshot_kawa_payload(
    state: GameState,
    round_state: RoundState,
    attrs: dict[str, Any],
    *,
    previous_discards: dict[int, list[Discard]] | None,
    clear_existing: bool,
) -> None:
    """Apply seat-indexed `kawa0..kawa3` payloads and preserve matching discard metadata."""

    if not _has_seat_payload(attrs, "kawa"):
        return
    if clear_existing:
        round_state.discards = _empty_seat_list_map()
        round_state.reinit_kawa_raw = _empty_seat_list_map()

    for source_seat in range(SEAT_COUNT):
        key = f"kawa{source_seat}"
        if key not in attrs:
            continue
        storage_seat = _source_seat_to_storage_seat(state, source_seat)
        raw_kawa, discards = _parse_reinit_kawa(attrs.get(key))
        round_state.reinit_kawa_raw[storage_seat] = raw_kawa
        round_state.discards[storage_seat] = _merge_snapshot_discards_with_previous_history(
            discards,
            previous_discards.get(storage_seat) if previous_discards is not None else None,
        )

    _carry_over_snapshot_discard_metadata(round_state, previous_discards)
    _reindex_round_discards(round_state)


def _clear_pending_response_discard(round_state: RoundState) -> None:
    """Drop the current unresolved discard-response measurement state."""

    round_state.pending_response_discard = None


def _begin_pending_response_discard(
    round_state: RoundState,
    seat: int,
    timestamp: Optional[float],
) -> None:
    """Start a discard-response measurement window for the latest discard."""

    discard_index = len(round_state.discards[seat]) - 1
    if discard_index < 0:
        return
    round_state.pending_response_discard = (seat, discard_index, timestamp)


def _set_discard_thinking_start(
    round_state: RoundState,
    seat: int,
    timestamp: Optional[float],
    source: str,
) -> None:
    """Record the most recent segment start that should anchor the next discard's thinking time."""

    if 0 <= seat < SEAT_COUNT:
        round_state.discard_thinking_starts[seat] = (timestamp, source)
        if source != "reach":
            round_state.discard_thinking_before_reach[seat] = None


def _split_discard_thinking_at_reach(
    round_state: RoundState,
    seat: int,
    timestamp: Optional[float],
) -> None:
    """Split the current thinking timer into pre-REACH and post-REACH segments."""

    if not 0 <= seat < SEAT_COUNT:
        return

    start = round_state.discard_thinking_starts.get(seat)
    pre_reach_ms: Optional[float] = None
    pre_reach_source: Optional[str] = None
    if start is not None:
        start_timestamp, start_source = start
        pre_reach_source = start_source
        if timestamp is not None and start_timestamp is not None:
            pre_reach_ms = round((timestamp - start_timestamp) * 1000.0, 3)
    round_state.discard_thinking_before_reach[seat] = (pre_reach_ms, pre_reach_source)
    round_state.discard_thinking_starts[seat] = (timestamp, "reach")


def _consume_discard_thinking_start(
    round_state: RoundState,
    seat: int,
    timestamp: Optional[float],
) -> tuple[Optional[float], Optional[str], Optional[float], Optional[str]]:
    """Return and clear the post-REACH and pre-REACH thinking-time segments for one discard."""

    start = round_state.discard_thinking_starts.get(seat)
    round_state.discard_thinking_starts[seat] = None
    pre_reach = round_state.discard_thinking_before_reach.get(seat)
    round_state.discard_thinking_before_reach[seat] = None
    if start is None:
        if pre_reach is None:
            return None, None, None, None
        return None, None, pre_reach[0], pre_reach[1]

    start_timestamp, source = start
    thinking_time_ms = None
    if timestamp is not None and start_timestamp is not None:
        thinking_time_ms = round((timestamp - start_timestamp) * 1000.0, 3)
    thinking_time_before_reach_ms = None
    thinking_time_before_reach_source = None
    if pre_reach is not None:
        thinking_time_before_reach_ms, thinking_time_before_reach_source = pre_reach
    return (
        thinking_time_ms,
        source,
        thinking_time_before_reach_ms,
        thinking_time_before_reach_source,
    )


def _set_discard_lag_metadata(
    state: GameState,
    round_state: RoundState,
    seat: int,
    discard_index: int,
    *,
    lagged: int,
    lag_delay_ms: Optional[float],
) -> None:
    """Mirror lag metadata onto both round-state and legacy tracker discards."""

    discard_event_index = -1
    if 0 <= seat < SEAT_COUNT and 0 <= discard_index < len(round_state.discards[seat]):
        round_discard = round_state.discards[seat][discard_index]
        round_discard.lagged = lagged
        round_discard.lag_delay_ms = lag_delay_ms
        discard_event_index = round_discard.event_index

    if 0 <= discard_event_index < len(state.events):
        discard_event = state.events[discard_event_index]
        if discard_event.event_type == "discard" and discard_event.seat == seat:
            discard_event.lagged = lagged
            discard_event.lag_delay_ms = lag_delay_ms
            discard_event.attrs["lagged"] = lagged
            if lag_delay_ms is not None:
                discard_event.attrs["lag_delay_ms"] = lag_delay_ms
            else:
                discard_event.attrs.pop("lag_delay_ms", None)

    if not 0 <= seat < SEAT_COUNT:
        return
    tracker_discards = state.tracker.discards[Player(seat)]
    if 0 <= discard_index < len(tracker_discards):
        tracker_discard = tracker_discards[discard_index]
        tracker_discard.lagged = lagged
        tracker_discard.lag_delay_ms = lag_delay_ms


def _resolve_pending_response_discard(
    state: GameState,
    round_state: RoundState,
    timestamp: Optional[float],
    resolved_by_call: bool,
) -> None:
    """Finalize the current discard-response measurement against draw/open-call arrival."""

    pending = round_state.pending_response_discard
    if pending is None:
        return

    round_state.pending_response_discard = None
    seat, discard_index, discard_timestamp = pending
    lagged = LAG_FLAG_UNKNOWN
    lag_delay_ms = None
    if timestamp is not None and discard_timestamp is not None:
        delta_seconds = timestamp - discard_timestamp
        if delta_seconds >= LAG_THRESHOLD_SECONDS:
            lag_delay_ms = round(delta_seconds * 1000.0, 3)
            # A real open call keeps the called flag regardless of duration.
            # Only unresolved skip-side delays are downgraded into the system-delay bucket.
            if resolved_by_call:
                lagged = LAG_FLAG_TRUE_CALLED
            elif lag_delay_ms <= LAG_SYSTEM_DELAY_MAX_MS:
                lagged = LAG_FLAG_SYSTEM_DELAY
            else:
                lagged = LAG_FLAG_UNCONFIRMED
    _set_discard_lag_metadata(
        state,
        round_state,
        seat,
        discard_index,
        lagged=lagged,
        lag_delay_ms=lag_delay_ms,
    )


def _resolve_pending_response_discard_on_next_discard(
    state: GameState,
    round_state: RoundState,
    timestamp: Optional[float],
) -> None:
    """Fallback-resolve the previous discard when the next observed event is another discard.

    Spectator/live payloads can omit draw tags. In that case, the next discard timestamp is the
    earliest observable boundary we have, and the lag metadata must stay attached to the previous
    discard instead of being dropped or shifted onto the current one.
    """

    _resolve_pending_response_discard(
        state,
        round_state,
        timestamp,
        resolved_by_call=False,
    )


def _meld_resolves_previous_discard(meld: Meld) -> bool:
    """Return whether this meld is an open response to another player's discard."""

    if meld.meld_type not in {"chi", "pon", "daiminkan"}:
        return False
    source_seat = meld_from_who_to_seat(meld.who, meld.from_who)
    return source_seat is not None and source_seat != meld.who


def _resolve_pending_response_discard_for_meld(
    state: GameState,
    round_state: RoundState,
    timestamp: Optional[float],
    meld: Meld,
) -> None:
    """Resolve lag measurement only when an open meld matches the pending source discard."""

    if not _meld_resolves_previous_discard(meld):
        return
    pending = round_state.pending_response_discard
    if pending is None or meld.called_tile_id is None:
        return

    source_seat = meld_from_who_to_seat(meld.who, meld.from_who)
    if source_seat is None:
        return
    seat, discard_index, _discard_timestamp = pending
    if seat != source_seat:
        return
    if not 0 <= discard_index < len(round_state.discards[seat]):
        return
    if round_state.discards[seat][discard_index].tile_136 != meld.called_tile_id:
        return
    _resolve_pending_response_discard(state, round_state, timestamp, resolved_by_call=True)


def _mark_called_discard(state: GameState, round_state: RoundState, meld: Meld) -> None:
    """Mark the source discard as consumed by an open meld."""

    if meld.meld_type not in {"chi", "pon", "daiminkan"}:
        return
    if meld.called_tile_id is None:
        return

    source_seat = meld_from_who_to_seat(meld.who, meld.from_who)
    if source_seat is None or source_seat == meld.who:
        return

    round_discards = round_state.discards[source_seat]
    called_round_index: int | None = None
    for index in range(len(round_discards) - 1, -1, -1):
        discard = round_discards[index]
        if discard.tile_136 != meld.called_tile_id or discard.called:
            continue
        discard.called = True
        discard.lagged = LAG_FLAG_TRUE_CALLED
        called_round_index = index
        break

    tracker_discards = state.tracker.discards[Player(source_seat)]
    if called_round_index is not None and called_round_index < len(tracker_discards):
        tracker_discards[called_round_index].called = True
        _set_discard_lag_metadata(
            state,
            round_state,
            source_seat,
            called_round_index,
            lagged=LAG_FLAG_TRUE_CALLED,
            lag_delay_ms=round_discards[called_round_index].lag_delay_ms,
        )
        return

    target_tile_37 = tile136_to_tile37(meld.called_tile_id)
    if target_tile_37 is None:
        return
    for discard in reversed(tracker_discards):
        if discard.tile_id == target_tile_37 and not discard.called:
            discard.called = True
            return


def _assign_meld_id(meld: Meld, prefix: str) -> None:
    """Assign a stable trace id when a meld does not have one yet."""

    if not meld.meld_id:
        meld.meld_id = f"{prefix}-{meld.who}-{meld.meld_type}-{meld.raw_m}"


def _upsert_meld(round_state: RoundState, meld: Meld) -> None:
    """Insert or replace a meld while supporting pon -> kakan upgrades."""

    seat_melds = round_state.melds[meld.who]
    if meld.meld_type == "kakan":
        for index, existing in enumerate(seat_melds):
            if existing.meld_type not in {"pon", "kakan"}:
                continue
            if existing.tile_34 != meld.tile_34:
                continue
            meld.upgraded_from = existing.meld_id or None
            seat_melds[index] = meld
            return
    seat_melds.append(meld)


def _parse_reinit_kawa(value: Any) -> tuple[list[int], list[Discard]]:
    """Decode a REINIT kawa list into raw tokens and visible discard tiles.

    REINIT kawa keeps marker values inline with visible discard ids. We preserve the raw token
    sequence, and currently treat `255` as "the next visible discard is the riichi declaration
    discard". Other markers such as `254` are still preserved without extra interpretation.
    REINIT-only tail discards have no original draw/discard boundary, so they start as estimated
    tsumogiri until a shared-prefix metadata carry-over can overwrite them with observed values.
    """

    raw_tokens = parse_csv_int_list(value)
    discards: list[Discard] = []
    next_discard_has_riichi_marker = False
    for item in raw_tokens:
        if item == 255:
            next_discard_has_riichi_marker = True
            continue
        if not 0 <= item <= 135:
            continue
        discards.append(
            Discard(
                tile_136=item,
                tsumogiri=True,
                is_tsumogiri_estimated=True,
                raw_tag=f"REINIT_KAWA:{item}",
                riichi_marker_before=next_discard_has_riichi_marker,
            )
        )
        next_discard_has_riichi_marker = False
    return raw_tokens, discards


def _restore_reach_state_from_snapshot_discards(round_state: RoundState) -> None:
    """Rebuild accepted riichi state from snapshot discards after REINIT overwrite."""

    round_state.reach_state = {seat: "none" for seat in range(SEAT_COUNT)}
    for seat in range(SEAT_COUNT):
        if any(discard.riichi_marker_before for discard in round_state.discards.get(seat, [])):
            round_state.reach_state[seat] = "accepted"


def _snapshot_visible_discards_by_seat(
    state: GameState,
    attrs: dict[str, Any],
) -> dict[int, list[int]]:
    """Return visible discard tile ids from `kawa0..kawa3` keyed by storage seat."""

    discards_by_seat = _empty_seat_list_map()
    for source_seat in range(SEAT_COUNT):
        key = f"kawa{source_seat}"
        if key not in attrs:
            continue
        storage_seat = _source_seat_to_storage_seat(state, source_seat)
        raw_tokens = parse_csv_int_list(attrs.get(key))
        discards_by_seat[storage_seat] = [item for item in raw_tokens if 0 <= item <= 135]
    return discards_by_seat


def _compare_snapshot_discards(
    state: GameState,
    current_round: RoundState,
    attrs: dict[str, Any],
) -> SnapshotDiscardComparison | None:
    """Compare the current visible rivers against a snapshot river payload.

    `REINIT` after browser reload often arrives with the same river prefix plus a few extra
    discards that the live parser missed while the page was refreshing. That append-only case is
    still the same round and must keep previously measured lag/thinking metadata.
    """

    if not _has_seat_payload(attrs, "kawa"):
        return None

    snapshot_discards = _snapshot_visible_discards_by_seat(state, attrs)
    current_total = 0
    snapshot_total = 0
    matched_prefix_total = 0
    is_append_only_extension = True

    for seat in range(SEAT_COUNT):
        current_tiles = [
            discard.tile_136
            for discard in current_round.discards.get(seat, [])
            if not discard.called
        ]
        snapshot_tiles = list(snapshot_discards.get(seat, []))
        current_total += len(current_tiles)
        snapshot_total += len(snapshot_tiles)

        seat_prefix_length = 0
        for current_tile, snapshot_tile in zip(current_tiles, snapshot_tiles):
            if current_tile != snapshot_tile:
                break
            seat_prefix_length += 1
        matched_prefix_total += seat_prefix_length

        if seat_prefix_length != len(current_tiles) or len(snapshot_tiles) < len(current_tiles):
            is_append_only_extension = False

    return SnapshotDiscardComparison(
        matched_prefix_discards=matched_prefix_total,
        current_total_visible_discards=current_total,
        snapshot_total_visible_discards=snapshot_total,
        is_append_only_extension=is_append_only_extension,
    )


def _snapshot_discard_match_ratio(
    state: GameState,
    current_round: RoundState,
    attrs: dict[str, Any],
) -> float | None:
    """Return the seat-wise prefix match ratio between current and snapshot discards."""

    comparison = _compare_snapshot_discards(state, current_round, attrs)
    if comparison is None:
        return None
    return comparison.match_ratio


def _snapshot_can_reuse_current_round(
    state: GameState,
    current_round: RoundState | None,
    attrs: dict[str, Any],
) -> bool:
    """Return whether a REINIT snapshot is close enough to reuse the current round."""

    if current_round is None:
        return False
    comparison = _compare_snapshot_discards(state, current_round, attrs)
    if comparison is None:
        return False

    # Exact prefix reuse is stronger than the coarse ratio heuristic. This keeps the current round
    # alive even early in a hand, where "same prefix + one extra discard" would otherwise score
    # below the threshold and incorrectly look like a round change.
    if comparison.is_append_only_extension:
        return True
    return comparison.match_ratio >= SNAPSHOT_ROUND_REUSE_MIN_DISCARD_MATCH_RATIO


def _reinit_requires_new_round(
    state: GameState,
    current_round: RoundState | None,
    attrs: dict[str, Any],
) -> bool:
    """Decide whether a REINIT snapshot belongs to a different round."""

    if current_round is None:
        return True

    seed = parse_csv_int_list(attrs.get("seed"))
    snapshot_kyoku = seed[0] if len(seed) >= 1 else None
    snapshot_honba = seed[1] if len(seed) >= 2 else None
    snapshot_oya = _safe_int(attrs.get("oya"))
    snapshot_key = (snapshot_kyoku, snapshot_honba, snapshot_oya)
    current_oya = current_round.oya_abs if _is_xml_log_source(state) else current_round.oya
    current_key = (current_round.kyoku_index, current_round.honba, current_oya)

    if any(value is not None for value in snapshot_key) and snapshot_key != current_key:
        return True
    if current_round.result is not None:
        return True
    if not _snapshot_can_reuse_current_round(state, current_round, attrs):
        return True
    return False


def _validate_tile_ids(tile_ids: Iterable[int], label: str) -> list[str]:
    """Validate that all tile ids are inside the canonical 0..135 range."""

    issues: list[str] = []
    for tile_id in tile_ids:
        if not 0 <= tile_id <= 135:
            issues.append(f"{label} contains out-of-range tile id: {tile_id}")
    return issues


def validate_round_state(round_state: RoundState) -> list[str]:
    """Return structural issues found in a round snapshot."""

    issues: list[str] = []
    issues.extend(_validate_tile_ids(round_state.dora_indicators_136, "dora_indicators_136"))
    issues.extend(_validate_tile_ids(round_state.initial_self_hand_136, "initial_self_hand_136"))
    if sorted(round_state.seat_order) != list(range(SEAT_COUNT)):
        issues.append(f"seat_order is invalid: {round_state.seat_order}")

    for seat in range(SEAT_COUNT):
        issues.extend(_validate_tile_ids(round_state.current_hands_136[seat], f"current_hands_136[{seat}]"))
        issues.extend(_validate_tile_ids(round_state.initial_hands_136[seat], f"initial_hands_136[{seat}]"))
        issues.extend(
            _validate_tile_ids(round_state.initial_hands_abs_136[seat], f"initial_hands_abs_136[{seat}]")
        )
        issues.extend(
            _validate_tile_ids(round_state.initial_hands_rel_136[seat], f"initial_hands_rel_136[{seat}]")
        )
        issues.extend(
            _validate_tile_ids(
                [discard.tile_136 for discard in round_state.discards[seat]],
                f"discards[{seat}]",
            )
        )
        for meld in round_state.melds[seat]:
            issues.extend(_validate_tile_ids(meld.tiles_136, f"meld[{seat}].tiles_136"))
            issues.extend(
                _validate_tile_ids(meld.consumed_tile_ids, f"meld[{seat}].consumed_tile_ids")
            )
            expected_shape = {
                "chi": (3, 2, True),
                "pon": (3, 2, True),
                "daiminkan": (4, 3, True),
                "ankan": (4, 4, False),
                "kakan": (4, 1, True),
            }.get(meld.meld_type)
            if expected_shape is None:
                issues.append(f"meld[{seat}] has unsupported meld_type={meld.meld_type}")
                continue
            tile_count, consumed_count, is_open = expected_shape
            if len(meld.tiles_136) != tile_count:
                issues.append(
                    f"meld[{seat}] {meld.meld_type} tile count mismatch: {len(meld.tiles_136)} != {tile_count}"
                )
            if len(meld.consumed_tile_ids) != consumed_count:
                issues.append(
                    f"meld[{seat}] {meld.meld_type} consumed count mismatch: "
                    f"{len(meld.consumed_tile_ids)} != {consumed_count}"
                )
            if meld.is_open != is_open:
                issues.append(
                    f"meld[{seat}] {meld.meld_type} openness mismatch: {meld.is_open} != {is_open}"
                )
    return issues


def verify_reinit_round_state(
    state: GameState,
    round_state: RoundState,
    attrs: dict[str, Any],
) -> list[str]:
    """Compare a rebuilt round snapshot against the source REINIT payload."""

    issues: list[str] = []
    hand_snapshot = _extract_hand_snapshot(attrs)
    for source_seat in range(SEAT_COUNT):
        storage_seat = _source_seat_to_storage_seat(state, source_seat)
        if (
            hand_snapshot.seat_hands[source_seat]
            and round_state.current_hands_136[storage_seat] != hand_snapshot.seat_hands[source_seat]
        ):
            issues.append(
                f"REINIT hand mismatch seat={storage_seat}: "
                f"{round_state.current_hands_136[storage_seat]} != {hand_snapshot.seat_hands[source_seat]}"
            )

        expected_raw_kawa = parse_csv_int_list(attrs.get(f"kawa{source_seat}"))
        if expected_raw_kawa and round_state.reinit_kawa_raw[storage_seat] != expected_raw_kawa:
            issues.append(
                f"REINIT kawa raw mismatch seat={storage_seat}: "
                f"{round_state.reinit_kawa_raw[storage_seat]} != {expected_raw_kawa}"
            )

        expected_visible_discards = [item for item in expected_raw_kawa if 0 <= item <= 135]
        actual_visible_discards = [discard.tile_136 for discard in round_state.discards[storage_seat]]
        if expected_raw_kawa and actual_visible_discards != expected_visible_discards:
            issues.append(
                f"REINIT visible discard mismatch seat={storage_seat}: "
                f"{actual_visible_discards} != {expected_visible_discards}"
            )

        expected_meld_codes = parse_csv_int_list(attrs.get(f"m{source_seat}"))
        actual_meld_codes = [meld.raw_m for meld in round_state.melds[storage_seat]]
        if expected_meld_codes and actual_meld_codes != expected_meld_codes:
            issues.append(
                f"REINIT meld mismatch seat={storage_seat}: {actual_meld_codes} != {expected_meld_codes}"
            )

    self_source_seat = LOCAL_RELATIVE_SEAT
    if _is_xml_log_source(state):
        if state.self_abs_seat is None:
            self_source_seat = -1
        else:
            self_source_seat = state.self_abs_seat

    if (
        hand_snapshot.has_self_hand
        and self_source_seat >= 0
        and not hand_snapshot.seat_hands.get(self_source_seat)
        and round_state.current_hands_136[LOCAL_RELATIVE_SEAT] != hand_snapshot.self_hand_136
    ):
        issues.append(
            f"REINIT self hand mismatch seat={LOCAL_RELATIVE_SEAT}: "
            f"{round_state.current_hands_136[LOCAL_RELATIVE_SEAT]} != {hand_snapshot.self_hand_136}"
        )

    return issues


def validate_game_state(game_state: GameState) -> list[str]:
    """Aggregate structural issues for every parsed round."""

    issues: list[str] = []
    for round_index, round_state in enumerate(game_state.rounds):
        for issue in validate_round_state(round_state):
            issues.append(f"round[{round_index}] {issue}")
    return issues


def _record_unknown(
    state: GameState,
    timestamp: Optional[float],
    raw_tag: str,
    reason: str,
    attrs: Optional[dict[str, Any]] = None,
) -> Event:
    """Store unsupported or failed payloads without crashing parsing."""

    payload = {
        "timestamp": timestamp,
        "raw_tag": raw_tag,
        "reason": reason,
    }
    if attrs:
        payload["attrs"] = _copy_attr_dict(attrs)
    state.unknown_tags.append(payload)
    state.diagnostics.append({"level": "warning", "code": "unknown_tag", **payload})
    logger.warning("Unknown tag: %s | reason=%s", raw_tag, reason)
    return state.add_event(timestamp, "unknown_tag", raw_tag=raw_tag, attrs=payload)


def _record_validation_issue(
    state: GameState,
    round_state: RoundState,
    message: str,
    *,
    timestamp: Optional[float] = None,
    raw_tag: str = "",
) -> None:
    """Record a round validation issue without downgrading it into an unknown tag."""

    round_state.validation_issues.append(message)
    payload = {
        "timestamp": timestamp,
        "raw_tag": raw_tag,
        "message": message,
        "round_index": state.rounds.index(round_state) if round_state in state.rounds else None,
    }
    state.diagnostics.append({"level": "warning", "code": "round_validation", **payload})
    state.prune_live_history()
    logger.warning("Round validation issue: %s", message)


def parse_un(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Apply UN player metadata onto the GameState."""

    attrs = parsed.attrs
    if _is_xml_log_source(state):
        _apply_player_metadata(state.players_abs, attrs)
        _maybe_resolve_xml_self_abs_seat(state)
    else:
        # Live capture keeps relative seats only. A later UN after browser reload must not erase a
        # freshly reconstructed snapshot when the previous signature was still empty/unknown.
        previous_signature = _relative_player_signature(state)
        next_signature, has_name_payload = _merged_relative_player_signature_from_un(state, attrs)
        if (
            has_name_payload
            and _signature_has_known_names(previous_signature)
            and _signature_has_known_names(next_signature)
            and next_signature != previous_signature
        ):
            _reset_live_hanchan_state(
                state,
                reason="UN relative-seat player signature changed",
                preserve_player_metadata=False,
                previous_signature=previous_signature,
                next_signature=next_signature,
            )
        _apply_player_metadata(state.players_rel, attrs)
        state.players_abs = {
            seat: _clone_player_info(player, seat=seat)
            for seat, player in state.players_rel.items()
        }
        state.seat_mapping_resolved = True
        state.refresh_player_views()
    return state.add_event(timestamp, "un", raw_tag=parsed.raw_tag, attrs=_copy_attr_dict(attrs))


def parse_init(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Create a new round snapshot from INIT using the active seat view."""

    round_state = _start_round_from_init(state, parsed.attrs)
    _mark_round_snapshot_bootstrap(state, round_state)
    _clear_pending_response_discard(round_state)
    hand_snapshot = _extract_hand_snapshot(parsed.attrs)
    _apply_init_hand_snapshot(state, round_state, hand_snapshot)
    _apply_snapshot_meld_payload(
        state,
        round_state,
        parsed.attrs,
        timestamp=timestamp,
        raw_tag=parsed.raw_tag,
        clear_existing=False,
    )
    _apply_snapshot_kawa_payload(
        state,
        round_state,
        parsed.attrs,
        previous_discards=None,
        clear_existing=False,
    )
    _rebuild_tracker_from_round(state)
    for melds in round_state.melds.values():
        for meld in melds:
            _mark_called_discard(state, round_state, meld)
    _sync_live_state(state)
    event_attrs = _copy_attrs_with_mapped_seats(state, parsed.attrs, "oya")
    event_attrs = _remap_seat_keyed_attrs(state, event_attrs, "hai")
    return state.add_event(
        timestamp,
        "init",
        raw_tag=parsed.raw_tag,
        attrs=event_attrs,
    )


def parse_reinit(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Reconstruct the current round from a REINIT snapshot using the active seat view."""

    round_state = _prepare_round_for_reinit(state, parsed.attrs)
    _mark_round_snapshot_bootstrap(state, round_state)
    previous_discards = _capture_discard_metadata_seed(round_state)
    _clear_pending_response_discard(round_state)
    _reset_round_runtime_snapshot(round_state)
    round_state.raw_reinit_attrs = _copy_attr_dict(parsed.attrs)
    hand_snapshot = _extract_hand_snapshot(parsed.attrs)
    _apply_reinit_hand_snapshot(state, round_state, hand_snapshot)
    _apply_snapshot_meld_payload(
        state,
        round_state,
        parsed.attrs,
        timestamp=timestamp,
        raw_tag=parsed.raw_tag,
        clear_existing=False,
    )
    _apply_snapshot_kawa_payload(
        state,
        round_state,
        parsed.attrs,
        previous_discards=previous_discards,
        clear_existing=False,
    )
    # REINIT overwrites runtime state, so restore riichi acceptance from the rebuilt snapshot
    # before the danger logic and tracker consumers read this round again.
    _restore_reach_state_from_snapshot_discards(round_state)

    # When the REINIT river is just the current river plus a few appended tiles, the discard
    # objects for the shared prefix keep their old lag/thinking metadata via the carry-over path,
    # while the snapshot-only tail is added as fresh state for subsequent live packets to extend.
    _rebuild_tracker_from_round(state)
    for melds in round_state.melds.values():
        for meld in melds:
            _mark_called_discard(state, round_state, meld)

    for issue in verify_reinit_round_state(state, round_state, parsed.attrs):
        _record_validation_issue(
            state,
            round_state,
            issue,
            timestamp=timestamp,
            raw_tag=parsed.raw_tag,
        )
    for issue in validate_round_state(round_state):
        _record_validation_issue(
            state,
            round_state,
            issue,
            timestamp=timestamp,
            raw_tag=parsed.raw_tag,
        )

    _sync_live_state(state)
    event_attrs = _copy_attrs_with_mapped_seats(state, parsed.attrs, "oya")
    event_attrs = _remap_seat_keyed_attrs(state, event_attrs, "hai", "kawa", "m")
    return state.add_event(
        timestamp,
        "reinit",
        raw_tag=parsed.raw_tag,
        attrs=event_attrs,
    )


def parse_draw(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Parse T/U/V/W draw tags into the active seat view."""

    match = DRAW_TAG_NAME_PATTERN.fullmatch(parsed.tag_name)
    if not match:
        return _record_unknown(state, timestamp, parsed.raw_tag, "Invalid draw tag", parsed.attrs)

    source_seat = DRAW_SEAT_MAP[match.group(1).upper()]
    seat = _source_seat_to_storage_seat(state, source_seat)
    tile_136 = _safe_int(match.group(2))
    round_state = state.ensure_round()
    _resolve_pending_response_discard(state, round_state, timestamp, resolved_by_call=False)
    if tile_136 is not None:
        round_state.draws[seat].append(tile_136)
        round_state.current_hands_136[seat].append(tile_136)
    round_state.last_draw_tiles_136[seat] = tile_136
    _set_discard_thinking_start(round_state, seat, timestamp, "draw")
    _sync_live_state(state)
    return state.add_event(
        timestamp,
        "draw",
        seat=seat,
        tile_136=tile_136,
        raw_tag=parsed.raw_tag,
        attrs=_copy_attr_dict(parsed.attrs),
    )


def _classify_tsumogiri(round_state: RoundState, seat: int, tile_136: int, tag_name: str) -> tuple[bool, bool]:
    """Classify discard style as `(tsumogiri, is_estimated)`.

    Confirmed rules:
    - if the previous draw for the same seat matches the discard tile, tsumogiri is confirmed.
    - if the previous draw does not match, uppercase discard tags are treated as confirmed tedashi.

    Provisional rule:
    - lowercase discard tags are treated as tsumogiri estimates only when the confirmed rule above
      could not already determine tsumogiri.
    """

    last_draw = round_state.last_draw_tiles_136.get(seat)
    if last_draw is not None and last_draw == tile_136:
        return True, False
    if tag_name and tag_name[0].islower():
        return True, True
    return False, False


def _build_discard_event_attrs(
    parsed_attrs: dict[str, Any],
    discard: Discard,
    *,
    delay_confidence: str,
    delay_ms: Optional[int] = None,
    delay_source: Optional[str] = None,
    extra_attrs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the event attrs shared by confirmed and provisional discard paths."""

    event_attrs = {
        **_copy_attr_dict(parsed_attrs),
        "tsumogiri": discard.tsumogiri,
        "is_tsumogiri_estimated": discard.is_tsumogiri_estimated,
        "tsumogiri_flag": discard.tsumogiri_flag,
        "riichi_marker_before": discard.riichi_marker_before,
        "concealed_tile_count_before_discard": len(discard.hand_tiles_before_discard_136),
        "delay_confidence": delay_confidence,
        "lagged": LAG_FLAG_UNKNOWN,
        "round_discard_index": discard.round_discard_index,
    }
    if delay_ms is not None:
        event_attrs["action_delay_ms"] = delay_ms
    if delay_source is not None:
        event_attrs["delay_source"] = delay_source
    if discard.thinking_time_ms is not None:
        event_attrs["thinking_time_ms"] = discard.thinking_time_ms
    if discard.thinking_time_source is not None:
        event_attrs["thinking_time_source"] = discard.thinking_time_source
    if discard.thinking_time_before_reach_ms is not None:
        event_attrs["thinking_time_before_reach_ms"] = discard.thinking_time_before_reach_ms
    if discard.thinking_time_before_reach_source is not None:
        event_attrs["thinking_time_before_reach_source"] = (
            discard.thinking_time_before_reach_source
        )
    if extra_attrs:
        event_attrs.update(extra_attrs)
    return event_attrs


def _confirm_client_discard_request(
    state: GameState,
    round_state: RoundState,
    timestamp: Optional[float],
    parsed: ParsedTag,
    *,
    seat: int,
    tile_136: int,
    delay_ms: Optional[int],
    delay_source: Optional[str],
    delay_confidence: str,
) -> Event:
    """Merge a server discard tag into the provisional self discard created from a client packet."""

    discard = _latest_matching_client_discard_request(round_state, seat, tile_136)
    if discard is None:
        raise RuntimeError("missing client discard request to confirm")
    discard.raw_tag = parsed.raw_tag
    event_attrs = _build_discard_event_attrs(
        parsed.attrs,
        discard,
        delay_ms=delay_ms,
        delay_source=delay_source,
        delay_confidence=delay_confidence,
        extra_attrs={"confirmed_client_discard_request": True},
    )
    _sync_live_state(state)
    event = state.add_event(
        timestamp,
        "discard",
        seat=seat,
        tile_136=tile_136,
        raw_tag=parsed.raw_tag,
        attrs=event_attrs,
        action_delay_ms=delay_ms,
        delay_source=delay_source,
        delay_confidence=delay_confidence,
        thinking_time_ms=discard.thinking_time_ms,
        thinking_time_source=discard.thinking_time_source,
        thinking_time_before_reach_ms=discard.thinking_time_before_reach_ms,
        thinking_time_before_reach_source=discard.thinking_time_before_reach_source,
    )
    discard.event_index = len(state.events) - 1
    _update_latest_tracker_discard_from_capture_discard(
        state,
        seat,
        discard,
        timestamp=timestamp,
    )
    return event


def parse_client_discard_request(
    state: GameState,
    timestamp: Optional[float],
    parsed: ParsedTag,
) -> Event:
    """Handle client-origin discard send packets without waiting for the server echo."""

    tag_name = parsed.normalized_tag
    source_seat = DISCARD_SEAT_MAP.get(tag_name, LOCAL_RELATIVE_SEAT)
    seat = _source_seat_to_storage_seat(state, source_seat)
    tile_136 = _safe_int(parsed.attrs.get("p"))
    event_attrs = {
        **_copy_attr_dict(parsed.attrs),
        "client_discard_request": True,
    }
    if tile_136 is None:
        return state.add_event(
            timestamp,
            "client_discard_request",
            seat=seat,
            raw_tag=parsed.raw_tag,
            attrs=event_attrs,
            mark_live_update=False,
        )

    round_state = state.current_round
    if (
        round_state is None
        or seat != LOCAL_RELATIVE_SEAT
        or tile_136 not in round_state.current_hands_136.get(seat, [])
        or _latest_matching_client_discard_request(round_state, seat, tile_136) is not None
    ):
        return state.add_event(
            timestamp,
            "client_discard_request",
            seat=seat,
            tile_136=tile_136,
            raw_tag=parsed.raw_tag,
            attrs={**event_attrs, "optimistic_discard_applied": False},
            mark_live_update=False,
        )

    tsumogiri, is_tsumogiri_estimated = _classify_tsumogiri(
        round_state,
        seat,
        tile_136,
        parsed.tag_name,
    )
    (
        thinking_time_ms,
        thinking_time_source,
        thinking_time_before_reach_ms,
        thinking_time_before_reach_source,
    ) = _consume_discard_thinking_start(round_state, seat, timestamp)
    riichi_marker_before = round_state.pending_riichi_markers[seat]
    round_state.pending_riichi_markers[seat] = False
    pre_discard_hand_tiles_136 = list(round_state.current_hands_136.get(seat, []))
    pre_self_hand_tiles_136 = list(round_state.current_hands_136.get(LOCAL_RELATIVE_SEAT, []))

    discard = Discard(
        tile_136=tile_136,
        hand_tiles_before_discard_136=pre_discard_hand_tiles_136,
        self_hand_tiles_before_discard_136=pre_self_hand_tiles_136,
        tsumogiri=tsumogiri,
        is_tsumogiri_estimated=is_tsumogiri_estimated,
        riichi_marker_before=riichi_marker_before,
        raw_tag=f"{CLIENT_DISCARD_REQUEST_RAW_TAG_PREFIX}{parsed.raw_tag}",
        thinking_time_ms=thinking_time_ms,
        thinking_time_source=thinking_time_source,
        thinking_time_before_reach_ms=thinking_time_before_reach_ms,
        thinking_time_before_reach_source=thinking_time_before_reach_source,
    )
    round_state.discards[seat].append(discard)
    discard.round_discard_index = sum(len(discards) for discards in round_state.discards.values()) - 1
    _remove_tile_from_hand(round_state.current_hands_136[seat], tile_136)
    round_state.last_draw_tiles_136[seat] = None

    tile_37 = tile136_to_tile37(tile_136)
    tracker_discard = None
    if tile_37 is not None:
        tracker_discard = state.tracker.add_discard(
            Player(seat),
            tile_37,
            tsumogiri=tsumogiri,
            tag=discard.raw_tag,
            timestamp=timestamp,
            riichi_marker_before=riichi_marker_before,
        )
        tracker_discard.thinking_time_ms = thinking_time_ms
        tracker_discard.thinking_time_source = thinking_time_source
        tracker_discard.thinking_time_before_reach_ms = thinking_time_before_reach_ms
        tracker_discard.thinking_time_before_reach_source = thinking_time_before_reach_source
        tracker_discard.self_hand_tiles_before_discard_136 = list(pre_self_hand_tiles_136)
        tracker_discard.round_discard_index = discard.round_discard_index
    _begin_pending_response_discard(round_state, seat, timestamp)
    _sync_live_state(state)
    event = state.add_event(
        timestamp,
        "discard",
        seat=seat,
        tile_136=tile_136,
        raw_tag=parsed.raw_tag,
        attrs=_build_discard_event_attrs(
            parsed.attrs,
            discard,
            delay_confidence="unknown",
            extra_attrs={
                **event_attrs,
                "optimistic_discard_applied": True,
                "discard_event_source": "client_request",
            },
        ),
        thinking_time_ms=thinking_time_ms,
        thinking_time_source=thinking_time_source,
        thinking_time_before_reach_ms=thinking_time_before_reach_ms,
        thinking_time_before_reach_source=thinking_time_before_reach_source,
    )
    discard.event_index = len(state.events) - 1
    if tracker_discard is not None:
        tracker_discard.event_index = discard.event_index
    return event


def parse_discard(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Parse D/E/F/G discard tags into the active seat view."""

    match = DISCARD_TAG_NAME_PATTERN.fullmatch(parsed.tag_name)
    if not match:
        return _record_unknown(state, timestamp, parsed.raw_tag, "Invalid discard tag", parsed.attrs)

    delay_prefix = match.group(1)
    delay_ms, delay_source, delay_confidence = _extract_discard_delay_metadata(state, delay_prefix)
    source_seat = DISCARD_SEAT_MAP[match.group(2).upper()]
    seat = _source_seat_to_storage_seat(state, source_seat)
    tile_136 = int(match.group(3))
    round_state = state.ensure_round()
    if _latest_matching_client_discard_request(round_state, seat, tile_136) is not None:
        return _confirm_client_discard_request(
            state,
            round_state,
            timestamp,
            parsed,
            seat=seat,
            tile_136=tile_136,
            delay_ms=delay_ms,
            delay_source=delay_source,
            delay_confidence=delay_confidence,
        )
    _resolve_pending_response_discard_on_next_discard(state, round_state, timestamp)
    tsumogiri, is_tsumogiri_estimated = _classify_tsumogiri(round_state, seat, tile_136, parsed.tag_name)
    (
        thinking_time_ms,
        thinking_time_source,
        thinking_time_before_reach_ms,
        thinking_time_before_reach_source,
    ) = _consume_discard_thinking_start(
        round_state,
        seat,
        timestamp,
    )
    riichi_marker_before = round_state.pending_riichi_markers[seat]
    round_state.pending_riichi_markers[seat] = False
    # Capture the discarding player's concealed hand before mutating runtime hand state.
    pre_discard_hand_tiles_136 = list(round_state.current_hands_136.get(seat, []))
    pre_self_hand_tiles_136 = list(round_state.current_hands_136.get(LOCAL_RELATIVE_SEAT, []))

    discard = Discard(
        tile_136=tile_136,
        hand_tiles_before_discard_136=pre_discard_hand_tiles_136,
        self_hand_tiles_before_discard_136=pre_self_hand_tiles_136,
        tsumogiri=tsumogiri,
        is_tsumogiri_estimated=is_tsumogiri_estimated,
        riichi_marker_before=riichi_marker_before,
        raw_tag=parsed.raw_tag,
        thinking_time_ms=thinking_time_ms,
        thinking_time_source=thinking_time_source,
        thinking_time_before_reach_ms=thinking_time_before_reach_ms,
        thinking_time_before_reach_source=thinking_time_before_reach_source,
    )
    round_state.discards[seat].append(discard)
    discard.round_discard_index = sum(len(discards) for discards in round_state.discards.values()) - 1
    _remove_tile_from_hand(round_state.current_hands_136[seat], tile_136)
    round_state.last_draw_tiles_136[seat] = None

    tile_37 = tile136_to_tile37(tile_136)
    tracker_discard = None
    if tile_37 is not None:
        tracker_discard = state.tracker.add_discard(
            Player(seat),
            tile_37,
            tsumogiri=tsumogiri,
            tag=parsed.raw_tag,
            timestamp=timestamp,
            riichi_marker_before=riichi_marker_before,
        )
        tracker_discard.riichi_marker_before = riichi_marker_before
        tracker_discard.thinking_time_ms = thinking_time_ms
        tracker_discard.thinking_time_source = thinking_time_source
        tracker_discard.thinking_time_before_reach_ms = thinking_time_before_reach_ms
        tracker_discard.thinking_time_before_reach_source = thinking_time_before_reach_source
        tracker_discard.self_hand_tiles_before_discard_136 = list(pre_self_hand_tiles_136)
        # Keep live tracker ordering aligned with round-state discards for renderer sorting.
        tracker_discard.round_discard_index = discard.round_discard_index
    _begin_pending_response_discard(round_state, seat, timestamp)

    _sync_live_state(state)
    event_attrs = _build_discard_event_attrs(
        parsed.attrs,
        discard,
        delay_ms=delay_ms,
        delay_source=delay_source,
        delay_confidence=delay_confidence,
    )
    event = state.add_event(
        timestamp,
        "discard",
        seat=seat,
        tile_136=tile_136,
        raw_tag=parsed.raw_tag,
        attrs=event_attrs,
        action_delay_ms=delay_ms,
        delay_source=delay_source,
        delay_confidence=delay_confidence,
        thinking_time_ms=thinking_time_ms,
        thinking_time_source=thinking_time_source,
        thinking_time_before_reach_ms=thinking_time_before_reach_ms,
        thinking_time_before_reach_source=thinking_time_before_reach_source,
    )
    discard.event_index = len(state.events) - 1
    if tracker_discard is not None:
        # Renderer-side awaseuchi and marker logic may sort tracker discards by event order.
        tracker_discard.event_index = discard.event_index
    return event


def parse_n(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Parse N meld events and update the meld state."""

    attrs = parsed.attrs
    seat_abs = _safe_int(attrs.get("who"))
    seat = _source_seat_to_storage_seat(state, seat_abs) if seat_abs is not None else None
    meld_code = _safe_int(attrs.get("m"))
    if seat is None or meld_code is None:
        return state.add_event(
            timestamp,
            "call_request",
            seat=seat,
            raw_tag=parsed.raw_tag,
            attrs=_copy_attrs_with_mapped_seats(state, attrs, "who"),
        )

    round_state = state.ensure_round()
    try:
        meld = decode_meld(seat, meld_code)
    except ValueError as exc:
        return _record_unknown(state, timestamp, parsed.raw_tag, f"Failed to decode meld: {exc}", attrs)

    meld.event_index = len(state.events)
    _assign_meld_id(meld, f"meld-{meld.event_index}")
    _upsert_meld(round_state, meld)

    for tile_136 in meld.consumed_tile_ids:
        _remove_tile_from_hand(round_state.current_hands_136[seat], tile_136)
    # After any meld declaration there is no longer an active "draw tile" at the hand edge.
    # Leaving the previous draw marker in place makes the UI show one extra tile after chi/pon/kan.
    round_state.last_draw_tiles_136[seat] = None

    _resolve_pending_response_discard_for_meld(state, round_state, timestamp, meld)
    _mark_called_discard(state, round_state, meld)
    _set_discard_thinking_start(round_state, seat, timestamp, "call")
    _sync_live_state(state)
    meld_info = {
        **_copy_attrs_with_mapped_seats(state, attrs, "who"),
        **asdict(meld),
    }
    return state.add_event(
        timestamp,
        "call",
        seat=seat,
        tile_136=meld.called_tile_id,
        raw_tag=parsed.raw_tag,
        attrs=meld_info,
    )


def parse_reach(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Parse REACH step 1 / 2 and update the round reach state."""

    round_state = state.ensure_round()
    seat_abs = _safe_int(parsed.attrs.get("who"))
    seat = _source_seat_to_storage_seat(state, seat_abs) if seat_abs is not None else None
    step = _safe_int(parsed.attrs.get("step"))
    event_type = "reach"

    if seat is not None and 0 <= seat <= 3:
        if step == 1:
            round_state.reach_state[seat] = "declared"
            round_state.pending_riichi_markers[seat] = True
            _split_discard_thinking_at_reach(round_state, seat, timestamp)
            event_type = "reach_declared"
        elif step == 2:
            round_state.reach_state[seat] = "accepted"
            event_type = "reach_accepted"
        ten = parse_csv_int_list(parsed.attrs.get("ten"))
        if len(ten) >= SEAT_COUNT:
            round_state.scores = _normalize_ten_scores_for_state(state, ten)

    return state.add_event(
        timestamp,
        event_type,
        seat=seat,
        raw_tag=parsed.raw_tag,
        attrs=_copy_attrs_with_mapped_seats(state, parsed.attrs, "who"),
    )


def parse_dora(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Parse DORA indicator reveals."""

    round_state = state.ensure_round()
    tile_136 = _safe_int(parsed.attrs.get("hai"))
    if tile_136 is not None and tile_136 not in round_state.dora_indicators_136:
        round_state.dora_indicators_136.append(tile_136)
    _sync_live_state(state)
    return state.add_event(
        timestamp,
        "dora",
        tile_136=tile_136,
        raw_tag=parsed.raw_tag,
        attrs=_copy_attr_dict(parsed.attrs),
    )


def parse_agari(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Store AGARI as the current round result snapshot."""

    round_state = state.ensure_round()
    who_abs = _safe_int(parsed.attrs.get("who"))
    from_who_abs = _safe_int(parsed.attrs.get("fromWho"))
    who = _source_seat_to_storage_seat(state, who_abs) if who_abs is not None else None
    from_who = _source_seat_to_storage_seat(state, from_who_abs) if from_who_abs is not None else None
    result = {
        **_copy_attrs_with_mapped_seats(state, parsed.attrs, "who", "fromWho"),
        "who": who,
        "fromWho": from_who,
        "is_tsumo": who is not None and who == from_who,
    }
    round_state.result = {"type": "agari", "data": result}
    _clear_pending_response_discard(round_state)
    return state.add_event(
        timestamp,
        "agari",
        seat=result["who"],
        raw_tag=parsed.raw_tag,
        attrs=result,
    )


def parse_ryuukyoku(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Store RYUUKYOKU as the current round result snapshot."""

    round_state = state.ensure_round()
    result = {
        **_remap_seat_keyed_attrs(state, parsed.attrs, "hai"),
        "type": str(parsed.attrs.get("type", "")) or None,
    }
    round_state.result = {"type": "ryuukyoku", "data": result}
    _clear_pending_response_discard(round_state)
    return state.add_event(
        timestamp,
        "ryuukyoku",
        raw_tag=parsed.raw_tag,
        attrs=result,
    )


def parse_spectator_init(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Accept spectator bootstrap/control tags as part of the normal live path."""

    _promote_parser_mode(
        state,
        PARSER_MODE_SPECTATOR_LIVE,
        reason=f"Observed spectator bootstrap tag {parsed.normalized_tag}",
    )

    attrs = _copy_attr_dict(parsed.attrs)
    game_id = attrs.get("log") or attrs.get("id")
    if game_id:
        state.game_id = str(game_id)

    should_touch_round = state.current_round is None or any(
        key in attrs for key in ("seed", "ten", "oya", "hai", "hai0", "hai1", "hai2", "hai3")
    ) or _has_seat_payload(attrs, "m") or _has_seat_payload(attrs, "kawa")
    if should_touch_round:
        # INIT-like spectator snapshots should always start fresh. Only REINIT is allowed to
        # compare against the current round and reuse lag / thinking metadata.
        state.begin_round(started_from_init_like=True)
        round_state = state.ensure_round()
        round_state.started_from_init_like = True
        _mark_round_snapshot_bootstrap(state, round_state)
        previous_discards = None
        _clear_pending_response_discard(round_state)
        if any(key in attrs for key in ("seed", "ten", "oya")):
            _apply_round_header(
                state,
                round_state,
                attrs,
                reset_dora=parsed.normalized_tag == "INITBYLOG",
            )
        if "hai" in attrs or _has_seat_payload(attrs, "hai"):
            _apply_reinit_hand_snapshot(state, round_state, _extract_hand_snapshot(attrs))
        _apply_snapshot_meld_payload(
            state,
            round_state,
            attrs,
            timestamp=timestamp,
            raw_tag=parsed.raw_tag,
            clear_existing=True,
        )
        _apply_snapshot_kawa_payload(
            state,
            round_state,
            attrs,
            previous_discards=previous_discards,
            clear_existing=True,
        )
        if _has_seat_payload(attrs, "m") or _has_seat_payload(attrs, "kawa"):
            _rebuild_tracker_from_round(state)
            for melds in round_state.melds.values():
                for meld in melds:
                    _mark_called_discard(state, round_state, meld)
        _sync_round_identity(state, round_state, preserve_existing=parsed.normalized_tag != "INITBYLOG")
        _sync_live_state(state)

    return state.add_event(
        timestamp,
        parsed.normalized_tag.lower(),
        raw_tag=parsed.raw_tag,
        attrs=attrs,
    )


def _parse_simple_event(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Store control tags that do not directly mutate the round snapshot."""

    event_type = parsed.normalized_tag.lower()
    if parsed.normalized_tag == "GO":
        go_type = parse_tenhou_game_type(parsed.attrs.get("type"))
        state.go_type = go_type
        state.room_class_code = tenhou_room_class_code(go_type)
        state.room_class_label = tenhou_room_class_label(go_type)
    if parsed.normalized_tag == "TAIKYOKU":
        # `TAIKYOKU.log` is the authoritative game id, but it can arrive after a reload-time
        # snapshot (`REINIT` / `INITBYLOG`). Preserve that snapshot and just rewrite identities.
        game_id = parsed.attrs.get("log")
        if game_id:
            normalized_game_id = str(game_id)
            if state.game_id and state.game_id != normalized_game_id:
                has_snapshot_round = (
                    state.current_round is not None
                    and state.current_round.started_from_init_like
                    and (
                        any(state.current_round.discards.values())
                        or any(state.current_round.current_hands_136.values())
                        or any(state.current_round.melds.values())
                    )
                )
                if has_snapshot_round:
                    _rebind_live_game_id(
                        state,
                        normalized_game_id,
                        reason="TAIKYOKU game_id arrived after reload snapshot",
                    )
                else:
                    _reset_live_hanchan_state(
                        state,
                        reason="TAIKYOKU game_id changed",
                        preserve_player_metadata=True,
                        previous_signature=_relative_player_signature(state),
                        next_signature=_relative_player_signature(state),
                        next_game_id=normalized_game_id,
                    )
            state.game_id = normalized_game_id
            game_id = normalized_game_id
            for round_state in state.rounds:
                if round_state.round_key is None or round_state.round_key[0] == "unknown":
                    round_state.round_key = build_round_key(
                        state.game_id,
                        round_state.kyoku_index,
                        round_state.honba,
                        round_state.kyotaku,
                        _round_identity_oya_value(state, round_state),
                    )
                    round_state.round_id = build_round_id(
                        state.game_id,
                        round_state.kyoku_index,
                        round_state.honba,
                        round_state.kyotaku,
                        _round_identity_oya_value(state, round_state),
                    )
            state.sync_current_round_context()
    return state.add_event(
        timestamp,
        event_type,
        raw_tag=parsed.raw_tag,
        attrs=_copy_attr_dict(parsed.attrs),
    )


def _parse_chat_like_tag(state: GameState, timestamp: Optional[float], parsed: ParsedTag) -> Event:
    """Store chat-like messages without treating them as unknowns."""

    payload = {
        "timestamp": timestamp,
        "tag": parsed.tag_name,
        "attrs": _copy_attr_dict(parsed.attrs),
        "raw_tag": parsed.raw_tag,
    }
    state.chats.append(payload)
    return state.add_event(timestamp, "chat_like", raw_tag=parsed.raw_tag, attrs=payload)


def parse_fragment(state: CaptureState, timestamp: Optional[float], fragment: str) -> Event | None:
    """Parse and apply a single tag fragment onto the mutable GameState."""

    raw_fragment = fragment.strip()
    if not raw_fragment:
        return None

    try:
        parsed = parse_tag_fragment(raw_fragment)
    except Exception as exc:  # noqa: BLE001 - unknown payloads must never kill capture.
        return _record_unknown(state, timestamp, raw_fragment, f"Failed to parse tag fragment: {exc}")

    tag_name = parsed.normalized_tag
    if not tag_name:
        return None

    # First handle server-style draw/discard names before generic simple tags.
    if DRAW_TAG_NAME_PATTERN.fullmatch(parsed.tag_name):
        return parse_draw(state, timestamp, parsed)
    if DISCARD_TAG_NAME_PATTERN.fullmatch(parsed.tag_name):
        return parse_discard(state, timestamp, parsed)

    if tag_name == "UN":
        return parse_un(state, timestamp, parsed)
    if tag_name in SPECTATOR_INIT_TAGS:
        return parse_spectator_init(state, timestamp, parsed)
    if tag_name == "INIT":
        return parse_init(state, timestamp, parsed)
    if tag_name == "REINIT":
        return parse_reinit(state, timestamp, parsed)
    if tag_name == "N":
        return parse_n(state, timestamp, parsed)
    if tag_name == "REACH":
        return parse_reach(state, timestamp, parsed)
    if tag_name == "DORA":
        return parse_dora(state, timestamp, parsed)
    if tag_name == "AGARI":
        return parse_agari(state, timestamp, parsed)
    if tag_name == "RYUUKYOKU":
        return parse_ryuukyoku(state, timestamp, parsed)
    if tag_name in {"LN", "REJOIN"}:
        return _record_unknown(
            state,
            timestamp,
            parsed.raw_tag,
            f"TODO unresolved tag semantics: {tag_name}",
            parsed.attrs,
        )

    if tag_name in {"CHAT", "SAY", "CHATMESSAGE"}:
        return _parse_chat_like_tag(state, timestamp, parsed)
    if tag_name in SIMPLE_EVENT_TAGS:
        return _parse_simple_event(state, timestamp, parsed)

    # Client-originated command packets show up in decrypted CSV captures as plain JSON objects.
    if tag_name in {"D", "E", "F", "G"} and "p" in parsed.attrs:
        return parse_client_discard_request(state, timestamp, parsed)

    return _record_unknown(state, timestamp, parsed.raw_tag, "Unsupported tag", parsed.attrs)


def extract_xml_log_fragments(text: str) -> list[str]:
    """Extract ordered child tags from a Tenhou XML mjlog document."""

    stripped = text.strip()
    if not stripped:
        return []

    try:
        root = et.fromstring(stripped)
    except et.ParseError:
        return [
            fragment
            for fragment in extract_tag_fragments(stripped)
            if fragment.strip() and not fragment.strip().startswith("</")
        ]

    children = list(root)
    if children:
        return [et.tostring(child, encoding="unicode") for child in children]
    return [et.tostring(root, encoding="unicode")]


def _build_xml_game_state(
    *,
    self_abs_seat: Optional[int] = None,
    self_player_name: Optional[str] = None,
) -> GameState:
    """Create a GameState configured for offline XML mjlog parsing."""

    normalized_self_player_name = _normalize_player_name_for_matching(self_player_name)
    state = GameState(
        parser_mode=PARSER_MODE_XML,
        seat_mapping_resolved=self_abs_seat is not None,
        self_abs_seat=self_abs_seat,
        self_player_name=normalized_self_player_name,
    )
    if self_abs_seat is not None:
        _set_xml_self_abs_seat(state, self_abs_seat)
    return state


def _preload_xml_un_context(state: GameState, fragment_records: list[tuple[Optional[float], str]]) -> None:
    """Read UN before event parsing so XML seat mapping can be resolved up front."""

    for _timestamp, fragment in fragment_records:
        parsed = parse_tag_fragment(fragment)
        if parsed.normalized_tag != "UN":
            continue
        _apply_player_metadata(state.players_abs, parsed.attrs)
        _maybe_resolve_xml_self_abs_seat(state)
        return

    if state.self_abs_seat is not None:
        _set_xml_self_abs_seat(state, state.self_abs_seat)


def _finalize_loaded_state(state: GameState) -> GameState:
    """Run final validation and pending-seat diagnostics after a bulk load."""

    for round_state in state.rounds:
        for issue in validate_round_state(round_state):
            if issue in round_state.validation_issues:
                continue
            _record_validation_issue(state, round_state, issue)

    if _is_xml_log_source(state) and not state.seat_mapping_resolved:
        state.diagnostics.append(
            {
                "level": "warning",
                "code": "seat_mapping_pending",
                "message": (
                    "XML seat mapping is unresolved; seat-keyed state is being held in absolute seat order "
                    "until resolve_seat_mapping() is called."
                ),
            }
        )
    return state


def _load_from_xml_fragment_records(
    fragment_records: list[tuple[Optional[float], str]],
    *,
    self_abs_seat: Optional[int] = None,
    self_player_name: Optional[str] = None,
) -> GameState:
    """Load offline XML fragments into GameState with UN-based seat preprocessing."""

    state = _build_xml_game_state(
        self_abs_seat=self_abs_seat,
        self_player_name=self_player_name,
    )
    state.source_fragments = list(fragment_records)
    _preload_xml_un_context(state, fragment_records)

    for timestamp, fragment in fragment_records:
        parse_fragment(state, timestamp, fragment)

    return _finalize_loaded_state(state)


def _looks_like_decrypted_csv(lines: list[str]) -> bool:
    """Detect the provided decrypted CSV export format."""

    if not lines:
        return False
    header = lines[0].strip()
    return "payload_text_url_decoded" in header and "approx_time_epoch" in header


def _load_from_csv_rows(lines: list[str], state: GameState) -> GameState:
    """Load the provided decrypted CSV export into a GameState."""

    reader = csv.DictReader(lines)
    rows = list(reader)
    has_server_rows = any((row.get("direction") or "").lower() == "s2c" for row in rows)

    for row in rows:
        direction = (row.get("direction") or "").lower()
        if has_server_rows and direction and direction != "s2c":
            # Server-to-client packets are the authoritative game-state source.
            continue

        timestamp: Optional[float] = None
        approx_time = row.get("approx_time_epoch")
        if approx_time not in (None, ""):
            try:
                timestamp = float(approx_time)
            except ValueError:
                timestamp = None

        payload = (
            row.get("payload_text_url_decoded")
            or row.get("payload_text")
            or row.get("tag")
            or ""
        ).strip()
        if not payload:
            continue

        for fragment in extract_tag_fragments(payload):
            parse_fragment(state, timestamp, fragment)

    return state


def load_from_decrypted_lines(
    lines: Iterable[str],
    *,
    parser_mode: Literal["player_live", "spectator_live", "xml_log"] = PARSER_MODE_PLAYER_LIVE,
) -> GameState:
    """Load decrypted websocket lines into a fully built GameState."""

    buffered_lines = list(lines)
    state = GameState(parser_mode=parser_mode)

    if _looks_like_decrypted_csv(buffered_lines):
        return _finalize_loaded_state(_load_from_csv_rows(buffered_lines, state))

    for line in buffered_lines:
        timestamp, payload = split_tshark_line(line)
        if timestamp is not None and payload:
            for fragment in extract_tag_fragments(payload):
                parse_fragment(state, timestamp, fragment)
            continue

        raw_line = line.strip()
        if not raw_line:
            continue
        for fragment in extract_tag_fragments(raw_line):
            parse_fragment(state, None, fragment)

    return _finalize_loaded_state(state)


def load_from_text(
    text: str,
    *,
    parser_mode: Literal["player_live", "spectator_live", "xml_log"] = PARSER_MODE_PLAYER_LIVE,
) -> GameState:
    """Load decrypted websocket payloads from a single text blob."""

    return load_from_decrypted_lines(text.splitlines(), parser_mode=parser_mode)


def load_from_xml_text(
    text: str,
    self_abs_seat: Optional[int] = None,
    self_player_name: Optional[str] = None,
) -> GameState:
    """Load an offline Tenhou XML mjlog using UN-driven absolute-seat preprocessing."""

    fragment_records = [(None, fragment) for fragment in extract_xml_log_fragments(text)]
    return _load_from_xml_fragment_records(
        fragment_records,
        self_abs_seat=self_abs_seat,
        self_player_name=self_player_name,
    )


def load_xml_discard_snapshots(
    text: str,
    self_abs_seat: Optional[int] = None,
    self_player_name: Optional[str] = None,
) -> tuple[GameState, list[XmlDiscardSnapshot]]:
    """Load XML and return discard-time hand snapshots in discard order."""

    fragment_records = [(None, fragment) for fragment in extract_xml_log_fragments(text)]
    state = _build_xml_game_state(
        self_abs_seat=self_abs_seat,
        self_player_name=self_player_name,
    )
    state.source_fragments = list(fragment_records)
    _preload_xml_un_context(state, fragment_records)

    snapshots: list[XmlDiscardSnapshot] = []
    for timestamp, fragment in fragment_records:
        event = parse_fragment(state, timestamp, fragment)
        round_state = state.current_round
        if (
            event.event_type != "discard"
            or round_state is None
            or event.seat is None
            or event.tile_136 is None
        ):
            continue
        discard_index = event.attrs.get("round_discard_index")
        if discard_index is None:
            continue
        try:
            normalized_discard_index = int(discard_index)
        except (TypeError, ValueError):
            continue
        hand_tiles_by_seat_136 = {
            seat: tuple(round_state.current_hands_136.get(seat, ()))
            for seat in range(SEAT_COUNT)
        }
        # XML replay parsing has already removed the discard from current_hands_136, so restore the
        # discarding seat from the Discard object's pre-discard snapshot before exporting to DB.
        discards_for_seat = round_state.discards.get(event.seat, [])
        if discards_for_seat:
            latest_discard = discards_for_seat[-1]
            if (
                latest_discard.event_index == len(state.events) - 1
                and latest_discard.hand_tiles_before_discard_136
            ):
                hand_tiles_by_seat_136[event.seat] = tuple(
                    latest_discard.hand_tiles_before_discard_136
                )
        snapshots.append(
            XmlDiscardSnapshot(
                kyoku_index=round_state.kyoku_index,
                honba=round_state.honba,
                discard_index=normalized_discard_index,
                player_rel_seat=event.seat,
                discard_tile_136=event.tile_136,
                hand_tiles_by_seat_136=hand_tiles_by_seat_136,
            )
        )

    return _finalize_loaded_state(state), snapshots


def resolve_seat_mapping(
    state: GameState,
    self_abs_seat: Optional[int] = None,
    self_player_name: Optional[str] = None,
) -> GameState:
    """Resolve a pending XML seat mapping by replaying the stored raw fragments."""

    if not _is_xml_log_source(state):
        return state

    fragment_records = list(state.source_fragments)
    if not fragment_records:
        fragment_records = [
            (event.timestamp, event.raw_tag)
            for event in state.raw_events
            if event.raw_tag
        ]
    if not fragment_records:
        raise ValueError("No XML source fragments are available to replay for seat resolution.")

    effective_self_abs_seat = self_abs_seat if self_abs_seat is not None else state.self_abs_seat
    effective_self_player_name = self_player_name or state.self_player_name
    resolved_state = _load_from_xml_fragment_records(
        fragment_records,
        self_abs_seat=effective_self_abs_seat,
        self_player_name=effective_self_player_name,
    )
    if not resolved_state.seat_mapping_resolved:
        raise ValueError(
            "Failed to resolve XML seat mapping. Provide self_abs_seat or a self_player_name "
            "that matches exactly one decoded UN player name."
        )

    state.__dict__.clear()
    state.__dict__.update(resolved_state.__dict__)
    return state


def export_round_summary(game_state: GameState) -> dict[str, Any]:
    """Export a summary that is easy to inspect or persist."""

    def summarize_players(players: dict[int, PlayerInfo]) -> dict[int, dict[str, Any]]:
        return {
            seat: {
                "seat": player.seat,
                "name": player.name,
                "dan": player.dan,
                "rate": player.rate,
                "sx": player.sx,
            }
            for seat, player in players.items()
        }

    def summarize_round(round_state: RoundState) -> dict[str, Any]:
        return {
            "round_id": round_state.round_id,
            "round_key": round_state.round_key,
            "kyoku_index": round_state.kyoku_index,
            "honba": round_state.honba,
            "kyotaku": round_state.kyotaku,
            "dice_1_minus_1": round_state.dice_1_minus_1,
            "dice_2_minus_1": round_state.dice_2_minus_1,
            "oya": round_state.oya,
            "oya_abs": round_state.oya_abs,
            "oya_rel": round_state.oya_rel,
            "seat_order": list(round_state.seat_order),
            "scores": list(round_state.scores),
            "dora_indicators_136": list(round_state.dora_indicators_136),
            "initial_self_hand_136": list(round_state.initial_self_hand_136),
            "initial_hands_136": {
                seat: list(hand_tiles)
                for seat, hand_tiles in round_state.initial_hands_136.items()
            },
            "initial_hands_abs_136": {
                seat: list(hand_tiles)
                for seat, hand_tiles in round_state.initial_hands_abs_136.items()
            },
            "initial_hands_rel_136": {
                seat: list(hand_tiles)
                for seat, hand_tiles in round_state.initial_hands_rel_136.items()
            },
            "hands_136": {
                seat: list(hand_tiles)
                for seat, hand_tiles in round_state.hands_136.items()
            },
            "kawa_raw": {
                seat: list(raw_tokens)
                for seat, raw_tokens in round_state.kawa_raw.items()
            },
            "snapshot_is_partial": round_state.snapshot_is_partial,
            "reach_state": dict(round_state.reach_state),
            "discard_counts": {
                seat: len(discards)
                for seat, discards in round_state.discards.items()
            },
            "melds": {
                seat: [meld.meld_type for meld in melds]
                for seat, melds in round_state.melds.items()
            },
            "result": round_state.result,
            "validation_issues": list(round_state.validation_issues),
        }

    return {
        "game_id": game_state.game_id,
        "go_type": game_state.go_type,
        "room_class_code": game_state.room_class_code,
        "room_class_label": game_state.room_class_label,
        "parser_mode": game_state.parser_mode,
        "source_kind": game_state.source_kind,
        "seat_order": list(game_state.seat_order),
        "self_abs_seat": game_state.self_abs_seat,
        "seat_mapping_resolved": game_state.seat_mapping_resolved,
        "current_dealer_seat": game_state.current_dealer_seat,
        "current_dealer_seat_rel": game_state.current_dealer_seat_rel,
        "round_key": game_state.round_key,
        "round_id": game_state.round_id,
        "unresolved_spec_todos": list(game_state.unresolved_spec_todos),
        "players": summarize_players(game_state.players),
        "players_abs": summarize_players(game_state.players_abs),
        "players_rel": summarize_players(game_state.players_rel),
        "round_count": len(game_state.rounds),
        "current_round": summarize_round(game_state.current_round) if game_state.current_round else None,
        "rounds": [summarize_round(round_state) for round_state in game_state.rounds],
        "diagnostics": list(game_state.diagnostics),
    }


def export_discards(game_state: GameState) -> dict[int, list[Discard]]:
    """Export current-round discards keyed by seat."""

    if game_state.current_round is None:
        return {seat: [] for seat in range(SEAT_COUNT)}
    return {
        seat: list(discards)
        for seat, discards in game_state.current_round.discards.items()
    }


def export_event_rows(game_state: GameState) -> list[dict[str, Any]]:
    """Export per-event rows matching the parser CSV contract."""

    rows: list[dict[str, Any]] = []
    for event in game_state.events:
        if event.event_type == "draw":
            action = "draw"
        elif event.event_type == "discard":
            action = "discard"
        elif event.event_type == "call":
            action = "meld"
        else:
            action = event.event_type

        tsumogiri_flag = ""
        if event.event_type == "discard":
            if event.attrs.get("tsumogiri") is True and event.attrs.get("is_tsumogiri_estimated"):
                tsumogiri_flag = "risekichu_hokan_tsumogiri"
            elif event.attrs.get("tsumogiri") is True:
                tsumogiri_flag = "tsumogiri"
            elif event.attrs.get("tsumogiri") is False:
                tsumogiri_flag = "tedashi"

        rows.append(
            {
                "timestamp": event.timestamp,
                "tag_type": event.event_type,
                "player": event.seat,
                "tile136": event.tile_136,
                "action": action,
                "tsumogiri_flag": tsumogiri_flag,
                "action_delay_ms": event.action_delay_ms,
                "delay_source": event.delay_source,
                "delay_confidence": event.delay_confidence,
                "raw_tag": event.raw_tag,
            }
        )
    return rows


def export_event_csv_text(game_state: GameState) -> str:
    """Render event rows as CSV text."""

    fieldnames = [
        "timestamp",
        "tag_type",
        "player",
        "tile136",
        "action",
        "tsumogiri_flag",
        "action_delay_ms",
        "delay_source",
        "delay_confidence",
        "raw_tag",
    ]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(export_event_rows(game_state))
    return buffer.getvalue()
