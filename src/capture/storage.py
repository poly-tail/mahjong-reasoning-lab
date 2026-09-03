from __future__ import annotations

import csv
import copy
import json
import queue
import re
import shutil
import threading
import time
import traceback
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from capture.csv_db_schema import (
    CSV_DB_DIRNAME,
    CSV_TABLE_SPECS,
    CsvTableSpec,
    LEGACY_REMOVED_FILENAME_GLOBS,
    RELATIVE_SEAT_NAME_COLUMNS,
    build_discard_id,
    build_hanchan_id,
    build_kyoku_id,
    build_kyoku_info,
    build_same_day_player_signature,
    monthly_chunk_token_from_hanchan_id,
)
from capture.discard_ledger import DiscardResetReason
from capture.fragment_parser import load_xml_discard_snapshots
from capture.state import (
    CaptureState,
    Discard,
    Event,
    LAG_FLAG_FALSE_CONFIRMED,
    LAG_FLAG_SYSTEM_DELAY,
    LAG_SYSTEM_DELAY_MAX_MS,
    LAG_FLAG_TRUE_CALLED,
    LAG_FLAG_TRUE_UNCALLED_PROBABLE,
    LAG_FLAG_UNCONFIRMED,
    Meld,
    RoundState,
    mark_runtime_thread_progress,
    parse_tenhou_game_type_hex,
    round_first_row_thinking_average_ms_by_seat,
    tenhou_room_class_label,
    tile136_to_tile37,
    tile136_to_tile34,
    tile136_to_tile34_index,
    tile136_to_tile37_text,
)
from logic.hand_analysis import (
    calculate_shanten_from_tiles_136,
    detect_ryanmen_fixed_discard,
    find_tenpai_wait_tiles_34_from_tiles_136,
    infer_open_meld_count_from_pre_discard_hand_size,
)
from logic.danger_suji import (
    build_all_opponent_suji_danger_profiles,
    build_all_opponent_suji_panel_summaries,
    build_discard_red_tint_indices_by_seat,
    build_latest_discard_push_alert_percentages,
    estimate_tile_suji_danger_percent,
)
from runtime_paths import DEFAULT_CSV_DB_DIR
from visible_tiles import collect_visible_tile_summary_from_tile136

# INIT_LIKE_EVENT_TYPES の集合。
INIT_LIKE_EVENT_TYPES = frozenset({"init", "reinit", "initbylog", "wgc"})
CSV_PERSIST_EVENT_TYPES = INIT_LIKE_EVENT_TYPES | frozenset({"discard", "agari", "go", "un"})
# SINGLE_FILE_LOGICAL_TABLES の集合。
SINGLE_FILE_LOGICAL_TABLES = frozenset({"hanchan_master", "kyoku_master", "player_profiles"})
# LEGACY_OPTIONAL_COLUMNS の集合。
LEGACY_OPTIONAL_COLUMNS = frozenset(
    {
        "lag_resolution",
        "hanchan_date",
        "hanchan_start_hms",
        "hanchan_id_source",
        "first_init_tag",
        "hanchan_start_epoch_ms",
        "game_id",
        "source_kind",
        "same_day_player_signature",
        "kyoku_index",
        "round_id_legacy",
        "round_start_epoch_ms",
        "seed_json",
        "initial_scores_json",
        "initial_dora_indicators_136_json",
        "discard_tile_37",
        "discard_tile_34",
        "discard_epoch_ms",
        "discard_index",
        "tsumogiri_flag",
        "riichi_marker_before",
        "discard_called",
        "discard_offset_ms_from_hanchan_start",
        "discard_time_text",
        "thinking_time_source",
        "thinking_time_before_reach_source",
        "raw_tag",
        "hand_known",
        "hand_source",
        "updated_at_epoch_ms",
        "seat0_hand_tiles_37_text_json",
        "seat1_hand_tiles_37_text_json",
        "seat2_hand_tiles_37_text_json",
        "seat3_hand_tiles_37_text_json",
        "shanten_kokushi_after_discard",
        "go_type",
        "go_type_hex",
        "room_class_code",
        "kyoku_info",
    }
)
# COMPAT_OPTIONAL_MISSING_COLUMNS の集合。
COMPAT_OPTIONAL_MISSING_COLUMNS = frozenset(
    {
        "room_class_label",
        "source_url",
        "thinking_time_before_reach_ms",
        "seat0_player_name",
        "seat1_player_name",
        "seat2_player_name",
        "seat3_player_name",
        "oya_player_name",
        "seat0_first_row_avg_thinking_time_ms",
        "seat1_first_row_avg_thinking_time_ms",
        "seat2_first_row_avg_thinking_time_ms",
        "seat3_first_row_avg_thinking_time_ms",
        "discard_epoch_s",
        "discard_tile_37_text",
        "tsumogiri_flag",
        "seat0_hand_tiles_136_json",
        "seat1_hand_tiles_136_json",
        "seat2_hand_tiles_136_json",
        "seat3_hand_tiles_136_json",
        "seat0_hand_tiles_37_text",
        "seat1_hand_tiles_37_text",
        "seat2_hand_tiles_37_text",
        "seat3_hand_tiles_37_text",
        "shanten_after_discard",
        "shanten_normal_after_discard",
        "shanten_chiitoitsu_after_discard",
        "wait_tiles_after_discard_mspz",
        "ryanmen_fixed_flag",
        "pystyle_top1_tile_37_text",
        "pystyle_top1_expected_value_text",
        "pystyle_top2_tile_37_text",
        "pystyle_top2_expected_value_text",
        "pystyle_top3_tile_37_text",
        "pystyle_top3_expected_value_text",
        "agari_state_snapshot_json",
    }
)
# _LEGACY_HAND_SNAPSHOT_CACHE の対応表。
_LEGACY_HAND_SNAPSHOT_CACHE: dict[str, dict[str, dict[str, str]]] = {}
# _LEGACY_HANCHAN_NAME_CACHE の対応表。
_LEGACY_HANCHAN_NAME_CACHE: dict[str, dict[str, dict[str, str]]] = {}
_LEGACY_HANCHAN_METADATA_CACHE: dict[str, dict[str, dict[str, str]]] = {}
TENHOU_LOG_GAME_TYPE_PATTERN = re.compile(r"gm-([0-9a-fA-F]{4})-")
# DISCARD_HAND_SNAPSHOT_COLUMNS の並びを定義する。
DISCARD_HAND_SNAPSHOT_COLUMNS = tuple(
    column
    for seat in range(4)
    for column in (
        f"seat{seat}_hand_tiles_136_json",
        f"seat{seat}_hand_tiles_37_text",
    )
)
# DISCARD_ANALYSIS_COLUMNS の並びを定義する。
DISCARD_ANALYSIS_COLUMNS = (
    "shanten_after_discard",
    "shanten_normal_after_discard",
    "shanten_chiitoitsu_after_discard",
    "wait_tiles_after_discard_mspz",
    "ryanmen_fixed_flag",
)
PYSTYLE_HISTORY_COLUMNS = (
    "pystyle_top1_tile_37_text",
    "pystyle_top1_expected_value_text",
    "pystyle_top2_tile_37_text",
    "pystyle_top2_expected_value_text",
    "pystyle_top3_tile_37_text",
    "pystyle_top3_expected_value_text",
)
_ASYNC_PERSIST_STOP = object()
_FILE_IO_RETRY_ATTEMPTS = 6
_FILE_IO_RETRY_DELAY_S = 0.05


@dataclass(frozen=True)
class AsyncPersistJob:
    """One queued CSV-persist request carrying an immutable event-time snapshot."""

    state: CaptureState
    event: Event
    monitor_state: CaptureState | None = None


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _csv_optional_float(value: Any) -> float | None:
    """Parse one CSV cell as float while treating blanks as missing values."""

    normalized = _csv_cell(value).strip()
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _run_file_io_with_retry(operation: Callable[[], None]) -> None:
    """Retry short-lived file access failures from OneDrive/AV interference."""

    last_error: OSError | None = None
    for attempt in range(_FILE_IO_RETRY_ATTEMPTS):
        try:
            operation()
            return
        except PermissionError as error:
            last_error = error
        except OSError as error:
            if getattr(error, "errno", None) != 13:
                raise
            last_error = error
        if attempt + 1 < _FILE_IO_RETRY_ATTEMPTS:
            time.sleep(_FILE_IO_RETRY_DELAY_S * (attempt + 1))
    assert last_error is not None
    raise last_error


def _timestamp_to_epoch_ms(timestamp: float | None) -> int | None:
    if timestamp is None:
        return None
    return int(round(timestamp * 1000.0))


def _timestamp_to_epoch_s(timestamp: float | None) -> int | None:
    if timestamp is None:
        return None
    return int(timestamp)


def _timestamp_parts(timestamp: float | None) -> tuple[str, str, str]:
    if timestamp is None:
        return "", "", ""
    dt = datetime.fromtimestamp(timestamp)
    return (
        dt.strftime("%Y%m%d"),
        dt.strftime("%H%M%S"),
        f"{dt.strftime('%Y%m%d%H%M%S')}{dt.microsecond // 1000:03d}",
    )


def _is_round_opening_discard(discard: Discard) -> bool:
    """Return whether this row is the round's opening discard.

    `round_discard_index == 0` is always the dealer's first discard, whose timing is polluted by
    the gap between the draw packet and the point when the initial hand is fully visible.
    """

    return discard.round_discard_index == 0


def _analysis_thinking_time_values(discard: Discard) -> tuple[float | None, float | None]:
    """Return thinking-time fields after removing known opening-discard noise."""

    if _is_round_opening_discard(discard):
        return None, None
    return discard.thinking_time_ms, discard.thinking_time_before_reach_ms


def _extract_hanchan_date_from_game_id(game_id: str | None) -> str | None:
    if not game_id:
        return None
    match = re.search(r"(\d{8})", str(game_id))
    if match is None:
        return None
    return match.group(1)


def _game_type_from_source_url(source_url: str | None) -> int | None:
    normalized = _csv_cell(source_url).strip()
    if not normalized:
        return None
    match = TENHOU_LOG_GAME_TYPE_PATTERN.search(normalized)
    if match is None:
        return None
    return parse_tenhou_game_type_hex(match.group(1))


def _source_url_from_game_id(game_id: str | None) -> str:
    """Return a stable Tenhou viewer URL for a known log id, or blank for non-log ids."""

    normalized = _csv_cell(game_id).strip()
    if not normalized:
        return ""
    if normalized.startswith(("http://", "https://")):
        return normalized
    if TENHOU_LOG_GAME_TYPE_PATTERN.search(normalized):
        return f"https://tenhou.net/0/?log={normalized}"
    return ""


def _source_url_from_state(state: CaptureState) -> str:
    return _source_url_from_game_id(getattr(state, "game_id", None))


def _game_type_columns_from_game_type(game_type: int | None) -> dict[str, str]:
    if game_type is None:
        return {
            "room_class_label": "",
        }
    return {
        "room_class_label": tenhou_room_class_label(game_type) or "",
    }


def _game_type_columns_from_state(state: CaptureState) -> dict[str, str]:
    room_class_label = _csv_cell(getattr(state, "room_class_label", "")).strip()
    if room_class_label:
        return {"room_class_label": room_class_label}
    game_type = getattr(state, "go_type", None)
    if game_type is None:
        game_type = _game_type_from_source_url(getattr(state, "game_id", ""))
    return _game_type_columns_from_game_type(game_type)


def _game_type_columns_from_hanchan_row(row: dict[str, str]) -> dict[str, str]:
    room_class_label = _csv_cell(row.get("room_class_label", "")).strip()
    if room_class_label:
        # Current CSVs persist the table class as a human-readable label. The legacy numeric/hex
        # fields below are only for old files that have not been rewritten.
        return {"room_class_label": room_class_label}
    go_type_text = _csv_cell(row.get("go_type", "")).strip()
    game_type = None
    if go_type_text:
        try:
            game_type = int(go_type_text)
        except ValueError:
            game_type = None
    if game_type is None:
        game_type = parse_tenhou_game_type_hex(_csv_cell(row.get("go_type_hex", "")).strip())
    if game_type is None:
        game_type = _game_type_from_source_url(row.get("source_url", ""))
    return _game_type_columns_from_game_type(game_type)


def _player_names_by_rel_seat(state: CaptureState) -> list[str | None]:
    return [
        state.players.get(seat).name if state.players.get(seat) is not None else None
        for seat in range(4)
    ]


def _player_name(state: CaptureState, seat: int | None) -> str:
    if seat is None:
        return ""
    player = state.players.get(seat)
    if player is None or player.name is None:
        return ""
    return player.name


def _decode_hand_tiles_json(json_text: str) -> list[int] | None:
    normalized = _csv_cell(json_text).strip()
    if not normalized:
        return None
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    hand_tiles: list[int] = []
    for value in payload:
        try:
            hand_tiles.append(int(value))
        except (TypeError, ValueError):
            return None
    return hand_tiles


def _hand_tiles_37_text(hand_tiles_136: list[int]) -> str:
    sorted_tiles_136 = sorted(
        tile_136 for tile_136 in hand_tiles_136 if isinstance(tile_136, int)
    )
    grouped_tiles: dict[str, list[str]] = {suit: [] for suit in ("m", "p", "s", "z")}
    for tile_136 in sorted_tiles_136:
        tile_text = tile136_to_tile37_text(tile_136)
        if tile_text is None:
            continue
        suit = tile_text[-1]
        if suit not in grouped_tiles:
            continue
        grouped_tiles[suit].append(tile_text[:-1])
    return " ".join(
        f"{''.join(grouped_tiles[suit])}{suit}"
        for suit in ("m", "p", "s", "z")
        if grouped_tiles[suit]
    )


def _tile34_indices_to_mspz_text(tile_34_indices: list[int] | tuple[int, ...]) -> str:
    grouped_tiles: dict[str, list[str]] = {suit: [] for suit in ("m", "p", "s", "z")}
    for tile_34 in sorted(set(tile_34_indices)):
        if not 0 <= tile_34 < 34:
            continue
        if tile_34 < 27:
            suit = "mps"[tile_34 // 9]
            rank = (tile_34 % 9) + 1
        else:
            suit = "z"
            rank = tile_34 - 26
        grouped_tiles[suit].append(str(rank))
    return " ".join(
        f"{''.join(grouped_tiles[suit])}{suit}"
        for suit in ("m", "p", "s", "z")
        if grouped_tiles[suit]
    )


def _post_discard_hand_tiles_136(
    pre_discard_hand_tiles_136: list[int],
    discard_tile_136: int,
) -> list[int] | None:
    post_discard_hand_tiles_136 = list(pre_discard_hand_tiles_136)
    try:
        post_discard_hand_tiles_136.remove(discard_tile_136)
        return post_discard_hand_tiles_136
    except ValueError:
        discard_tile_34 = tile136_to_tile34_index(discard_tile_136)
        if discard_tile_34 is None:
            return None
        for index, tile_136 in enumerate(post_discard_hand_tiles_136):
            if tile136_to_tile34_index(tile_136) != discard_tile_34:
                continue
            del post_discard_hand_tiles_136[index]
            return post_discard_hand_tiles_136
    return None


def _hand_tiles_by_seat_from_fact_row(row: dict[str, str]) -> dict[int, list[int]] | None:
    hands_by_seat: dict[int, list[int]] = {}
    for seat in range(4):
        hand_tiles = _decode_hand_tiles_json(row.get(f"seat{seat}_hand_tiles_136_json", ""))
        if hand_tiles is None:
            return None
        hands_by_seat[seat] = hand_tiles
    return hands_by_seat


def _count_tile34_in_hand(hand_tiles_136: list[int], tile_34: int) -> int:
    return sum(1 for tile_136 in hand_tiles_136 if tile136_to_tile34_index(tile_136) == tile_34)


def _empty_discard_analysis_columns() -> dict[str, str]:
    return {
        column: ""
        for column in DISCARD_ANALYSIS_COLUMNS
    }


def _empty_pystyle_history_columns() -> dict[str, str]:
    return {
        column: ""
        for column in PYSTYLE_HISTORY_COLUMNS
    }


def _normalize_hand_tiles_37_key(hand_tiles_37: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sorted(int(tile) for tile in hand_tiles_37))


def _build_pystyle_history_columns(
    ranked_entries: list[tuple[str, str]] | tuple[tuple[str, str], ...],
) -> dict[str, str]:
    columns = _empty_pystyle_history_columns()
    for rank, (tile_text, expected_value_text) in enumerate(ranked_entries[:3], start=1):
        columns[f"pystyle_top{rank}_tile_37_text"] = _csv_cell(tile_text)
        columns[f"pystyle_top{rank}_expected_value_text"] = _csv_cell(expected_value_text)
    return columns


def remember_pystyle_self_history(
    state: CaptureState,
    hand_tiles_37: list[int] | tuple[int, ...],
    ranked_entries: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    *,
    blocking: bool = True,
) -> bool:
    """Cache the visible AI TOP3 result for the current self hand under the active round id."""

    acquired = state.state_lock.acquire(blocking=blocking)
    if not acquired:
        return False
    try:
        round_state = state.current_round
        round_id = round_state.round_id if round_state is not None else state.round_id
        if not round_id or round_state is None:
            return False
        normalized_hand_key = _normalize_hand_tiles_37_key(hand_tiles_37)
        if len(normalized_hand_key) != 14:
            return False
        next_discard_index = sum(len(discards) for discards in round_state.discards.values())
        normalized_columns = _build_pystyle_history_columns(ranked_entries)
        history = dict(getattr(state, "pystyle_self_history_by_round_hand", {}))
        history_key = (round_id, next_discard_index, normalized_hand_key)
        if history.get(history_key) == normalized_columns:
            return False
        history[history_key] = normalized_columns
        state.pystyle_self_history_by_round_hand = history
        return True
    finally:
        state.state_lock.release()


def _pystyle_history_columns_from_state(
    state: CaptureState,
    round_state: RoundState,
    seat: int,
    discard_index: int,
    hand_tiles_136: list[int],
) -> dict[str, str]:
    """Return cached AI TOP3 history columns for one self-hand discard snapshot."""

    columns = _empty_pystyle_history_columns()
    if seat != 0:
        return columns
    round_id = round_state.round_id or state.round_id
    if not round_id or not hand_tiles_136:
        return columns
    hand_tiles_37 = [
        tile_id
        for tile_id in (tile136_to_tile37(tile_136) for tile_136 in hand_tiles_136)
        if tile_id is not None
    ]
    if len(hand_tiles_37) != len(hand_tiles_136):
        return columns
    history = getattr(state, "pystyle_self_history_by_round_hand", {})
    cached_columns = history.get(
        (
            round_id,
            discard_index,
            _normalize_hand_tiles_37_key(hand_tiles_37),
        )
    )
    if cached_columns is None:
        return columns
    return dict(cached_columns)


def _discard_analysis_columns(row: dict[str, Any]) -> dict[str, str]:
    """Build shanten and ryanmen-fix columns from one discard_fact-compatible row."""

    analysis = _empty_discard_analysis_columns()
    try:
        seat = int(_csv_cell(row.get("player_rel_seat", "")))
    except ValueError:
        return analysis
    if not 0 <= seat < 4:
        return analysis

    hand_tiles_136 = _decode_hand_tiles_json(_csv_cell(row.get(f"seat{seat}_hand_tiles_136_json", "")))
    if hand_tiles_136 is None:
        return analysis

    # The discard_fact hand snapshot is the discarding player's concealed hand immediately before
    # the discard. The DB column names keep the older and somewhat confusing *_after_discard label
    # for compatibility, but the stored shanten values are intentionally derived from this
    # pre-discard snapshot.
    completed_meld_count = infer_open_meld_count_from_pre_discard_hand_size(len(hand_tiles_136))
    if completed_meld_count is None:
        return analysis

    shanten = calculate_shanten_from_tiles_136(
        hand_tiles_136,
        open_meld_count=completed_meld_count,
    )
    analysis["shanten_after_discard"] = _csv_cell(shanten.overall)
    analysis["shanten_normal_after_discard"] = _csv_cell(shanten.normal)
    analysis["shanten_chiitoitsu_after_discard"] = _csv_cell(shanten.chiitoitsu)

    try:
        discard_tile_136 = int(_csv_cell(row.get("discard_tile_136", "")))
    except ValueError:
        return analysis

    ryanmen_fixed = detect_ryanmen_fixed_discard(hand_tiles_136, discard_tile_136)
    analysis["ryanmen_fixed_flag"] = _csv_cell(ryanmen_fixed.is_ryanmen_fixed)
    post_discard_hand_tiles_136 = _post_discard_hand_tiles_136(hand_tiles_136, discard_tile_136)
    if post_discard_hand_tiles_136 is None:
        return analysis

    wait_tiles_34 = find_tenpai_wait_tiles_34_from_tiles_136(
        post_discard_hand_tiles_136,
        open_meld_count=completed_meld_count,
    )
    analysis["wait_tiles_after_discard_mspz"] = _tile34_indices_to_mspz_text(wait_tiles_34)
    return analysis


def _merge_preserved_discard_fact_fields(
    existing_row: dict[str, str] | None,
    candidate_row: dict[str, Any],
) -> dict[str, Any]:
    """Keep the first recorded pre-discard hand snapshot for a discard while refreshing mutable fields."""

    merged_row = dict(candidate_row)
    if existing_row is None:
        merged_row.update(_discard_analysis_columns(merged_row))
        return merged_row

    # Live sync revisits old rows after later draws/calls. Preserve per-discard snapshots once they
    # exist, otherwise historical hand sizes, shanten, and ryanmen-fix analysis would drift.
    for column in DISCARD_HAND_SNAPSHOT_COLUMNS:
        existing_value = _csv_cell(existing_row.get(column, "")).strip()
        if existing_value:
            merged_row[column] = existing_row[column]
    for column in PYSTYLE_HISTORY_COLUMNS:
        existing_value = _csv_cell(existing_row.get(column, "")).strip()
        candidate_value = _csv_cell(merged_row.get(column, "")).strip()
        if existing_value and not candidate_value:
            merged_row[column] = existing_row[column]

    merged_row.update(_discard_analysis_columns(merged_row))
    return merged_row


def _can_pon_from_hand(hand_tiles_136: list[int], tile_34: int) -> bool:
    return _count_tile34_in_hand(hand_tiles_136, tile_34) >= 2


def _can_chi_from_hand(hand_tiles_136: list[int], tile_34: int) -> bool:
    if tile_34 < 0 or tile_34 >= 27:
        return False
    suit_offset = (tile_34 // 9) * 9
    rank = tile_34 - suit_offset + 1
    counts = {
        suit_offset + local_rank - 1: _count_tile34_in_hand(hand_tiles_136, suit_offset + local_rank - 1)
        for local_rank in range(1, 10)
    }
    patterns = (
        (rank - 2, rank - 1),
        (rank - 1, rank + 1),
        (rank + 1, rank + 2),
    )
    for left_rank, right_rank in patterns:
        if not (1 <= left_rank <= 9 and 1 <= right_rank <= 9):
            continue
        left_tile = suit_offset + left_rank - 1
        right_tile = suit_offset + right_rank - 1
        if counts.get(left_tile, 0) >= 1 and counts.get(right_tile, 0) >= 1:
            return True
    return False


def _can_anyone_call_discard(
    discard_seat: int,
    discard_tile_136: int,
    hands_by_seat: dict[int, list[int]],
) -> bool:
    """Return whether the discard could legally be called by chi or pon."""

    discard_tile_34 = tile136_to_tile34_index(discard_tile_136)
    if discard_tile_34 is None:
        return False

    shimocha_seat = (discard_seat + 1) % 4
    if _can_chi_from_hand(hands_by_seat.get(shimocha_seat, []), discard_tile_34):
        return True

    for seat in range(4):
        if seat == discard_seat:
            continue
        if _can_pon_from_hand(hands_by_seat.get(seat, []), discard_tile_34):
            return True
    return False


def _refined_lag_flag_from_hands(
    discard_seat: int,
    discard_tile_136: int,
    hands_by_seat: dict[int, list[int]],
) -> int:
    if _can_anyone_call_discard(discard_seat, discard_tile_136, hands_by_seat):
        return LAG_FLAG_TRUE_UNCALLED_PROBABLE
    return LAG_FLAG_FALSE_CONFIRMED


def _same_day_signature_from_hanchan_row(row: dict[str, str]) -> str | None:
    hanchan_id = row.get("hanchan_id", "")
    if len(hanchan_id) < 8 or not hanchan_id[:8].isdigit():
        return None
    return build_same_day_player_signature(
        hanchan_id[:8],
        [row.get(column) or "" for column in RELATIVE_SEAT_NAME_COLUMNS],
    )


def _migrate_kyoku_id(kyoku_id: str) -> str:
    if "_" in kyoku_id:
        return kyoku_id
    if len(kyoku_id) >= 18:
        return f"{kyoku_id[:-4]}_{kyoku_id[-4:]}"
    return kyoku_id


def _migrate_discard_id(discard_id: str) -> str:
    if not discard_id:
        return discard_id
    if discard_id.count("_") >= 2:
        prefix, suffix = discard_id.rsplit("_", 1)
        if suffix.isdigit():
            return f"{prefix}_{int(suffix):03d}"
        return discard_id
    if "_" in discard_id:
        prefix, suffix = discard_id.rsplit("_", 1)
        if suffix.isdigit() and len(suffix) >= 5:
            kyoku_info = suffix[:4]
            discard_suffix = suffix[4:]
            return f"{prefix}_{kyoku_info}_{int(discard_suffix):03d}"
        return discard_id
    if discard_id.isdigit() and len(discard_id) >= 22:
        return (
            f"{discard_id[:-8]}_"
            f"{discard_id[-8:-4]}_"
            f"{int(discard_id[-4:]):03d}"
        )
    return discard_id


def _normalized_db_dir_key(db_dir: Path) -> str:
    return str(db_dir.resolve())


def _prime_legacy_hand_snapshot_cache(db_dir: Path) -> None:
    cache_key = _normalized_db_dir_key(db_dir)
    if cache_key in _LEGACY_HAND_SNAPSHOT_CACHE:
        return
    snapshots: dict[str, dict[str, str]] = {}
    candidate_paths = list(db_dir.glob("discard_hands_*.csv"))
    candidate_paths.extend(sorted(db_dir.glob("old/*/discard_hands_*.csv")))
    for path in candidate_paths:
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                discard_id = _csv_cell(row.get("discard_id"))
                seat_rel = _csv_cell(row.get("seat_rel"))
                if not discard_id or seat_rel not in {"0", "1", "2", "3"}:
                    continue
                snapshot_keys = [discard_id]
                migrated_discard_id = _migrate_discard_id(discard_id)
                if migrated_discard_id != discard_id:
                    snapshot_keys.append(migrated_discard_id)
                key = f"seat{seat_rel}_hand_tiles_136_json"
                value = _csv_cell(row.get("hand_tiles_136_json", ""))
                for snapshot_key in snapshot_keys:
                    snapshot = snapshots.setdefault(snapshot_key, {})
                    if key not in snapshot or not snapshot[key]:
                        snapshot[key] = value
    _LEGACY_HAND_SNAPSHOT_CACHE[cache_key] = snapshots


def _legacy_hand_snapshot_columns_for(db_dir: Path, discard_id: str) -> dict[str, str]:
    snapshots = _LEGACY_HAND_SNAPSHOT_CACHE.get(_normalized_db_dir_key(db_dir), {})
    return snapshots.get(discard_id, {})


def _prime_legacy_hanchan_name_cache(db_dir: Path) -> None:
    cache_key = _normalized_db_dir_key(db_dir)
    if cache_key in _LEGACY_HANCHAN_NAME_CACHE:
        return
    names_by_hanchan_id: dict[str, dict[str, str]] = {}
    path = db_dir / "hanchan_master.csv"
    if path.is_file():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                hanchan_id = _csv_cell(row.get("hanchan_id"))
                if not hanchan_id:
                    continue
                names_by_hanchan_id[hanchan_id] = {
                    column: _csv_cell(row.get(column, ""))
                    for column in RELATIVE_SEAT_NAME_COLUMNS
                }
    _LEGACY_HANCHAN_NAME_CACHE[cache_key] = names_by_hanchan_id


def _legacy_hanchan_names_for(db_dir: Path, hanchan_id: str) -> dict[str, str]:
    names_by_hanchan_id = _LEGACY_HANCHAN_NAME_CACHE.get(_normalized_db_dir_key(db_dir), {})
    return names_by_hanchan_id.get(hanchan_id, {})


def _prime_legacy_hanchan_metadata_cache(db_dir: Path) -> None:
    cache_key = _normalized_db_dir_key(db_dir)
    if cache_key in _LEGACY_HANCHAN_METADATA_CACHE:
        return
    metadata_by_hanchan_id: dict[str, dict[str, str]] = {}
    path = db_dir / "hanchan_master.csv"
    if path.is_file():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                hanchan_id = _csv_cell(row.get("hanchan_id"))
                if not hanchan_id:
                    continue
                metadata_by_hanchan_id[hanchan_id] = _game_type_columns_from_hanchan_row(row)
    _LEGACY_HANCHAN_METADATA_CACHE[cache_key] = metadata_by_hanchan_id


def _legacy_hanchan_metadata_for(db_dir: Path, hanchan_id: str) -> dict[str, str]:
    metadata_by_hanchan_id = _LEGACY_HANCHAN_METADATA_CACHE.get(_normalized_db_dir_key(db_dir), {})
    return metadata_by_hanchan_id.get(hanchan_id, {})


def _remember_hanchan_metadata(db_dir: Path, row: dict[str, Any]) -> None:
    hanchan_id = _csv_cell(row.get("hanchan_id", ""))
    if not hanchan_id:
        return
    cache_key = _normalized_db_dir_key(db_dir)
    # Keep the hanchan metadata cache warm after an upsert so monthly fact rows written later can
    # inherit the corrected room_class_label without rereading hanchan_master.
    cache = _LEGACY_HANCHAN_METADATA_CACHE.setdefault(cache_key, {})
    cache[hanchan_id] = _game_type_columns_from_hanchan_row(
        {key: _csv_cell(value) for key, value in row.items()}
    )


def _visible_tile_counts_34(round_state: RoundState) -> dict[str, int]:
    visible_counter: Counter[int] = Counter()

    for discards in round_state.discards.values():
        for discard in discards:
            if discard.called:
                continue
            tile_34 = tile136_to_tile34(discard.tile_136)
            if tile_34 is not None:
                visible_counter[tile_34] += 1

    for melds in round_state.melds.values():
        for meld in melds:
            for tile_136 in meld.tiles_136:
                tile_34 = tile136_to_tile34(tile_136)
                if tile_34 is not None:
                    visible_counter[tile_34] += 1

    for tile_136 in round_state.dora_indicators_136:
        tile_34 = tile136_to_tile34(tile_136)
        if tile_34 is not None:
            visible_counter[tile_34] += 1

    return {
        str(tile_34): visible_counter[tile_34]
        for tile_34 in sorted(visible_counter)
    }


def _discard_event_for(state: CaptureState, discard: Discard) -> Event | None:
    if not 0 <= discard.event_index < len(state.events):
        return None
    event = state.events[discard.event_index]
    if event.event_type != "discard":
        return None
    return event


def _snapshot_discard_event_for_storage(
    discard: Discard,
    seat: int,
    fallback_event: Event | None,
) -> Event | None:
    """Build a storage-only discard event for a visible snapshot discard.

    REINIT/WGC river snapshots expose already-visible discards without replaying their original
    discard packets. Persist them with the snapshot event timestamp so live capture does not lose
    those rows after a browser reload or capture restart.
    """

    if fallback_event is None or fallback_event.timestamp is None:
        return None
    raw_tag = _csv_cell(getattr(discard, "raw_tag", "")).strip()
    if not _is_snapshot_discard_for_storage(discard):
        return None
    return Event(
        timestamp=fallback_event.timestamp,
        event_type="discard",
        raw_tag=raw_tag,
        seat=seat,
        attrs={
            "snapshot_source_event_type": fallback_event.event_type,
            "snapshot_source_raw_tag": _csv_cell(fallback_event.raw_tag),
        },
    )


def _discard_event_for_storage(
    state: CaptureState,
    discard: Discard,
    seat: int,
    fallback_event: Event | None = None,
) -> Event | None:
    """Return the observed discard event, or a snapshot fallback event for storage."""

    return _discard_event_for(state, discard) or _snapshot_discard_event_for_storage(
        discard,
        seat,
        fallback_event,
    )


def _find_discard_for_event(
    state: CaptureState,
    round_state: RoundState,
    event: Event,
) -> tuple[int, Discard] | None:
    for seat in range(4):
        for discard in reversed(round_state.discards[seat]):
            discard_event_index = discard.event_index
            if discard_event_index < 0:
                continue
            if discard_event_index >= len(state.events):
                continue
            if state.events[discard_event_index] is event:
                return seat, discard
    return None


def _event_index_for(state: CaptureState, event: Event) -> int | None:
    for index in range(len(state.events) - 1, -1, -1):
        if state.events[index] is event:
            return index
    return None


def _int_event_attr(event: Event, key: str) -> int | None:
    value = event.attrs.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _latest_discard_by_seat(round_state: RoundState, seat: int | None) -> Discard | None:
    if seat is None or not 0 <= seat < 4:
        return None
    discards = round_state.discards.get(seat, [])
    if not discards:
        return None
    return discards[-1]


def _clone_round_state_without_discard(
    round_state: RoundState,
    seat: int,
    discard: Discard,
) -> RoundState:
    cloned_round_state = copy.deepcopy(round_state)
    cloned_discards_by_seat = cloned_round_state.mutable_discard_copy_by_seat()
    cloned_discards = cloned_discards_by_seat.get(seat, [])
    remove_index = None
    for index in range(len(cloned_discards) - 1, -1, -1):
        candidate = cloned_discards[index]
        if (
            discard.round_discard_index is not None
            and candidate.round_discard_index == discard.round_discard_index
        ):
            remove_index = index
            break
        if discard.event_index >= 0 and candidate.event_index == discard.event_index:
            remove_index = index
            break
        if candidate.tile_136 == discard.tile_136:
            remove_index = index
            break
    if remove_index is None and cloned_discards:
        remove_index = len(cloned_discards) - 1
    if remove_index is not None:
        del cloned_discards[remove_index]
        cloned_round_state.replace_discards_for_reset(
            discards_by_seat=cloned_discards_by_seat,
            reason=DiscardResetReason.MANUAL_FULL_RESET,
        )
    return cloned_round_state


def _visible_tile_summary_from_round_state(
    round_state: RoundState,
    *,
    self_hand_tiles_136: list[int] | None = None,
):
    discard_tiles_136 = [
        discard.tile_136
        for discards in round_state.discards.values()
        for discard in discards
        if not discard.called
    ]
    meld_tiles_136 = [
        tile_136
        for melds in round_state.melds.values()
        for meld in melds
        for tile_136 in meld.tiles_136
    ]
    return collect_visible_tile_summary_from_tile136(
        discard_tiles_136=discard_tiles_136,
        hand_tiles_136=list(
            round_state.current_hands_136.get(0, [])
            if self_hand_tiles_136 is None
            else self_hand_tiles_136
        ),
        meld_tiles_136=meld_tiles_136,
        dora_indicator_tiles_136=list(round_state.dora_indicators_136),
    )


def _clone_plain_value_for_async_persist(value: Any) -> Any:
    """Clone plain containers without invoking arbitrary object-level deepcopy hooks."""

    if isinstance(value, dict):
        return {
            _clone_plain_value_for_async_persist(key): _clone_plain_value_for_async_persist(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_clone_plain_value_for_async_persist(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_clone_plain_value_for_async_persist(item) for item in value)
    if isinstance(value, set):
        return {_clone_plain_value_for_async_persist(item) for item in value}
    return value


def _clone_event_for_async_persist(event: Event) -> Event:
    """Return a small independent event copy for the CSV persist worker."""

    cloned_event = copy.copy(event)
    cloned_event.attrs = _clone_plain_value_for_async_persist(getattr(event, "attrs", {}))
    return cloned_event


def _clone_discard_for_async_persist(discard: Discard) -> Discard:
    """Return a lightweight discard copy for the CSV persist worker."""

    cloned_discard = copy.copy(discard)
    cloned_discard.hand_tiles_before_discard_136 = list(
        getattr(discard, "hand_tiles_before_discard_136", ())
    )
    cloned_discard.self_hand_tiles_before_discard_136 = list(
        getattr(discard, "self_hand_tiles_before_discard_136", ())
    )
    return cloned_discard


def _clone_meld_for_async_persist(meld: Meld) -> Meld:
    """Return a lightweight meld copy for the CSV persist worker."""

    cloned_meld = copy.copy(meld)
    cloned_meld.consumed_tile_ids = list(getattr(meld, "consumed_tile_ids", ()))
    cloned_meld.tiles_136 = list(getattr(meld, "tiles_136", ()))
    cloned_meld.tiles_34 = list(getattr(meld, "tiles_34", ()))
    cloned_meld.tiles_37 = list(getattr(meld, "tiles_37", ()))
    return cloned_meld


def _clone_round_state_for_async_persist(round_state: RoundState) -> RoundState:
    """Clone only the current-round fields needed by CSV persistence."""

    return RoundState(
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
        initial_hands_136={
            seat: list(round_state.initial_hands_136.get(seat, ()))
            for seat in range(4)
        },
        initial_hands_abs_136={
            seat: list(round_state.initial_hands_abs_136.get(seat, ()))
            for seat in range(4)
        },
        initial_hands_rel_136={
            seat: list(round_state.initial_hands_rel_136.get(seat, ()))
            for seat in range(4)
        },
        current_hands_136={
            seat: list(round_state.current_hands_136.get(seat, ()))
            for seat in range(4)
        },
        snapshot_is_partial=bool(round_state.snapshot_is_partial),
        started_from_init_like=bool(round_state.started_from_init_like),
        snapshot_bootstrap_sequence=int(getattr(round_state, "snapshot_bootstrap_sequence", 0)),
        hanchan_round_ordinal=int(getattr(round_state, "hanchan_round_ordinal", 0) or 0),
        first_row_thinking_history_recorded=bool(
            getattr(round_state, "first_row_thinking_history_recorded", False)
        ),
        discards={
            seat: [
                _clone_discard_for_async_persist(discard)
                for discard in round_state.discards.get(seat, ())
            ]
            for seat in range(4)
        },
        melds={
            seat: [
                _clone_meld_for_async_persist(meld)
                for meld in round_state.melds.get(seat, ())
            ]
            for seat in range(4)
        },
        reach_state=dict(round_state.reach_state),
        events=[
            _clone_event_for_async_persist(event)
            for event in getattr(round_state, "events", ())
        ],
        draws={
            seat: list(round_state.draws.get(seat, ()))
            for seat in range(4)
        },
        last_draw_tiles_136=dict(round_state.last_draw_tiles_136),
        pending_riichi_markers=dict(round_state.pending_riichi_markers),
        discard_thinking_starts=dict(round_state.discard_thinking_starts),
        discard_thinking_before_reach=dict(round_state.discard_thinking_before_reach),
        pending_response_discard=round_state.pending_response_discard,
        raw_attrs=_clone_plain_value_for_async_persist(round_state.raw_attrs),
        raw_init_attrs=_clone_plain_value_for_async_persist(round_state.raw_init_attrs),
        raw_reinit_attrs=_clone_plain_value_for_async_persist(round_state.raw_reinit_attrs),
        result=_clone_plain_value_for_async_persist(round_state.result),
        reinit_kawa_raw={
            seat: list(round_state.reinit_kawa_raw.get(seat, ()))
            for seat in range(4)
        },
        validation_issues=list(round_state.validation_issues),
    )


def _snapshot_capture_state_for_async_persist(
    state: CaptureState,
    event: Event,
    *,
    blocking: bool = True,
) -> tuple[CaptureState, Event] | None:
    """Return a lightweight immutable snapshot for background DB persistence."""

    state_lock = state.state_lock
    acquired = state_lock.acquire(blocking=blocking)
    if not acquired:
        return None
    try:
        round_state = state.current_round
        if round_state is None or not round_state.started_from_init_like:
            return None
        event_index = _event_index_for(state, event)
        round_snapshot = _clone_round_state_for_async_persist(round_state)
        event_snapshot = _clone_event_for_async_persist(event)
        events_snapshot = [
            _clone_event_for_async_persist(candidate)
            for candidate in state.events
        ]
        snapshot_state = CaptureState(
            players_abs={
                seat: copy.copy(player)
                for seat, player in state.players_abs.items()
            },
            players_rel={
                seat: copy.copy(player)
                for seat, player in state.players_rel.items()
            },
            seat_order=list(state.seat_order),
            game_id=state.game_id,
            go_type=state.go_type,
            room_class_code=state.room_class_code,
            room_class_label=state.room_class_label,
            rounds=[round_snapshot],
            current_round=round_snapshot,
            raw_events=events_snapshot,
            self_seat=state.self_seat,
            parser_mode=state.parser_mode,
            self_abs_seat=state.self_abs_seat,
            self_player_name=state.self_player_name,
            seat_mapping_resolved=state.seat_mapping_resolved,
            pystyle_self_history_by_round_hand=_clone_plain_value_for_async_persist(
                state.pystyle_self_history_by_round_hand
            ),
            hanchan_round_ordinal=int(getattr(state, "hanchan_round_ordinal", 0) or 0),
            first_row_thinking_avg_history_by_seat={
                seat: [
                    float(value)
                    for value in getattr(
                        state,
                        "first_row_thinking_avg_history_by_seat",
                        {},
                    ).get(seat, ())
                ]
                for seat in range(4)
            },
        )
    finally:
        state_lock.release()
    snapshot_state.sync_current_round_context()
    if event_index is not None and 0 <= event_index < len(snapshot_state.events):
        return snapshot_state, snapshot_state.events[event_index]
    return snapshot_state, event_snapshot


def _suji_line_label(suit_index: int, left_number: int, right_number: int) -> str:
    suit_label = "mps"[suit_index] if 0 <= suit_index < 3 else "?"
    return f"{left_number}-{right_number}{suit_label}"


def _suji_line_share_percent(line_weight: float, denominator_count: float) -> float:
    if denominator_count <= 0.0:
        return 0.0
    return round(max(0.0, float(line_weight)) / denominator_count * 100.0, 1)


def _build_agari_alert_records(
    panel_summary: Any,
    push_alert: Any,
) -> list[dict[str, Any]]:
    """Return user-visible alert labels active at agari timing."""

    alerts: list[dict[str, Any]] = []
    remain_count = max(0.0, float(getattr(panel_summary, "denominator_count", 0.0)))
    no_temp_remain_count = getattr(panel_summary, "denominator_count_without_temporary_safe", None)
    if no_temp_remain_count is not None:
        no_temp_remain_count = max(0.0, float(no_temp_remain_count))

    if remain_count < 6.0:
        alerts.append({"severity": "red", "label": f"Remain {remain_count:.1f}"})
    elif remain_count < 8.0:
        alerts.append({"severity": "yellow", "label": f"Remain {remain_count:.1f}"})

    menzen_alert_score = max(0, int(getattr(panel_summary, "menzen_alert_score", 0)))
    if menzen_alert_score >= 5:
        alerts.append(
            {
                "severity": (
                    "purple"
                    if no_temp_remain_count is not None and no_temp_remain_count < 13.0
                    else "red"
                ),
                "label": f"門前 {menzen_alert_score}",
            }
        )
    elif menzen_alert_score >= 3:
        alerts.append({"severity": "yellow", "label": f"門前 {menzen_alert_score}"})

    hand_pattern_alert_level = max(0, int(getattr(panel_summary, "hand_pattern_alert_level", 0)))
    if hand_pattern_alert_level >= 2:
        alerts.append({"severity": "red", "label": "手役傾向"})
    elif hand_pattern_alert_level >= 1:
        alerts.append({"severity": "yellow", "label": "手役傾向"})

    if bool(getattr(panel_summary, "suit_bias_alert", False)):
        alerts.append({"severity": "yellow", "label": "染/対々 UP"})
    if bool(getattr(panel_summary, "ryanmen_chi_central_tedashi_alert", False)):
        alerts.append({"severity": "yellow", "label": "両面チー3-7"})
    if bool(getattr(panel_summary, "tedashi_thinking_rise_alert", False)) and remain_count <= 14.0:
        alerts.append({"severity": "yellow", "label": "思考時間聴牌近"})

    push_percent = max(0.0, float(getattr(push_alert, "percentage", 0.0)))
    try:
        push_threshold_percent = float(getattr(push_alert, "threshold_percent", 9.0))
    except (TypeError, ValueError):
        push_threshold_percent = 9.0
    if push_threshold_percent <= 0.0:
        push_threshold_percent = 9.0
    if push_percent >= push_threshold_percent:
        push_tile_label = str(getattr(push_alert, "tile_label", "") or "").strip()
        push_label = f"Push {push_percent:.1f}%"
        if push_tile_label:
            push_label = f"Push {push_tile_label} {push_percent:.1f}%"
        alerts.append({"severity": "purple", "label": push_label})
    return alerts


def _serialize_agari_suji_seat_payload(
    state: CaptureState,
    seat: int,
    profile: Any,
    panel_summary: Any,
    push_alert: Any,
) -> dict[str, Any]:
    denominator_count = max(0.0, float(getattr(profile, "corrected_musuji_count", 0.0)))
    sorted_line_weights = sorted(
        tuple(getattr(profile, "line_weights", ()) or ()),
        key=lambda item: (-float(item[3]), item[0], item[1], item[2]),
    )
    return {
        "seat": seat,
        "player_name": _player_name(state, seat),
        "remaining_suji_count": round(denominator_count, 1),
        "remaining_suji_count_without_temporary_safe": (
            None
            if getattr(panel_summary, "denominator_count_without_temporary_safe", None) is None
            else round(float(panel_summary.denominator_count_without_temporary_safe), 1)
        ),
        "tenpai_probability": round(float(getattr(panel_summary, "tenpai_probability", 0.0)), 1),
        "line_weights": [
            {
                "line": _suji_line_label(suit_index, left_number, right_number),
                "count": round(float(line_weight), 1),
                "share_percent": _suji_line_share_percent(float(line_weight), denominator_count),
            }
            for suit_index, left_number, right_number, line_weight in sorted_line_weights
            if float(line_weight) > 0.0
        ],
        "top_line_labels": list(getattr(panel_summary, "top_line_labels", ()) or ()),
        "top_line_summaries": [
            asdict(summary) for summary in (getattr(panel_summary, "top_line_summaries", ()) or ())
        ],
        "top_safe_hand_labels": list(getattr(panel_summary, "top_safe_hand_labels", ()) or ()),
        "top_tile_rank_labels": list(getattr(panel_summary, "top_tile_rank_labels", ()) or ()),
        "panel_flags": {
            "menzen_alert_score": int(getattr(panel_summary, "menzen_alert_score", 0)),
            "hand_pattern_alert_level": int(getattr(panel_summary, "hand_pattern_alert_level", 0)),
            "suit_bias_alert": bool(getattr(panel_summary, "suit_bias_alert", False)),
            "ryanmen_chi_central_tedashi_alert": bool(
                getattr(panel_summary, "ryanmen_chi_central_tedashi_alert", False)
            ),
            "tedashi_thinking_rise_alert": bool(
                getattr(panel_summary, "tedashi_thinking_rise_alert", False)
            ),
        },
        "alerts": _build_agari_alert_records(panel_summary, push_alert),
        "push_alert": {
            "percentage": round(float(getattr(push_alert, "percentage", 0.0)), 1),
            "threshold_percent": round(float(getattr(push_alert, "threshold_percent", 9.0)), 1),
            "tile_34": getattr(push_alert, "tile_34", None),
            "tile_label": str(getattr(push_alert, "tile_label", "") or ""),
            "discard_index": getattr(push_alert, "discard_index", None),
            "seat_discard_index": getattr(push_alert, "seat_discard_index", None),
            "is_current": bool(getattr(push_alert, "is_current", False)),
            "target_seats": list(getattr(push_alert, "target_seats", ()) or ()),
            "exact_safe_target_seats": list(
                getattr(push_alert, "exact_safe_target_seats", ()) or ()
            ),
        },
    }


def _serialize_agari_discards_by_seat(
    state: CaptureState,
    round_state: RoundState,
    red_tint_indices_by_seat: dict[int, tuple[int, ...]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for seat in range(4):
        highlighted_indices = set(int(index) for index in red_tint_indices_by_seat.get(seat, ()))
        items: list[dict[str, Any]] = []
        for seat_discard_index, discard in enumerate(round_state.discards.get(seat, ())):
            items.append(
                {
                    "seat_discard_index": seat_discard_index,
                    "round_discard_index": discard.round_discard_index,
                    "tile_136": discard.tile_136,
                    "tile_mspz": tile136_to_tile37_text(discard.tile_136) or "",
                    "tsumogiri": bool(discard.tsumogiri),
                    "tsumogiri_flag": discard.tsumogiri_flag,
                    "called": bool(discard.called),
                    "riichi_marker_before": bool(discard.riichi_marker_before),
                    "lagged": discard.lagged,
                    "lag_delay_ms": discard.lag_delay_ms,
                    "red_tint": seat_discard_index in highlighted_indices,
                }
            )
        payload[str(seat)] = {
            "seat": seat,
            "player_name": _player_name(state, seat),
            "items": items,
        }
    return payload


def _build_agari_state_snapshot_json(
    state: CaptureState,
    round_state: RoundState,
) -> str:
    """Return one JSON snapshot describing the suji state at agari timing."""

    visible_summary = _visible_tile_summary_from_round_state(round_state)
    profiles = build_all_opponent_suji_danger_profiles(
        round_state,
        visible_counts_34=visible_summary.visible_counts_34_index,
        self_hand_counts_34=visible_summary.self_hand_counts_34_index,
    )
    panel_summaries = build_all_opponent_suji_panel_summaries(
        round_state,
        visible_counts_34=visible_summary.visible_counts_34_index,
        self_hand_counts_34=visible_summary.self_hand_counts_34_index,
        profiles=profiles,
    )
    push_alerts = build_latest_discard_push_alert_percentages(
        round_state,
        visible_counts_34=visible_summary.visible_counts_34_index,
    )
    red_tint_indices_by_seat = {
        seat: tuple(int(index) for index in indices)
        for seat, indices in build_discard_red_tint_indices_by_seat(round_state).items()
    }
    payload = {
        "visible_counts_34_index": list(visible_summary.visible_counts_34_index),
        "self_hand_counts_34_index": list(visible_summary.self_hand_counts_34_index),
        "red_tint_indices_by_seat": {
            str(seat): list(red_tint_indices_by_seat.get(seat, ()))
            for seat in range(4)
        },
        "suji_by_seat": {
            str(seat): _serialize_agari_suji_seat_payload(
                state,
                seat,
                profiles[seat],
                panel_summaries[seat],
                push_alerts.get(seat),
            )
            for seat in sorted(profiles)
        },
        "discards_by_seat": _serialize_agari_discards_by_seat(
            state,
            round_state,
            red_tint_indices_by_seat,
        ),
    }
    return _json_text(payload)


def _build_agari_ron_danger_columns(
    state: CaptureState,
    round_state: RoundState,
    event: Event,
    kyoku_id: str,
) -> tuple[dict[str, Any], Discard | None]:
    empty_columns = {
        "deal_in_discard_id": "",
        "deal_in_round_discard_index": "",
        "estimated_danger_percent": "",
        "danger_estimate_source": "",
    }
    winner_seat = _int_event_attr(event, "who")
    from_seat = _int_event_attr(event, "fromWho")
    if winner_seat is None or from_seat is None or winner_seat == from_seat:
        return empty_columns, None

    deal_in_discard = _latest_discard_by_seat(round_state, from_seat)
    if deal_in_discard is None or deal_in_discard.round_discard_index is None:
        return empty_columns, deal_in_discard

    winning_tile_136 = _int_event_attr(event, "machi")
    if winning_tile_136 is None:
        winning_tile_136 = deal_in_discard.tile_136
    winning_tile_34 = tile136_to_tile34_index(winning_tile_136)
    if (
        winning_tile_34 is None
        or deal_in_discard.tile_34 is None
        or deal_in_discard.tile_34 != winning_tile_34
    ):
        return empty_columns, deal_in_discard

    pre_ron_round_state = _clone_round_state_without_discard(round_state, from_seat, deal_in_discard)
    danger_estimate_source = "synthetic_tile"
    if from_seat == 0 and deal_in_discard.hand_tiles_before_discard_136:
        visible_summary = _visible_tile_summary_from_round_state(
            pre_ron_round_state,
            self_hand_tiles_136=list(deal_in_discard.hand_tiles_before_discard_136),
        )
        self_hand_counts_34: list[int] | tuple[int, ...] = visible_summary.self_hand_counts_34_index
        danger_estimate_source = "self_pre_discard_hand"
    else:
        visible_summary = _visible_tile_summary_from_round_state(pre_ron_round_state)
        synthetic_self_hand_counts_34 = [0] * 34
        synthetic_self_hand_counts_34[winning_tile_34] = 1
        self_hand_counts_34 = synthetic_self_hand_counts_34

    estimated_danger_percent = estimate_tile_suji_danger_percent(
        pre_ron_round_state,
        winner_seat,
        winning_tile_34,
        visible_counts_34=visible_summary.visible_counts_34_index,
        self_hand_counts_34=self_hand_counts_34,
    )
    return (
        {
            "deal_in_discard_id": build_discard_id(
                kyoku_id,
                int(deal_in_discard.round_discard_index),
            ),
            "deal_in_round_discard_index": int(deal_in_discard.round_discard_index),
            "estimated_danger_percent": estimated_danger_percent,
            "danger_estimate_source": danger_estimate_source,
        },
        deal_in_discard,
    )


def _empty_agari_ron_danger_columns() -> dict[str, str]:
    """Return blank agari ron-danger columns when the estimate is unavailable."""

    return {
        "deal_in_discard_id": "",
        "deal_in_round_discard_index": "",
        "estimated_danger_percent": "",
        "danger_estimate_source": "",
    }


def _is_snapshot_discard_for_storage(discard: Discard) -> bool:
    """Return whether a discard came from a live river snapshot instead of a discard event."""

    return _csv_cell(getattr(discard, "raw_tag", "")).strip().startswith("REINIT_KAWA:")


def _observed_discards(round_state: RoundState) -> list[tuple[int, Discard]]:
    observed: list[tuple[int, Discard]] = []
    for seat in range(4):
        for discard in round_state.discards[seat]:
            if discard.round_discard_index is None:
                continue
            if discard.event_index < 0 and not _is_snapshot_discard_for_storage(discard):
                continue
            observed.append((seat, discard))
    observed.sort(key=lambda item: item[1].round_discard_index or -1)
    return observed


def _hand_known(round_state: RoundState, seat: int) -> bool:
    if round_state.initial_hands_136.get(seat):
        return True
    if seat == 0 and round_state.current_hands_136.get(seat):
        return True
    if not round_state.snapshot_is_partial and round_state.current_hands_136.get(seat):
        return True
    return False


def _hand_snapshot_columns(
    round_state: RoundState,
    *,
    discard_seat: int | None = None,
    discard: Discard | None = None,
) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for seat in range(4):
        key_136 = f"seat{seat}_hand_tiles_136_json"
        key_37 = f"seat{seat}_hand_tiles_37_text"
        if _hand_known(round_state, seat):
            # Only the discarding player's concealed hand changes during parse_discard(). Reuse the
            # Discard-side pre-discard snapshot there and the current runtime hand for all others.
            if seat == discard_seat and discard is not None and discard.hand_tiles_before_discard_136:
                hand_tiles_136 = list(discard.hand_tiles_before_discard_136)
            else:
                hand_tiles_136 = list(round_state.current_hands_136.get(seat, []))
            snapshot[key_136] = _json_text(hand_tiles_136)
            snapshot[key_37] = _hand_tiles_37_text(hand_tiles_136)
        else:
            snapshot[key_136] = ""
            snapshot[key_37] = ""
    return snapshot


def _archive_target_path(source_path: Path) -> Path:
    archive_date = datetime.now().strftime("%Y%m%d")
    archive_dir = source_path.parent / "old" / archive_date
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / source_path.name
    if archive_path.exists():
        stem = source_path.stem
        suffix = source_path.suffix
        counter = 1
        while True:
            candidate = archive_dir / f"{stem}_{counter:02d}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
    return archive_path


# CsvFileStore を表すデータクラス。
@dataclass
class CsvFileStore:
    # path を保持する。
    path: Path
    # key_columns の並びを保持する。
    key_columns: tuple[str, ...]
    # columns の並びを保持する。
    columns: tuple[str, ...]
    # rows_by_key の対応表。
    rows_by_key: dict[tuple[str, ...], dict[str, str]] = field(default_factory=dict)
    # key_order の一覧。
    key_order: list[tuple[str, ...]] = field(default_factory=list)
    # loaded を保持する。
    loaded: bool = False
    # needs_rewrite を保持する。
    needs_rewrite: bool = False
    # legacy_archive_created を保持する。
    legacy_archive_created: bool = False

    def ensure_exists(self) -> None:
        self._load()
        if self.path.exists():
            if self.needs_rewrite:
                self._rewrite()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        def create_file() -> None:
            with self.path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.columns, lineterminator="\n")
                writer.writeheader()

        _run_file_io_with_retry(create_file)

    def _load(self) -> None:
        if self.loaded:
            return
        self.loaded = True
        if not self.path.exists():
            return

        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            normalized_legacy_fieldnames = [
                fieldname
                for fieldname in fieldnames
                if fieldname not in LEGACY_OPTIONAL_COLUMNS
            ]
            expected_columns = list(self.columns)
            normalized_expected_columns = [
                column
                for column in expected_columns
                if column not in COMPAT_OPTIONAL_MISSING_COLUMNS
            ]
            missing_columns = [
                column for column in expected_columns if column not in normalized_legacy_fieldnames
            ]
            unexpected_columns = [
                column for column in normalized_legacy_fieldnames if column not in expected_columns
            ]
            if normalized_legacy_fieldnames == expected_columns or (
                not unexpected_columns
                and all(column in COMPAT_OPTIONAL_MISSING_COLUMNS for column in missing_columns)
            ) or (
                normalized_legacy_fieldnames == normalized_expected_columns
            ):
                self.needs_rewrite = fieldnames != expected_columns
            else:
                raise ValueError(
                    f"Unexpected CSV header for {self.path}: {reader.fieldnames} != {list(self.columns)}"
                )
            for row in reader:
                normalized = {
                    column: _csv_cell(row.get(column, ""))
                    for column in self.columns
                }
                if self._apply_legacy_row_migrations(normalized, row):
                    self.needs_rewrite = True
                key = tuple(normalized[column] for column in self.key_columns)
                if key not in self.rows_by_key:
                    self.key_order.append(key)
                self.rows_by_key[key] = normalized
        if self.needs_rewrite and self.path.exists():
            self._rewrite()

    def _apply_legacy_row_migrations(
        self,
        normalized: dict[str, str],
        raw_row: dict[str, str | None],
    ) -> bool:
        changed = False
        if "kyoku_id" in self.columns:
            migrated_kyoku_id = _migrate_kyoku_id(normalized.get("kyoku_id", ""))
            if migrated_kyoku_id != normalized.get("kyoku_id", ""):
                normalized["kyoku_id"] = migrated_kyoku_id
                changed = True

        if "discard_id" in self.columns:
            migrated_discard_id = _migrate_discard_id(normalized.get("discard_id", ""))
            if migrated_discard_id != normalized.get("discard_id", ""):
                normalized["discard_id"] = migrated_discard_id
                changed = True

        if "discard_epoch_s" in self.columns and not normalized.get("discard_epoch_s"):
            legacy_ms = _csv_cell(raw_row.get("discard_epoch_ms"))
            if legacy_ms:
                try:
                    normalized["discard_epoch_s"] = str(int(float(legacy_ms)) // 1000)
                    changed = True
                except ValueError:
                    pass

        if "discard_tile_37_text" in self.columns and not normalized.get("discard_tile_37_text"):
            legacy_tile_text = _csv_cell(raw_row.get("discard_tile_37"))
            if legacy_tile_text:
                normalized["discard_tile_37_text"] = legacy_tile_text
                changed = True
            else:
                discard_tile_136 = _csv_cell(normalized.get("discard_tile_136", ""))
                if discard_tile_136:
                    try:
                        converted_tile_text = tile136_to_tile37_text(int(discard_tile_136))
                    except ValueError:
                        converted_tile_text = None
                    if converted_tile_text:
                        normalized["discard_tile_37_text"] = converted_tile_text
                        changed = True

        if "seat0_hand_tiles_136_json" in self.columns:
            discard_id = normalized.get("discard_id", "")
            if discard_id:
                snapshot = _legacy_hand_snapshot_columns_for(self.path.parent, discard_id)
                for seat in range(4):
                    key_136 = f"seat{seat}_hand_tiles_136_json"
                    key_37 = f"seat{seat}_hand_tiles_37_text"
                    legacy_key_37 = f"seat{seat}_hand_tiles_37_text_json"
                    if not normalized.get(key_136):
                        migrated_value = snapshot.get(key_136, "")
                        if migrated_value:
                            normalized[key_136] = migrated_value
                            changed = True
                    if not normalized.get(key_37):
                        migrated_text = _csv_cell(raw_row.get(legacy_key_37))
                        if migrated_text:
                            normalized[key_37] = migrated_text
                            changed = True
                    if not normalized.get(key_37):
                        hand_tiles = _decode_hand_tiles_json(normalized.get(key_136, ""))
                        if hand_tiles is not None:
                            normalized[key_37] = _hand_tiles_37_text(hand_tiles)
                            changed = True

        if "shanten_after_discard" in self.columns:
            analysis_columns = _discard_analysis_columns(normalized)
            for column, value in analysis_columns.items():
                if normalized.get(column, "") != value:
                    normalized[column] = value
                    changed = True

        if "oya_player_name" in self.columns:
            hanchan_id = normalized.get("hanchan_id", "")
            if hanchan_id:
                names = _legacy_hanchan_names_for(self.path.parent, hanchan_id)
                for column in RELATIVE_SEAT_NAME_COLUMNS:
                    if not normalized.get(column):
                        migrated_value = names.get(column, "")
                        if migrated_value:
                            normalized[column] = migrated_value
                            changed = True
                if not normalized.get("oya_player_name"):
                    try:
                        oya_rel = int(normalized.get("oya_rel", ""))
                    except ValueError:
                        oya_rel = -1
                    if 0 <= oya_rel < len(RELATIVE_SEAT_NAME_COLUMNS):
                        migrated_value = normalized.get(
                            RELATIVE_SEAT_NAME_COLUMNS[oya_rel],
                            "",
                        )
                        if migrated_value:
                            normalized["oya_player_name"] = migrated_value
                            changed = True
        if "room_class_label" in self.columns:
            metadata_columns: dict[str, str] = {}
            if "source_url" in self.columns:
                metadata_columns = _game_type_columns_from_hanchan_row(
                    {
                        "room_class_label": _csv_cell(
                            raw_row.get("room_class_label", normalized.get("room_class_label", ""))
                        ),
                        "go_type": _csv_cell(raw_row.get("go_type", "")),
                        "go_type_hex": _csv_cell(raw_row.get("go_type_hex", "")),
                        "source_url": _csv_cell(raw_row.get("source_url", normalized.get("source_url", ""))),
                    }
                )
            elif normalized.get("hanchan_id", ""):
                metadata_columns = _legacy_hanchan_metadata_for(
                    self.path.parent,
                    normalized.get("hanchan_id", ""),
                )
            for column, value in metadata_columns.items():
                if value and normalized.get(column, "") != value:
                    normalized[column] = value
                    changed = True
        return changed

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, str]:
        return {
            column: _csv_cell(row.get(column))
            for column in self.columns
        }

    def get(self, key_values: tuple[Any, ...]) -> dict[str, str] | None:
        self._load()
        normalized_key = tuple(_csv_cell(value) for value in key_values)
        return self.rows_by_key.get(normalized_key)

    def iter_rows(self) -> list[dict[str, str]]:
        self._load()
        return [self.rows_by_key[key] for key in self.key_order]

    def _rewrite(self) -> None:
        if self.needs_rewrite and self.path.exists() and not self.legacy_archive_created:
            self._archive_legacy_file()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        def rewrite_file() -> None:
            with self.path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.columns, lineterminator="\n")
                writer.writeheader()
                for ordered_key in self.key_order:
                    writer.writerow(self.rows_by_key[ordered_key])

        _run_file_io_with_retry(rewrite_file)
        self.needs_rewrite = False

    def _archive_legacy_file(self) -> None:
        archive_path = _archive_target_path(self.path)
        shutil.copy2(self.path, archive_path)
        self.legacy_archive_created = True

    def upsert(self, row: dict[str, Any]) -> None:
        self._load()
        normalized = self._normalize_row(row)
        key = tuple(normalized[column] for column in self.key_columns)
        existing = self.rows_by_key.get(key)
        if existing == normalized:
            if self.needs_rewrite:
                self._rewrite()
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.needs_rewrite:
            if existing is None:
                self.rows_by_key[key] = normalized
                self.key_order.append(key)
            else:
                self.rows_by_key[key] = normalized
            self._rewrite()
            return

        if existing is None:
            self.rows_by_key[key] = normalized
            self.key_order.append(key)
            file_exists = self.path.exists()
            def append_row() -> None:
                with self.path.open("a", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=self.columns, lineterminator="\n")
                    if not file_exists:
                        writer.writeheader()
                    writer.writerow(normalized)

            _run_file_io_with_retry(append_row)
            return

        self.rows_by_key[key] = normalized
        self._rewrite()


# HanchanContext を表すデータクラス。
@dataclass
class HanchanContext:
    # hanchan_id を保持する。
    hanchan_id: str
    # hanchan_date を保持する。
    hanchan_date: str
    # hanchan_start_hms を保持する。
    hanchan_start_hms: str
    # hanchan_start_epoch_ms を保持する。
    hanchan_start_epoch_ms: int
    # hanchan_id_source を保持する。
    hanchan_id_source: str
    # first_init_tag を保持する。
    first_init_tag: str
    # same_day_player_signature を保持する。
    same_day_player_signature: str
    # game_id を保持する。
    game_id: str
    # room_class_label を保持する。
    room_class_label: str
    # source_kind を保持する。
    source_kind: str


# CsvDatabase クラスを定義する。
class CsvDatabase:
    def __init__(
        self,
        db_dir: Path | None = None,
        *,
        bootstrap_logical_tables: Iterable[str] | None = None,
        async_persist: bool = False,
    ) -> None:
        self.db_dir = db_dir or DEFAULT_CSV_DB_DIR
        self.db_dir.mkdir(parents=True, exist_ok=True)
        _prime_legacy_hand_snapshot_cache(self.db_dir)
        _prime_legacy_hanchan_name_cache(self.db_dir)
        _prime_legacy_hanchan_metadata_cache(self.db_dir)
        self.spec_by_name = {spec.logical_name: spec for spec in CSV_TABLE_SPECS}
        self.file_stores: dict[tuple[str, str], CsvFileStore] = {}
        self.current_hanchan: HanchanContext | None = None
        self.current_game_id: str | None = None
        self.async_persist = bool(async_persist)
        self._async_persist_queue: queue.Queue[AsyncPersistJob | object] | None = None
        self._async_persist_worker: threading.Thread | None = None
        self._async_persist_error_text = ""

        self._archive_removed_legacy_files()
        if self.async_persist:
            self._async_persist_queue = queue.Queue()
            self._async_persist_worker = threading.Thread(
                target=self._async_persist_worker_loop,
                name="csv-db-persist",
                daemon=True,
            )
            self._async_persist_worker.start()

        logical_tables_to_bootstrap = (
            tuple(bootstrap_logical_tables)
            if bootstrap_logical_tables is not None
            else SINGLE_FILE_LOGICAL_TABLES
        )
        for logical_name in logical_tables_to_bootstrap:
            self._store(logical_name).ensure_exists()

    def close(self) -> None:
        self.wait_for_pending_writes()
        if self._async_persist_queue is None or self._async_persist_worker is None:
            return
        self._async_persist_queue.put(_ASYNC_PERSIST_STOP)
        self._async_persist_queue.join()
        self._async_persist_worker.join(timeout=5.0)
        self._async_persist_worker = None

    def _async_persist_worker_loop(self) -> None:
        """Serialize queued persist jobs so live capture never blocks on CSV writes."""

        assert self._async_persist_queue is not None
        while True:
            monitor_state: CaptureState | None = None
            queued_item = self._async_persist_queue.get()
            try:
                if queued_item is _ASYNC_PERSIST_STOP:
                    return
                assert isinstance(queued_item, AsyncPersistJob)
                monitor_state = queued_item.monitor_state
                if monitor_state is not None:
                    mark_runtime_thread_progress(
                        monitor_state,
                        "db-persist",
                        "persist_event",
                        detail=(
                            f"event={queued_item.event.event_type} "
                            f"queue={self._async_persist_queue.qsize()}"
                        ),
                        blocked_hint="background CSV persist is running",
                        stale_after_s=3.0,
                        repeat_after_s=8.0,
                    )
                self._persist_event_now(queued_item.state, queued_item.event)
            except Exception as exc:
                error_text = traceback.format_exc(limit=8).strip()
                if not self._async_persist_error_text:
                    self._async_persist_error_text = error_text
                if monitor_state is not None:
                    mark_runtime_thread_progress(
                        monitor_state,
                        "db-persist",
                        "persist_error",
                        detail=str(exc),
                        blocked_hint="background CSV persist hit an error",
                        stale_after_s=30.0,
                        repeat_after_s=60.0,
                    )
                    with monitor_state.state_lock:
                        monitor_state.diagnostics.append(
                            {
                                "level": "error",
                                "code": "async_csv_persist_failed",
                                "message": str(exc),
                                "traceback": error_text,
                            }
                        )
                        monitor_state.prune_live_history()
            finally:
                if queued_item is not _ASYNC_PERSIST_STOP and monitor_state is not None:
                    mark_runtime_thread_progress(
                        monitor_state,
                        "db-persist",
                        "idle_wait",
                        detail=f"queue={self._async_persist_queue.qsize()}",
                        blocked_hint="waiting for the next queued CSV persist job",
                        stale_after_s=20.0,
                        repeat_after_s=30.0,
                    )
                self._async_persist_queue.task_done()

    def _raise_async_persist_error_if_any(self) -> None:
        if self._async_persist_error_text:
            raise RuntimeError(self._async_persist_error_text)

    def wait_for_pending_writes(self) -> None:
        if self._async_persist_queue is not None:
            self._async_persist_queue.join()
        self._raise_async_persist_error_if_any()

    def _archive_removed_legacy_files(self) -> None:
        for pattern in LEGACY_REMOVED_FILENAME_GLOBS:
            for path in self.db_dir.glob(pattern):
                if not path.is_file():
                    continue
                archive_path = _archive_target_path(path)
                shutil.move(str(path), str(archive_path))

    def _store(self, logical_name: str, chunk_token: str = "") -> CsvFileStore:
        spec = self.spec_by_name[logical_name]
        store_key = (logical_name, chunk_token)
        if store_key in self.file_stores:
            return self.file_stores[store_key]

        if spec.split_mode == "single_file":
            path = self.db_dir / spec.filename_pattern
        else:
            if not chunk_token:
                raise ValueError(f"chunk_token is required for monthly table {logical_name}")
            path = self.db_dir / spec.filename_pattern.replace("*", chunk_token)

        store = CsvFileStore(
            path=path,
            key_columns=spec.key_columns,
            columns=spec.columns,
        )
        self.file_stores[store_key] = store
        return store

    def _ensure_player_profiles(self, state: CaptureState, _timestamp_ms: int | None) -> None:
        store = self._store("player_profiles")
        for player_name in _player_names_by_rel_seat(state):
            if not player_name:
                continue
            existing = store.get((player_name,))
            row = {
                "player_name": player_name,
                "user_memo": existing["user_memo"] if existing is not None else "",
                "analysis_memo": existing["analysis_memo"] if existing is not None else "",
                "source_url": existing["source_url"] if existing is not None else "",
            }
            store.upsert(row)

    def _upsert_player_profile_source_url_for_players(
        self,
        player_names_by_rel_seat: list[str | None],
        source_url: str | None,
    ) -> None:
        """Mirror one imported牌譜 URL into each player profile row for later opponent lookup."""

        normalized_source_url = _csv_cell(source_url).strip()
        if not normalized_source_url:
            return
        seen_names: set[str] = set()
        for player_name in player_names_by_rel_seat:
            normalized_player_name = _csv_cell(player_name).strip()
            if not normalized_player_name or normalized_player_name in seen_names:
                continue
            seen_names.add(normalized_player_name)
            self.upsert_player_profile(
                normalized_player_name,
                source_url=normalized_source_url,
            )

    def get_player_profile(self, player_name: str) -> dict[str, str]:
        store = self._store("player_profiles")
        store.ensure_exists()
        existing = store.get((player_name,))
        if existing is None:
            return {
                "player_name": player_name,
                "user_memo": "",
                "analysis_memo": "",
                "source_url": "",
            }
        return dict(existing)

    def upsert_player_profile(
        self,
        player_name: str,
        *,
        user_memo: str | None = None,
        analysis_memo: str | None = None,
        source_url: str | None = None,
    ) -> dict[str, str]:
        existing = self.get_player_profile(player_name)
        row = {
            "player_name": player_name,
            "user_memo": existing["user_memo"] if user_memo is None else user_memo,
            "analysis_memo": existing["analysis_memo"] if analysis_memo is None else analysis_memo,
            "source_url": existing["source_url"] if source_url is None else source_url,
        }
        self._store("player_profiles").upsert(row)
        return row

    def _find_hanchan_row_by_date_and_names(
        self,
        hanchan_date: str,
        player_names_by_rel_seat: list[str | None],
    ) -> dict[str, str]:
        signature = build_same_day_player_signature(hanchan_date, player_names_by_rel_seat)
        matches = [
            row
            for row in self._store("hanchan_master").iter_rows()
            if _same_day_signature_from_hanchan_row(row) == signature
        ]
        if not matches:
            raise ValueError(
                "No DB hanchan matched the XML date/player signature: "
                f"date={hanchan_date}, players={player_names_by_rel_seat}"
            )
        if len(matches) > 1:
            raise ValueError(
                "Multiple DB hanchan rows matched the same XML date/player signature: "
                f"date={hanchan_date}, players={player_names_by_rel_seat}"
            )
        return matches[0]

    def refine_unconfirmed_lagged_discards(
        self,
        *,
        hanchan_id: str | None = None,
    ) -> dict[str, int]:
        updated_rows = 0
        skipped_incomplete = 0
        already_called = 0
        confirmed_true_uncalled = 0
        confirmed_false = 0
        system_delay = 0

        chunk_tokens: set[str]
        if hanchan_id:
            chunk_tokens = {monthly_chunk_token_from_hanchan_id(hanchan_id)}
        else:
            chunk_tokens = {
                path.stem.replace("discard_fact_", "", 1)
                for path in self.db_dir.glob("discard_fact_*.csv")
                if path.is_file()
            }

        for chunk_token in sorted(chunk_tokens):
            fact_store = self._store("discard_fact", chunk_token)
            for row in list(fact_store.iter_rows()):
                if hanchan_id and row.get("hanchan_id") != hanchan_id:
                    continue
                lagged = _csv_cell(row.get("lagged", ""))
                if lagged == str(LAG_FLAG_TRUE_CALLED):
                    already_called += 1
                    continue
                if lagged != str(LAG_FLAG_UNCONFIRMED):
                    continue
                lag_delay_ms = _csv_optional_float(row.get("lag_delay_ms"))
                # Upgrade older unresolved rows into the dedicated short-delay bucket before
                # any XML-side hand-based refinement tries to classify them as true/false lag.
                if lag_delay_ms is not None and lag_delay_ms <= LAG_SYSTEM_DELAY_MAX_MS:
                    updated_row = dict(row)
                    updated_row["lagged"] = str(LAG_FLAG_SYSTEM_DELAY)
                    fact_store.upsert(updated_row)
                    updated_rows += 1
                    system_delay += 1
                    continue
                hands_by_seat = _hand_tiles_by_seat_from_fact_row(row)
                if hands_by_seat is None:
                    skipped_incomplete += 1
                    continue
                try:
                    discard_seat = int(_csv_cell(row.get("player_rel_seat", "")))
                    discard_tile_136 = int(_csv_cell(row.get("discard_tile_136", "")))
                except ValueError:
                    skipped_incomplete += 1
                    continue
                refined_flag = _refined_lag_flag_from_hands(
                    discard_seat,
                    discard_tile_136,
                    hands_by_seat,
                )
                if refined_flag == LAG_FLAG_UNCONFIRMED:
                    continue
                updated_row = dict(row)
                updated_row["lagged"] = str(refined_flag)
                fact_store.upsert(updated_row)
                updated_rows += 1
                if refined_flag == LAG_FLAG_TRUE_UNCALLED_PROBABLE:
                    confirmed_true_uncalled += 1
                elif refined_flag == LAG_FLAG_FALSE_CONFIRMED:
                    confirmed_false += 1

        return {
            "updated_rows": updated_rows,
            "skipped_incomplete": skipped_incomplete,
            "already_called": already_called,
            "confirmed_true_uncalled": confirmed_true_uncalled,
            "confirmed_false": confirmed_false,
            "system_delay": system_delay,
        }

    def import_xml_discard_hands(
        self,
        xml_text: str,
        *,
        self_abs_seat: int | None = None,
        self_player_name: str | None = None,
        hanchan_date_override: str | None = None,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        state, snapshots = load_xml_discard_snapshots(
            xml_text,
            self_abs_seat=self_abs_seat,
            self_player_name=self_player_name,
        )
        if not state.seat_mapping_resolved:
            raise ValueError(
                "XML seat mapping is unresolved. Provide self_abs_seat or self_player_name."
            )
        hanchan_date = hanchan_date_override or _extract_hanchan_date_from_game_id(state.game_id)
        if not hanchan_date:
            raise ValueError(f"Could not extract YYYYMMDD from XML game_id: {state.game_id}")

        player_names_by_rel_seat = _player_names_by_rel_seat(state)
        hanchan_row = self._find_hanchan_row_by_date_and_names(
            hanchan_date,
            player_names_by_rel_seat,
        )
        hanchan_id = hanchan_row["hanchan_id"]
        updated_hanchan_row = dict(hanchan_row)
        if source_url:
            updated_hanchan_row["source_url"] = source_url
        game_type_columns = _game_type_columns_from_state(state)
        if not any(game_type_columns.values()):
            game_type_columns = _game_type_columns_from_hanchan_row(updated_hanchan_row)
        updated_hanchan_row.update(game_type_columns)
        self._store("hanchan_master").upsert(updated_hanchan_row)
        _remember_hanchan_metadata(self.db_dir, updated_hanchan_row)
        self._upsert_player_profile_source_url_for_players(
            player_names_by_rel_seat,
            updated_hanchan_row.get("source_url"),
        )
        chunk_token = monthly_chunk_token_from_hanchan_id(hanchan_id)
        fact_store = self._store("discard_fact", chunk_token)
        kyoku_store = self._store("kyoku_master")

        updated_rows = 0
        missing_rows = 0
        mismatched_tiles = 0
        for snapshot in snapshots:
            kyoku_info = build_kyoku_info(snapshot.kyoku_index, snapshot.honba)
            if kyoku_info is None:
                continue
            kyoku_id = build_kyoku_id(hanchan_id, kyoku_info)
            existing_kyoku_row = kyoku_store.get((kyoku_id,))
            if existing_kyoku_row is not None:
                updated_kyoku_row = dict(existing_kyoku_row)
                updated_kyoku_row.update(game_type_columns)
                kyoku_store.upsert(updated_kyoku_row)
            discard_id = build_discard_id(kyoku_id, snapshot.discard_index)
            existing = fact_store.get((discard_id,))
            if existing is None:
                missing_rows += 1
                continue
            stored_tile_136 = _csv_cell(existing.get("discard_tile_136", ""))
            if stored_tile_136:
                try:
                    if int(stored_tile_136) != snapshot.discard_tile_136:
                        mismatched_tiles += 1
                        continue
                except ValueError:
                    mismatched_tiles += 1
                    continue
            updated_row = dict(existing)
            for seat in range(4):
                hand_tiles_136 = list(snapshot.hand_tiles_by_seat_136.get(seat, ()))
                hand_key_136 = f"seat{seat}_hand_tiles_136_json"
                hand_key_37 = f"seat{seat}_hand_tiles_37_text"
                if seat == 0 and _csv_cell(existing.get(hand_key_136, "")).strip():
                    if not _csv_cell(updated_row.get(hand_key_37, "")).strip():
                        existing_hand_tiles = _decode_hand_tiles_json(existing.get(hand_key_136, ""))
                        if existing_hand_tiles is not None:
                            updated_row[hand_key_37] = _hand_tiles_37_text(existing_hand_tiles)
                    continue
                updated_row[hand_key_136] = _json_text(hand_tiles_136)
                updated_row[hand_key_37] = _hand_tiles_37_text(hand_tiles_136)
            updated_row.update(game_type_columns)
            updated_row.update(_discard_analysis_columns(updated_row))
            fact_store.upsert(updated_row)
            updated_rows += 1

        lag_result = self.refine_unconfirmed_lagged_discards(hanchan_id=hanchan_id)
        return {
            "hanchan_id": hanchan_id,
            "game_id": state.game_id or "",
            "updated_rows": updated_rows,
            "missing_rows": missing_rows,
            "mismatched_tiles": mismatched_tiles,
            "lag_rows_refined": lag_result["updated_rows"],
            "lag_rows_true_uncalled": lag_result["confirmed_true_uncalled"],
            "lag_rows_false_confirmed": lag_result["confirmed_false"],
            "lag_rows_system_delay": lag_result["system_delay"],
            "lag_rows_skipped_incomplete": lag_result["skipped_incomplete"],
        }

    def _sync_current_hanchan_room_class_label(self, state: CaptureState) -> None:
        """Fill current hanchan metadata that can arrive after INIT-like storage."""

        if self.current_hanchan is None:
            return
        game_type_columns = _game_type_columns_from_state(state)
        room_class_label = _csv_cell(game_type_columns.get("room_class_label", "")).strip()
        hanchan_store = self._store("hanchan_master")
        existing_row = hanchan_store.get((self.current_hanchan.hanchan_id,))
        if existing_row is None:
            return
        updated_row = dict(existing_row)
        changed = False
        if (
            room_class_label
            and room_class_label != _csv_cell(self.current_hanchan.room_class_label).strip()
        ):
            updated_row.update(game_type_columns)
            self.current_hanchan.room_class_label = room_class_label
            changed = True
        if not _csv_cell(updated_row.get("source_url", "")).strip():
            source_url = _source_url_from_state(state)
            if source_url:
                updated_row["source_url"] = source_url
                changed = True
        if not changed:
            return
        hanchan_store.upsert(updated_row)
        _remember_hanchan_metadata(self.db_dir, updated_row)
        if state.game_id:
            self.current_hanchan.game_id = state.game_id

    def _ensure_hanchan_context(
        self,
        state: CaptureState,
        event: Event,
    ) -> HanchanContext | None:
        if state.game_id and self.current_game_id and state.game_id != self.current_game_id:
            self.current_hanchan = None

        if (
            self.current_hanchan is not None
            and event.event_type in INIT_LIKE_EVENT_TYPES
            and event.timestamp is not None
        ):
            hanchan_date, _hanchan_start_hms, _ = _timestamp_parts(event.timestamp)
            if hanchan_date:
                signature = build_same_day_player_signature(
                    hanchan_date,
                    _player_names_by_rel_seat(state),
                )
                if signature != self.current_hanchan.same_day_player_signature:
                    self.current_hanchan = None

        if self.current_hanchan is not None:
            self._sync_current_hanchan_room_class_label(state)
            self.current_game_id = state.game_id or self.current_hanchan.game_id
            return self.current_hanchan

        if event.event_type not in INIT_LIKE_EVENT_TYPES:
            return None
        if event.timestamp is None:
            return None

        hanchan_date, hanchan_start_hms, _ = _timestamp_parts(event.timestamp)
        if not hanchan_date or not hanchan_start_hms:
            return None

        player_names = _player_names_by_rel_seat(state)
        signature = build_same_day_player_signature(hanchan_date, player_names)
        hanchan_store = self._store("hanchan_master")
        existing_by_id: dict[str, str] | None = None
        existing_by_signature = next(
            (
                row
                for row in hanchan_store.iter_rows()
                if _same_day_signature_from_hanchan_row(row) == signature
            ),
            None,
        )

        use_initbylog_fallback = event.event_type in {"initbylog", "wgc"}
        if existing_by_signature is not None:
            hanchan_id = existing_by_signature["hanchan_id"]
            start_epoch_ms = _csv_cell(_timestamp_to_epoch_ms(event.timestamp))
            hanchan_id_source = "initbylog_fallback" if use_initbylog_fallback else "init_timestamp"
            first_init_tag = event.raw_tag or event.event_type
        else:
            hanchan_id = build_hanchan_id(
                hanchan_date,
                hanchan_start_hms,
                use_initbylog_fallback=use_initbylog_fallback,
            )
            existing_by_id = hanchan_store.get((hanchan_id,))
            if (
                existing_by_id is not None
                and _same_day_signature_from_hanchan_row(existing_by_id) != signature
            ):
                raise ValueError(
                    f"INITBYLOG fallback hanchan_id collision: {hanchan_id} "
                    f"for signatures {_same_day_signature_from_hanchan_row(existing_by_id)} and {signature}"
                )
            start_epoch_ms = _csv_cell(_timestamp_to_epoch_ms(event.timestamp))
            hanchan_id_source = "initbylog_fallback" if use_initbylog_fallback else "init_timestamp"
            first_init_tag = event.raw_tag or event.event_type

        game_type_columns = _game_type_columns_from_state(state)
        if not any(game_type_columns.values()) and existing_by_signature is not None:
            game_type_columns = _game_type_columns_from_hanchan_row(existing_by_signature)
        existing_source_url = ""
        if existing_by_signature is not None:
            existing_source_url = _csv_cell(existing_by_signature.get("source_url", "")).strip()
        elif existing_by_id is not None:
            existing_source_url = _csv_cell(existing_by_id.get("source_url", "")).strip()

        row = {
            "hanchan_id": hanchan_id,
            **game_type_columns,
            "seat0_player_name": player_names[0] or "",
            "seat1_player_name": player_names[1] or "",
            "seat2_player_name": player_names[2] or "",
            "seat3_player_name": player_names[3] or "",
            "source_url": existing_source_url or _source_url_from_state(state),
        }
        hanchan_store.upsert(row)
        _remember_hanchan_metadata(self.db_dir, row)

        self.current_game_id = state.game_id
        self.current_hanchan = HanchanContext(
            hanchan_id=hanchan_id,
            hanchan_date=hanchan_date,
            hanchan_start_hms=hanchan_start_hms,
            hanchan_start_epoch_ms=int(start_epoch_ms),
            hanchan_id_source=hanchan_id_source,
            first_init_tag=first_init_tag,
            same_day_player_signature=signature,
            game_id=state.game_id or "",
            room_class_label=row["room_class_label"],
            source_kind=state.source_kind,
        )
        return self.current_hanchan

    def _ensure_kyoku_row(
        self,
        state: CaptureState,
        hanchan: HanchanContext,
    ) -> tuple[str, str] | None:
        round_state = state.current_round
        if round_state is None:
            return None

        kyoku_info = build_kyoku_info(round_state.kyoku_index, round_state.honba)
        if kyoku_info is None:
            return None

        kyoku_id = build_kyoku_id(hanchan.hanchan_id, kyoku_info)
        kyoku_store = self._store("kyoku_master")
        player_names = _player_names_by_rel_seat(state)
        first_row_average_ms_by_seat = round_first_row_thinking_average_ms_by_seat(
            round_state
        )
        kyoku_store.upsert(
            {
                "kyoku_id": kyoku_id,
                "hanchan_id": hanchan.hanchan_id,
                "room_class_label": hanchan.room_class_label,
                "honba": round_state.honba,
                "kyotaku": round_state.kyotaku,
                "oya_rel": round_state.oya,
                "seat0_player_name": player_names[0] or "",
                "seat1_player_name": player_names[1] or "",
                "seat2_player_name": player_names[2] or "",
                "seat3_player_name": player_names[3] or "",
                "oya_player_name": _player_name(state, round_state.oya),
                "seat0_first_row_avg_thinking_time_ms": first_row_average_ms_by_seat.get(0, ""),
                "seat1_first_row_avg_thinking_time_ms": first_row_average_ms_by_seat.get(1, ""),
                "seat2_first_row_avg_thinking_time_ms": first_row_average_ms_by_seat.get(2, ""),
                "seat3_first_row_avg_thinking_time_ms": first_row_average_ms_by_seat.get(3, ""),
            }
        )
        return kyoku_id, kyoku_info

    def _discard_fact_row(
        self,
        state: CaptureState,
        event: Event,
        seat: int,
        discard: Discard,
        hanchan: HanchanContext,
        kyoku_id: str,
        kyoku_info: str,
        round_state: RoundState,
    ) -> dict[str, Any]:
        thinking_time_ms, thinking_time_before_reach_ms = _analysis_thinking_time_values(discard)
        discard_hand_tiles_136 = (
            list(discard.hand_tiles_before_discard_136)
            if discard.hand_tiles_before_discard_136
            else list(round_state.current_hands_136.get(seat, []))
        )
        row = {
            "discard_id": build_discard_id(kyoku_id, discard.round_discard_index or 0),
            "kyoku_id": kyoku_id,
            "hanchan_id": hanchan.hanchan_id,
            "room_class_label": hanchan.room_class_label,
            "player_rel_seat": seat,
            "player_name": _player_name(state, seat),
            "discard_tile_136": discard.tile_136,
            "discard_tile_37_text": tile136_to_tile37_text(discard.tile_136) or "",
            "tsumogiri_flag": discard.tsumogiri_flag,
            "discard_epoch_s": _timestamp_to_epoch_s(event.timestamp),
            "thinking_time_ms": thinking_time_ms,
            "thinking_time_before_reach_ms": thinking_time_before_reach_ms,
            "lagged": discard.lagged,
            "lag_delay_ms": discard.lag_delay_ms,
            **_hand_snapshot_columns(round_state, discard_seat=seat, discard=discard),
            **_pystyle_history_columns_from_state(
                state,
                round_state,
                seat,
                int(discard.round_discard_index or 0),
                discard_hand_tiles_136,
            ),
        }
        row.update(_discard_analysis_columns(row))
        return row

    def _discard_context_row(
        self,
        round_state: RoundState,
        kyoku_id: str,
        discard: Discard,
    ) -> dict[str, Any]:
        return {
            "discard_id": build_discard_id(kyoku_id, discard.round_discard_index or 0),
            "kyoku_id": kyoku_id,
            "scores_json": _json_text(round_state.scores),
            "reach_state_json": _json_text(round_state.reach_state),
            "dora_indicators_136_json": _json_text(round_state.dora_indicators_136),
            "melds_by_seat_json": _json_text(
                {
                    str(seat): [asdict(meld) for meld in melds]
                    for seat, melds in round_state.melds.items()
                }
            ),
            "rivers_by_seat_136_json": _json_text(
                {
                    str(seat): [seat_discard.tile_136 for seat_discard in discards]
                    for seat, discards in round_state.discards.items()
                }
            ),
            "visible_tile_counts_34_json": _json_text(_visible_tile_counts_34(round_state)),
        }

    def _agari_fact_row(
        self,
        state: CaptureState,
        event: Event,
        hanchan: HanchanContext,
        kyoku_id: str,
        kyoku_info: str,
        round_state: RoundState,
    ) -> dict[str, Any]:
        agari_event_index = _event_index_for(state, event)
        if agari_event_index is None:
            agari_event_index = max(0, len(state.events) - 1)

        winner_seat = _int_event_attr(event, "who")
        from_seat = _int_event_attr(event, "fromWho")
        is_tsumo = bool(event.attrs.get("is_tsumo"))
        try:
            ron_columns, deal_in_discard = _build_agari_ron_danger_columns(
                state,
                round_state,
                event,
                kyoku_id,
            )
        except Exception as exc:
            # Ron-danger estimation is best-effort. Keep live DB persistence running even when
            # one hand has inconsistent end-of-round state and surface the failure as a warning.
            with state.state_lock:
                state.diagnostics.append(
                    {
                        "level": "warning",
                        "code": "agari_ron_danger_estimate_failed",
                        "message": str(exc),
                        "kyoku_id": kyoku_id,
                        "agari_event_index": agari_event_index,
                        "traceback": traceback.format_exc(limit=6),
                    }
                )
                state.prune_live_history()
            ron_columns = _empty_agari_ron_danger_columns()
            deal_in_discard = None
        winning_tile_136 = _int_event_attr(event, "machi")
        if winning_tile_136 is None and deal_in_discard is not None:
            winning_tile_136 = deal_in_discard.tile_136
        return {
            "agari_id": f"{kyoku_id}_agari_{agari_event_index:03d}",
            "kyoku_id": kyoku_id,
            "hanchan_id": hanchan.hanchan_id,
            "room_class_label": hanchan.room_class_label,
            "agari_epoch_s": _timestamp_to_epoch_s(event.timestamp),
            "winner_rel_seat": winner_seat,
            "winner_name": _player_name(state, winner_seat),
            "from_rel_seat": from_seat,
            "from_name": _player_name(state, from_seat),
            "is_tsumo": is_tsumo,
            "winning_tile_136": winning_tile_136,
            "winning_tile_37_text": (
                tile136_to_tile37_text(winning_tile_136) or ""
                if winning_tile_136 is not None
                else ""
            ),
            "agari_state_snapshot_json": _build_agari_state_snapshot_json(state, round_state),
            **ron_columns,
        }

    def _persist_discard_snapshot(
        self,
        state: CaptureState,
        round_state: RoundState,
        seat: int,
        discard: Discard,
        hanchan: HanchanContext,
        kyoku_id: str,
        kyoku_info: str,
    ) -> None:
        discard_event = _discard_event_for(state, discard)
        if discard_event is None:
            return
        chunk_token = monthly_chunk_token_from_hanchan_id(hanchan.hanchan_id)
        self._store("discard_fact", chunk_token).upsert(
            self._discard_fact_row(
                state,
                discard_event,
                seat,
                discard,
                hanchan,
                kyoku_id,
                kyoku_info,
                round_state,
            )
        )
        self._store("discard_context", chunk_token).upsert(
            self._discard_context_row(round_state, kyoku_id, discard)
        )

    def _persist_agari_snapshot(
        self,
        state: CaptureState,
        round_state: RoundState,
        event: Event,
        hanchan: HanchanContext,
        kyoku_id: str,
        kyoku_info: str,
    ) -> None:
        chunk_token = monthly_chunk_token_from_hanchan_id(hanchan.hanchan_id)
        self._store("agari_fact", chunk_token).upsert(
            self._agari_fact_row(
                state,
                event,
                hanchan,
                kyoku_id,
                kyoku_info,
                round_state,
            )
        )

    def _sync_mutable_discard_facts(
        self,
        state: CaptureState,
        round_state: RoundState,
        hanchan: HanchanContext,
        kyoku_id: str,
        kyoku_info: str,
        fallback_event: Event | None = None,
    ) -> None:
        chunk_token = monthly_chunk_token_from_hanchan_id(hanchan.hanchan_id)
        fact_store = self._store("discard_fact", chunk_token)
        for seat, discard in _observed_discards(round_state):
            discard_event = _discard_event_for_storage(
                state,
                discard,
                seat,
                fallback_event=fallback_event,
            )
            if discard_event is None:
                continue
            candidate_row = self._discard_fact_row(
                state,
                discard_event,
                seat,
                discard,
                hanchan,
                kyoku_id,
                kyoku_info,
                round_state,
            )
            existing_row = fact_store.get((candidate_row["discard_id"],))
            fact_store.upsert(_merge_preserved_discard_fact_fields(existing_row, candidate_row))

    def _persist_event_now(self, state: CaptureState, event: Event) -> None:
        round_state = state.current_round
        if round_state is None or not round_state.started_from_init_like:
            return

        event_timestamp_ms = _timestamp_to_epoch_ms(event.timestamp)
        hanchan = self._ensure_hanchan_context(state, event)
        if hanchan is None:
            return
        self._ensure_player_profiles(state, event_timestamp_ms)

        kyoku = self._ensure_kyoku_row(state, hanchan)
        if kyoku is None:
            return
        kyoku_id, kyoku_info = kyoku

        if event.event_type == "discard":
            current_discard = _find_discard_for_event(state, round_state, event)
            if current_discard is not None:
                seat, discard = current_discard
                self._persist_discard_snapshot(
                    state,
                    round_state,
                    seat,
                    discard,
                    hanchan,
                    kyoku_id,
                    kyoku_info,
                )
        elif event.event_type == "agari":
            self._persist_agari_snapshot(
                state,
                round_state,
                event,
                hanchan,
                kyoku_id,
                kyoku_info,
            )

        self._sync_mutable_discard_facts(
            state,
            round_state,
            hanchan,
            kyoku_id,
            kyoku_info,
            fallback_event=event,
        )

    def persist_event(self, state: CaptureState, event: Event) -> None:
        if event.event_type not in CSV_PERSIST_EVENT_TYPES:
            return
        if not self.async_persist:
            self._raise_async_persist_error_if_any()
            self._persist_event_now(state, event)
            return
        if self._async_persist_queue is None:
            raise RuntimeError("async persist queue was not initialized")
        snapshot = _snapshot_capture_state_for_async_persist(state, event, blocking=True)
        if snapshot is None:
            return
        snapshot_state, snapshot_event = snapshot
        mark_runtime_thread_progress(
            state,
            "db-persist",
            "queued",
            detail=(
                f"event={snapshot_event.event_type} "
                f"queue={self._async_persist_queue.qsize() + 1}"
            ),
            blocked_hint="waiting for the background CSV persist worker",
            stale_after_s=6.0,
            repeat_after_s=12.0,
        )
        self._async_persist_queue.put(
            AsyncPersistJob(
                state=snapshot_state,
                event=snapshot_event,
                monitor_state=state,
            )
        )


def initialize_db() -> CsvDatabase:
    return CsvDatabase(async_persist=True)


def persist_event(db: CsvDatabase, state: CaptureState, event: Event) -> None:
    db.persist_event(state, event)


def load_player_profile(
    player_name: str,
    db: CsvDatabase | None = None,
    *,
    db_dir: Path | None = None,
) -> dict[str, str]:
    owns_db = db is None
    database = (
        db
        if db is not None
        else CsvDatabase(
            db_dir=db_dir,
            bootstrap_logical_tables=("player_profiles",),
        )
    )
    try:
        return database.get_player_profile(player_name)
    finally:
        if owns_db:
            database.close()


def save_player_profile_user_memo(
    player_name: str,
    user_memo: str,
    db: CsvDatabase | None = None,
    *,
    db_dir: Path | None = None,
) -> dict[str, str]:
    owns_db = db is None
    database = (
        db
        if db is not None
        else CsvDatabase(
            db_dir=db_dir,
            bootstrap_logical_tables=("player_profiles",),
        )
    )
    try:
        return database.upsert_player_profile(
            player_name,
            user_memo=user_memo,
        )
    finally:
        if owns_db:
            database.close()


def import_xml_discard_hands(
    xml_text: str,
    *,
    self_abs_seat: int | None = None,
    self_player_name: str | None = None,
    hanchan_date_override: str | None = None,
    source_url: str | None = None,
    db: CsvDatabase | None = None,
    db_dir: Path | None = None,
) -> dict[str, Any]:
    owns_db = db is None
    database = db if db is not None else CsvDatabase(db_dir=db_dir)
    try:
        return database.import_xml_discard_hands(
            xml_text,
            self_abs_seat=self_abs_seat,
            self_player_name=self_player_name,
            hanchan_date_override=hanchan_date_override,
            source_url=source_url,
        )
    finally:
        if owns_db:
            database.close()
