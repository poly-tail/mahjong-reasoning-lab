from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from capture.state import (
    CaptureState,
    LAG_FLAG_TRUE_CALLED,
    LAG_FLAG_TRUE_UNCALLED_PROBABLE,
    LAG_FLAG_UNCONFIRMED,
    Meld,
    RED_TILE_IDS_136,
    RoundState,
    tile136_to_tile34_index,
)

# Relative-seat order shared by both the self-hand danger bars and opponent SUMMARY panels.
SUJI_LABEL_SEAT_ORDER = (3, 2, 1)
# SUJI_LABEL_PREFIX_BY_SEAT の対応表。
SUJI_LABEL_PREFIX_BY_SEAT = {
    3: "上",
    2: "対",
    1: "下",
}
# SUJI_LINE_NUMBER_PAIRS の並びを定義する。
SUJI_LINE_NUMBER_PAIRS = (
    (1, 4),
    (4, 7),
    (2, 5),
    (5, 8),
    (3, 6),
    (6, 9),
)
# BASE_SUJI_LINE_COUNT の定義。
BASE_SUJI_LINE_COUNT = 1.0
# LAST_TEDASHI_MATAGI_FACTOR の定義。
LAST_TEDASHI_MATAGI_FACTOR = 1.0
# PREVIOUS_TEDASHI_MATAGI_FACTOR の定義。
PREVIOUS_TEDASHI_MATAGI_FACTOR = 0.5
# EARLIER_TEDASHI_MATAGI_FACTOR の定義。
EARLIER_TEDASHI_MATAGI_FACTOR = 0.3
# TAATSU_DROP_MATAGI_COUNT の定義。
TAATSU_DROP_MATAGI_COUNT = 0.7
# EMPTY_VISIBLE_COUNTS_34 の型定義。
EMPTY_VISIBLE_COUNTS_34 = (0,) * 34
# Open chi shapes reduce specific same-suit suji lines before the final danger share is computed.
CHI_KANCHAN_LINE_FACTOR = 0.5
RED_FIVE_MATAGI_LINE_COUNT = 0.25
THREE_VISIBLE_MATAGI_FACTOR = 0.8
# CHI_PENCHAN_LINE_FACTOR の定義。
CHI_PENCHAN_LINE_FACTOR = 0.5
# CHI_RYANMEN_LINE_FACTOR の定義。
CHI_RYANMEN_LINE_FACTOR = 0.6
# Inside-to-outside tedashi progression also softens one central suji line.
INNER_TO_OUTER_LINE_FACTOR = 0.7
LOW_REMAIN_LONG_THINK_TSUMOGIRI_MAX_REMAIN_COUNT = 16.0
LOW_REMAIN_LONG_THINK_TSUMOGIRI_MIN_THINKING_TIME_MS = 2500.0
# Latest-tedashi urasuji-ryanmen is another multiplicative line correction. This is always based
# on each opponent's current latest tedashi, so it is temporary and is replaced as soon as that
# same opponent makes a newer tedashi. Only one visible-count branch can apply per line.
# 75% -> 65% -> 60%.
URASUJI_RYANMEN_BASE_FACTOR = 0.75
# URASUJI_RYANMEN_TWO_VISIBLE_FACTOR の定義。
URASUJI_RYANMEN_TWO_VISIBLE_FACTOR = 0.65
# URASUJI_RYANMEN_HEAVY_VISIBLE_FACTOR の定義。
URASUJI_RYANMEN_HEAVY_VISIBLE_FACTOR = 0.60
# Lagged skip windows increase adjacent-line danger only when the delay is long enough to suggest
# a meaningful "uke ari skip". <=1400ms and >7000ms do not receive this bonus.
LAG_DANGER_LIGHT_MAX_DELAY_MS = 2000.0
# LAG_DANGER_NO_BONUS_MAX_DELAY_MS の定義。
LAG_DANGER_NO_BONUS_MAX_DELAY_MS = 1400.0
# LAG_DANGER_BONUS_MAX_DELAY_MS の定義。
LAG_DANGER_BONUS_MAX_DELAY_MS = 7000.0
# LAG_DANGER_LIGHT_LINE_FACTOR の定義。
LAG_DANGER_LIGHT_LINE_FACTOR = 1.2
# LAG_DANGER_STRONG_LINE_FACTOR の定義。
LAG_DANGER_STRONG_LINE_FACTOR = 1.4
# Visible-count concentration is a per-tile second-stage musuji correction. It only triggers after
# the corrected musuji percentage (before ugly-wait adders) already exceeds 10%.
MUSUJI_CONCENTRATION_TRIGGER_PERCENT = 10.0
# MUSUJI_CONCENTRATION_LOW_VISIBLE_FACTOR の定義。
MUSUJI_CONCENTRATION_LOW_VISIBLE_FACTOR = 0.9
# MUSUJI_CONCENTRATION_THREE_VISIBLE_FACTOR の定義。
MUSUJI_CONCENTRATION_THREE_VISIBLE_FACTOR = 1.1
# MUSUJI_CONCENTRATION_FOUR_VISIBLE_FACTOR の定義。
MUSUJI_CONCENTRATION_FOUR_VISIBLE_FACTOR = 1.2
# MUSUJI_CONCENTRATION_FIVE_PLUS_VISIBLE_FACTOR の定義。
MUSUJI_CONCENTRATION_FIVE_PLUS_VISIBLE_FACTOR = 1.3
# UGLY_WAIT_BASE_PERCENT の定義。
UGLY_WAIT_BASE_PERCENT = 2.0
# UGLY_WAIT_KANCHAN_THIN_PERCENT の定義。
UGLY_WAIT_KANCHAN_THIN_PERCENT = 0.6
# UGLY_WAIT_SHANPON_THIN_PERCENT の定義。
UGLY_WAIT_SHANPON_THIN_PERCENT = 1.0
# UGLY_WAIT_SHANPON_TWO_VISIBLE_PERCENT の定義。
UGLY_WAIT_SHANPON_TWO_VISIBLE_PERCENT = 1.0
# UGLY_WAIT_CONCENTRATION_BONUS_PERCENT の定義。
UGLY_WAIT_CONCENTRATION_BONUS_PERCENT = 1.0
# SUJI_LINE_SUIT_SUFFIX の対応表。
SUJI_LINE_SUIT_SUFFIX = {
    0: "m",
    1: "p",
    2: "s",
}
PUSH_ALERT_PERCENT_THRESHOLD = 9.0
PUSH_ALERT_PERCENT_THRESHOLD_AGAINST_RIICHI = 6.0
PUSH_ALERT_MAX_TARGET_REMAIN_COUNT = 13.0
LATE_HONOR_SHONPAI_PUSH_MIN_TURN = 8
MENZEN_ALERT_YELLOW_SCORE = 3
MENZEN_ALERT_RED_SCORE = 5
HAND_PATTERN_ALERT_YELLOW_LEVEL = 1
HAND_PATTERN_ALERT_RED_LEVEL = 2
SUIT_BIAS_ALERT_GAP_THRESHOLD = 2.5
NO_TEMP_REMAIN_RED_TINT_THRESHOLD = 13.0
OPEN_HAND_TENPAI_BASE_PERCENT_BY_MELD_COUNT = {1: 40.0, 2: 60.0}
OPEN_HAND_TENPAI_THREE_PLUS_BASE_PERCENT = 80.0
POST_CALL_TEDASHI_TENPAI_INCREMENT_PERCENT = 10.0
OPEN_HAND_PUSH_TENPAI_INCREMENT_PERCENT = 15.0
MENZEN_PUSH_TENPAI_BASE_PERCENT = 70.0
MENZEN_PUSH_TENPAI_INCREMENT_PERCENT = 15.0
DEFAULT_TENPAI_PROBABILITY_PERCENT = 20.0
RED_TINT_TENPAI_FLOOR_BASE_PERCENT = 35.0
RED_TINT_TENPAI_FLOOR_INCREMENT_PERCENT = 5.0
MAX_TENPAI_PROBABILITY_PERCENT = 100.0
LATEST_TEDASHI_SUJI_UGLY_WAIT_BASE_PERCENT = 8.0
LATEST_TEDASHI_SUJI_UGLY_WAIT_REMAIN_REFERENCE_COUNT = 10.0
LATEST_TEDASHI_SUJI_UGLY_WAIT_REMAIN_STEP_PERCENT = 2.0
LATEST_TEDASHI_SUJI_UGLY_WAIT_MIN_PERCENT = 2.0
# Latest-tedashi "space thinning" only applies to the inner-side tiles of 2/3/4/6/7/8.
# 5 has no unique inner direction, while 1/9 are edge tiles and do not trigger this correction.
LATEST_TEDASHI_SPACE_THIN_NUMBERS = {
    2: (3, 4),
    3: (4, 5),
    4: (5, 6),
    6: (5, 4),
    7: (6, 5),
    8: (7, 6),
}


def _safe_int(value: object) -> int | None:
    """Return one integer when coercion succeeds, else `None`."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: object) -> float | None:
    """Return one float when coercion succeeds, else `None`."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _danger_suji_runtime_cache(round_state: RoundState) -> dict[str, Any]:
    """Return the mutable per-round incremental cache used by danger/tint helpers."""

    bootstrap_sequence = int(getattr(round_state, "snapshot_bootstrap_sequence", 0) or 0)
    cache = getattr(round_state, "_danger_suji_runtime_cache", None)
    if not isinstance(cache, dict) or int(cache.get("bootstrap_sequence", -1)) != bootstrap_sequence:
        cache = {
            "bootstrap_sequence": bootstrap_sequence,
            "meld_signature": (),
            "tedashi_source_count_by_seat": {seat: 0 for seat in range(4)},
            "tedashi_last_source_discard_id_by_seat": {seat: 0 for seat in range(4)},
            "tedashi_discards_by_seat": {seat: [] for seat in range(4)},
            "tedashi_tiles_by_seat": {seat: [] for seat in range(4)},
            "red_tint_processed_discard_count_by_seat": {seat: 0 for seat in range(4)},
            "red_tint_last_processed_discard_id_by_seat": {seat: 0 for seat in range(4)},
            "red_tint_previous_no_temp_remain_by_seat": {seat: 18.0 for seat in range(4)},
            "red_tint_highlight_started_by_seat": {seat: False for seat in range(4)},
            "red_tint_highlight_indices_by_seat": {seat: [] for seat in range(4)},
            "red_tint_no_temp_remain_cache_by_seat": {seat: {} for seat in range(4)},
            "red_tint_inner_highest_seen_bucket_by_seat": {
                seat: {0: -1, 1: -1, 2: -1}
                for seat in range(4)
            },
            "red_tint_seen_suited_numbers_by_seat": {
                seat: {0: set(), 1: set(), 2: set()}
                for seat in range(4)
            },
        }
        setattr(round_state, "_danger_suji_runtime_cache", cache)
    return cache


def _danger_suji_meld_signature(round_state: RoundState) -> tuple[tuple[int, int, int], ...]:
    """Return one lightweight signature that changes when meld state may rewrite old discard flags."""

    return tuple(
        (
            seat,
            len(round_state.melds.get(seat, ())),
            (
                id(round_state.melds.get(seat, ())[-1])
                if round_state.melds.get(seat, ())
                else 0
            ),
        )
        for seat in range(4)
    )


def _reset_tedashi_history_cache_for_seat(cache: dict[str, Any], seat: int) -> None:
    """Drop one seat's cached tedashi histories."""

    cache["tedashi_source_count_by_seat"][seat] = 0
    cache["tedashi_last_source_discard_id_by_seat"][seat] = 0
    cache["tedashi_discards_by_seat"][seat] = []
    cache["tedashi_tiles_by_seat"][seat] = []


def _reset_red_tint_cache_for_seat(cache: dict[str, Any], seat: int) -> None:
    """Drop one seat's incremental red-tint state."""

    cache["red_tint_processed_discard_count_by_seat"][seat] = 0
    cache["red_tint_last_processed_discard_id_by_seat"][seat] = 0
    cache["red_tint_previous_no_temp_remain_by_seat"][seat] = 18.0
    cache["red_tint_highlight_started_by_seat"][seat] = False
    cache["red_tint_highlight_indices_by_seat"][seat] = []
    cache["red_tint_no_temp_remain_cache_by_seat"][seat] = {}
    cache["red_tint_inner_highest_seen_bucket_by_seat"][seat] = {0: -1, 1: -1, 2: -1}
    cache["red_tint_seen_suited_numbers_by_seat"][seat] = {0: set(), 1: set(), 2: set()}


def _refresh_danger_suji_incremental_cache(round_state: RoundState) -> dict[str, Any]:
    """Return one valid runtime cache, resetting incremental state when meld history changed."""

    cache = _danger_suji_runtime_cache(round_state)
    meld_signature = _danger_suji_meld_signature(round_state)
    if cache.get("meld_signature") != meld_signature:
        for seat in range(4):
            _reset_tedashi_history_cache_for_seat(cache, seat)
            _reset_red_tint_cache_for_seat(cache, seat)
        cache["meld_signature"] = meld_signature
    return cache


def _ensure_tedashi_history_cache(round_state: RoundState, seat: int) -> dict[str, Any]:
    """Extend one seat's tedashi history cache only for newly observed discards."""

    cache = _refresh_danger_suji_incremental_cache(round_state)
    discards = tuple(round_state.discards.get(seat, ()))
    source_count = int(cache["tedashi_source_count_by_seat"].get(seat, 0) or 0)
    if source_count > len(discards):
        _reset_tedashi_history_cache_for_seat(cache, seat)
        source_count = 0
    last_source_discard_id = int(cache["tedashi_last_source_discard_id_by_seat"].get(seat, 0) or 0)
    if source_count > 0 and id(discards[source_count - 1]) != last_source_discard_id:
        _reset_tedashi_history_cache_for_seat(cache, seat)
        source_count = 0
    tedashi_discards = list(cache["tedashi_discards_by_seat"].get(seat, ()))
    tedashi_tiles = list(cache["tedashi_tiles_by_seat"].get(seat, ()))
    for discard in discards[source_count:]:
        if discard.tsumogiri:
            continue
        if discard.tile_34 is None:
            continue
        tedashi_discards.append(discard)
        tedashi_tiles.append(discard.tile_34)
    cache["tedashi_source_count_by_seat"][seat] = len(discards)
    cache["tedashi_last_source_discard_id_by_seat"][seat] = id(discards[-1]) if discards else 0
    cache["tedashi_discards_by_seat"][seat] = tedashi_discards
    cache["tedashi_tiles_by_seat"][seat] = tedashi_tiles
    return cache


# Immutable transport objects passed from logic into the renderer.
@dataclass(frozen=True)
class OpponentSujiDangerProfile:
    """Per-opponent suji danger weights over the 34-tile space."""

    # seat を保持する。
    seat: int
    # tile_weights_34 の並びを保持する。
    tile_weights_34: tuple[float, ...]
    # corrected_musuji_count を保持する。
    corrected_musuji_count: float
    # safe_tile34 の集合。
    safe_tile34: frozenset[int]
    # line_weights の並びを保持する。
    line_weights: tuple[tuple[int, int, int, float], ...] = ()
    # visible_counts_34 の並びを保持する。
    visible_counts_34: tuple[int, ...] = EMPTY_VISIBLE_COUNTS_34
    # ugly_wait_add_percent_34 の並びを保持する。
    ugly_wait_add_percent_34: tuple[float, ...] = EMPTY_VISIBLE_COUNTS_34


@dataclass(frozen=True)
class TileDangerMetric:
    """One seat's danger result for one candidate tile."""

    # percentage を保持する。
    percentage: int
    # numerator_count を保持する。
    numerator_count: float
    # denominator_count を保持する。
    denominator_count: float
    # base_percentage を保持する。
    base_percentage: int = 0
    # ugly_wait_percentage を保持する。
    ugly_wait_percentage: float = 0.0


@dataclass(frozen=True)
class OpponentSujiPanelSummary:
    """Panel-facing summary for one opponent's current suji state."""

    # seat を保持する。
    seat: int
    # denominator_count を保持する。
    denominator_count: float
    # top_line_labels の並びを保持する。
    top_line_labels: tuple[str, ...]
    # top_line_summaries の並びを保持する。
    top_line_summaries: tuple["OpponentSujiPanelLineSummary", ...] = ()
    # denominator_count_without_temporary_safe を保持する。
    denominator_count_without_temporary_safe: float | None = None
    # menzen_alert_score を保持する。
    menzen_alert_score: int = 0
    # hand_pattern_alert_level を保持する。
    hand_pattern_alert_level: int = 0
    # suit_bias_alert を保持する。
    suit_bias_alert: bool = False
    # ryanmen_chi_central_tedashi_alert を保持する。
    ryanmen_chi_central_tedashi_alert: bool = False
    # tedashi_thinking_rise_alert を保持する。
    tedashi_thinking_rise_alert: bool = False
    # tenpai_probability を保持する。
    tenpai_probability: float = 0.0
    # top_safe_hand_labels の並びを保持する。
    top_safe_hand_labels: tuple[str, ...] = ()
    # top_tile_rank_labels の並びを保持する。
    top_tile_rank_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpponentSujiPanelLineSummary:
    """One player-panel `Line` row with tile endpoints and same-suit remaining count."""

    rank_text: str
    left_tile_label: str
    right_tile_label: str
    suit_label: str
    line_weight_text: str
    percent_text: str
    suit_remaining_count_text: str


@dataclass(frozen=True)
class PlayerPushAlertSummary:
    """Panel-facing push-alert state for one player's latest discard."""

    seat: int
    percentage: float = 0.0
    tile_34: int | None = None
    tile_label: str = ""
    discard_index: int | None = None
    is_current: bool = False
    threshold_percent: float = PUSH_ALERT_PERCENT_THRESHOLD
    target_seats: tuple[int, ...] = ()
    exact_safe_target_seats: tuple[int, ...] = ()


def _tile34_to_suit_and_number(tile_34: int | None) -> tuple[int, int] | None:
    """Return `(suit_index, suit_number)` for suited tiles, else `None`."""

    if tile_34 is None or not 0 <= tile_34 < 27:
        return None
    return tile_34 // 9, tile_34 % 9 + 1


def _tile34_from_suit_and_number(suit_index: int, suit_number: int) -> int:
    """Build a 34-tile index from suit and 1..9 number."""

    return suit_index * 9 + (suit_number - 1)


def _format_suji_line_label(line_key: tuple[int, int, int]) -> str:
    """Format one suji line key as `3-6m` / `4-7p` / `2-5s`."""

    suit_index, left_number, right_number = line_key
    return f"{left_number}-{right_number}{SUJI_LINE_SUIT_SUFFIX.get(suit_index, '?')}"


def _format_suji_line_weight(line_weight: float) -> str:
    """Format one suji-line weight like `1`, `0.5`, or `0.4`."""

    rounded_weight = round(max(0.0, float(line_weight)), 1)
    return f"{rounded_weight:.1f}".rstrip("0").rstrip(".")


def _format_suji_line_percent(
    line_weight: float,
    denominator_count: float,
) -> str:
    """Format one suji-line share as a compact percentage string."""

    if denominator_count <= 0.0:
        return "0%"
    return f"{int(round(max(0.0, float(line_weight)) / denominator_count * 100.0))}%"


def _suit_remaining_count_by_suit(
    line_weights: Mapping[tuple[int, int, int], float],
) -> tuple[float, float, float]:
    """Return current weighted remaining suji counts for man/pin/sou."""

    unresolved_count_by_suit = [0.0, 0.0, 0.0]
    for (suit_index, _left_number, _right_number), line_weight in line_weights.items():
        if 0 <= suit_index < len(unresolved_count_by_suit):
            unresolved_count_by_suit[suit_index] += max(0.0, float(line_weight))
    return tuple(unresolved_count_by_suit)


def _format_tile34_label(tile_34: int) -> str:
    """Format one canonical 34-tile index as `1m` / `9s` / `7z`."""

    suited_tile = _tile34_to_suit_and_number(tile_34)
    if suited_tile is not None:
        suit_index, suit_number = suited_tile
        return f"{suit_number}{SUJI_LINE_SUIT_SUFFIX.get(suit_index, '?')}"
    return f"{tile_34 - 26}z"


def _format_composite_percent(percent_value: float) -> str:
    """Format danger percentages while preserving 0.6-style adjustments when needed."""

    normalized = max(0.0, float(percent_value))
    return f"{normalized:.1f}".rstrip("0").rstrip(".") + "%"


def _normalize_visible_counts_34(
    visible_counts_34: Sequence[int] | None,
) -> tuple[int, ...]:
    """Normalize caller-provided visible-count arrays into a fixed 34-entry tuple."""

    if visible_counts_34 is None:
        return EMPTY_VISIBLE_COUNTS_34
    normalized = [0] * 34
    for tile_34 in range(min(len(visible_counts_34), 34)):
        try:
            normalized[tile_34] = max(0, int(visible_counts_34[tile_34]))
        except (TypeError, ValueError):
            normalized[tile_34] = 0
    return tuple(normalized)


def _hand_tile34_counts_from_tile136(hand_tiles_136: Sequence[int]) -> tuple[int, ...]:
    """Count self-hand tiles in canonical 34-kind space for concentration corrections."""

    counts = [0] * 34
    for tile_136 in hand_tiles_136:
        tile_34 = tile136_to_tile34_index(tile_136)
        if tile_34 is None:
            continue
        counts[tile_34] += 1
    return tuple(counts)


def _matagi_line_pairs_for_number(suit_number: int | None) -> tuple[tuple[int, int], ...]:
    """Return matagi-affected suji line pairs for one suited tedashi number."""

    normalized_suit_number = _safe_int(suit_number)
    if normalized_suit_number is None:
        return ()
    line_pairs: list[tuple[int, int]] = []
    if 1 <= normalized_suit_number - 2 and normalized_suit_number + 1 <= 9:
        line_pairs.append((normalized_suit_number - 2, normalized_suit_number + 1))
    if 1 <= normalized_suit_number - 1 and normalized_suit_number + 2 <= 9:
        line_pairs.append((normalized_suit_number - 1, normalized_suit_number + 2))
    return tuple(line_pairs)


def _matagi_factor_by_followup_tedashi_count(followup_tedashi_count: int) -> float:
    """Return the count factor for one matagi line from later tedashi distance."""

    if followup_tedashi_count <= 0:
        return LAST_TEDASHI_MATAGI_FACTOR
    if followup_tedashi_count == 1:
        return PREVIOUS_TEDASHI_MATAGI_FACTOR
    return EARLIER_TEDASHI_MATAGI_FACTOR


def _matagi_line_count(
    followup_tedashi_count: int,
    *,
    taatsu_drop_softened: bool = False,
    red_five_discarded: bool = False,
    visible_count: int = 0,
) -> float:
    """Return the counted line amount for one matagi candidate."""

    if visible_count >= 4:
        return 0.0
    if red_five_discarded:
        line_count = RED_FIVE_MATAGI_LINE_COUNT
    else:
        # Representative cut-order handling: once a later tedashi pair clearly drops one taatsu,
        # earlier matagi lines are treated as 70% counts instead of aging down to 50% / 30%.
        if taatsu_drop_softened and followup_tedashi_count > 0:
            line_count = TAATSU_DROP_MATAGI_COUNT
        else:
            line_count = BASE_SUJI_LINE_COUNT * _matagi_factor_by_followup_tedashi_count(
                followup_tedashi_count
            )
    if visible_count == 3:
        return line_count * THREE_VISIBLE_MATAGI_FACTOR
    return line_count


def _representative_taatsu_drop_second_index(
    tedashi_history: Sequence[object],
) -> int | None:
    """Return the latest nearby same-suit tedashi that confirms a representative taatsu drop."""

    latest_second_index: int | None = None
    for history_index in range(1, len(tedashi_history)):
        previous_item = tedashi_history[history_index - 1]
        current_item = tedashi_history[history_index]
        previous_tile_34 = getattr(previous_item, "tile_34", previous_item)
        current_tile_34 = getattr(current_item, "tile_34", current_item)
        previous_suited_tile = _tile34_to_suit_and_number(previous_tile_34)
        current_suited_tile = _tile34_to_suit_and_number(current_tile_34)
        if previous_suited_tile is None or current_suited_tile is None:
            continue
        if previous_suited_tile[0] != current_suited_tile[0]:
            continue
        if abs(previous_suited_tile[1] - current_suited_tile[1]) not in {1, 2}:
            continue
        previous_discard_index = _safe_int(getattr(previous_item, "round_discard_index", None))
        current_discard_index = _safe_int(getattr(current_item, "round_discard_index", None))
        if previous_discard_index is None:
            previous_discard_index = _safe_int(getattr(previous_item, "event_index", None))
        if current_discard_index is None:
            current_discard_index = _safe_int(getattr(current_item, "event_index", None))
        if (
            previous_discard_index is not None
            and current_discard_index is not None
            and (current_discard_index - previous_discard_index) >= 3
        ):
            continue
        latest_second_index = history_index
    return latest_second_index


def _line_keys_including_number(
    suit_index: int | None,
    suit_number: int | None,
) -> tuple[tuple[int, int, int], ...]:
    """Return every suji line key that contains the given suit number."""

    normalized_suit_index = _safe_int(suit_index)
    normalized_suit_number = _safe_int(suit_number)
    if normalized_suit_index is None or normalized_suit_number is None:
        return ()
    return tuple(
        (normalized_suit_index, left_number, right_number)
        for left_number, right_number in SUJI_LINE_NUMBER_PAIRS
        if normalized_suit_number in (left_number, right_number)
    )


def _line_key_from_left_number(
    suit_index: int | None,
    left_number: int | None,
) -> tuple[int, int, int] | None:
    """Build one suji line key from its left-side number when it exists."""

    normalized_suit_index = _safe_int(suit_index)
    normalized_left_number = _safe_int(left_number)
    if normalized_suit_index is None or normalized_left_number is None:
        return None
    if not 1 <= normalized_left_number <= 6:
        return None
    return (normalized_suit_index, normalized_left_number, normalized_left_number + 3)


def _multiply_line_factor(
    line_factors: dict[tuple[int, int, int], float],
    line_key: tuple[int, int, int] | None,
    factor: float,
) -> None:
    """Multiply one line's count factor across competing heuristic sources."""

    if line_key is None:
        return
    previous_factor = line_factors.get(line_key, 1.0)
    line_factors[line_key] = previous_factor * factor


# Chi-shape helpers: normalize one open chi into a wait shape, then convert that wait shape into
# per-line count factors. These factors are applied only after unresolved-line detection and
# matagi count assignment.
def _chi_wait_shape(meld: Meld) -> tuple[int, int, int, str] | None:
    """Return `(suit_index, start_number, called_offset, wait_kind)` for one chi meld."""

    if meld.meld_type != "chi" or meld.called_tile_id is None or len(meld.tiles_34) != 3:
        return None

    suited_tiles = [_tile34_to_suit_and_number(tile_34) for tile_34 in meld.tiles_34]
    if any(suited_tile is None for suited_tile in suited_tiles):
        return None
    suit_index = suited_tiles[0][0]
    if any(suited_tile[0] != suit_index for suited_tile in suited_tiles):
        return None

    sorted_numbers = sorted(suited_tile[1] for suited_tile in suited_tiles)
    start_number = sorted_numbers[0]
    if sorted_numbers != [start_number, start_number + 1, start_number + 2]:
        return None

    called_tile_34 = tile136_to_tile34_index(meld.called_tile_id)
    called_suited_tile = _tile34_to_suit_and_number(called_tile_34)
    if called_suited_tile is None or called_suited_tile[0] != suit_index:
        return None
    called_offset = called_suited_tile[1] - start_number
    if called_offset not in (0, 1, 2):
        return None

    if called_offset == 1:
        return suit_index, start_number, called_offset, "kanchan"
    if (start_number == 1 and called_offset == 2) or (start_number == 7 and called_offset == 0):
        return suit_index, start_number, called_offset, "penchan"
    return suit_index, start_number, called_offset, "ryanmen"


def _chi_line_factors(
    round_state: RoundState,
    seat: int,
) -> dict[tuple[int, int, int], float]:
    """Return per-line count factors derived from the opponent's open chi shapes."""

    line_factors: dict[tuple[int, int, int], float] = {}
    for meld in round_state.melds.get(seat, []):
        chi_shape = _chi_wait_shape(meld)
        if chi_shape is None:
            continue

        suit_index, start_number, called_offset, wait_kind = chi_shape
        if wait_kind == "kanchan":
            # Kanchan chi turns the three nearby lines into 50% counted lines.
            called_number = start_number + 1
            for left_number in (called_number - 2, called_number - 1, called_number + 1):
                _multiply_line_factor(
                    line_factors,
                    _line_key_from_left_number(suit_index, left_number),
                    CHI_KANCHAN_LINE_FACTOR,
                )
            continue

        # Penchan / ryanmen both point to the single line adjacent to the side from which the chi
        # extended. Penchan counts that line at 50%, while ordinary ryanmen counts it at 60%.
        adjacent_left_number = start_number if called_offset == 0 else start_number - 1
        _multiply_line_factor(
            line_factors,
            _line_key_from_left_number(suit_index, adjacent_left_number),
            CHI_PENCHAN_LINE_FACTOR if wait_kind == "penchan" else CHI_RYANMEN_LINE_FACTOR,
        )
    return line_factors


# Inside-to-outside helpers: track tedashi progression by suit bucket and weaken only one central
# line when the player visibly moves from inner tiles toward outer tiles in the same suit.
def _inside_to_outside_bucket(suit_number: int) -> int:
    """Group suited numbers into outer / middle / inner bands for tedashi progression."""

    if suit_number in (1, 9):
        return 0
    if suit_number in (2, 8):
        return 1
    return 2


def _inside_to_outside_target_left_number(suit_number: int) -> int | None:
    """Return the central suji line that softens after an inner-to-outer tedashi move."""

    if suit_number in (1, 8):
        return 3
    if suit_number in (2, 9):
        return 4
    return None


def _inside_to_outside_line_factors(
    round_state: RoundState,
    seat: int,
) -> dict[tuple[int, int, int], float]:
    """Return per-line count factors from same-suit tedashi moving inner to outer."""

    line_factors: dict[tuple[int, int, int], float] = {}
    highest_seen_bucket_by_suit = {0: -1, 1: -1, 2: -1}
    for tile_34 in _tedashi_tile34_history(round_state, seat):
        suited_tile = _tile34_to_suit_and_number(tile_34)
        if suited_tile is None:
            continue
        suit_index, suit_number = suited_tile
        bucket = _inside_to_outside_bucket(suit_number)
        target_left_number = _inside_to_outside_target_left_number(suit_number)

        # Only true inner->outer moves apply this correction. 3..7 after 3..7, such as 5->3,
        # stays inside the same bucket and therefore does not create the new 70% count.
        if (
            target_left_number is not None
            and highest_seen_bucket_by_suit[suit_index] > bucket
        ):
            _multiply_line_factor(
                line_factors,
                _line_key_from_left_number(suit_index, target_left_number),
                INNER_TO_OUTER_LINE_FACTOR,
            )
        highest_seen_bucket_by_suit[suit_index] = max(
            highest_seen_bucket_by_suit[suit_index],
            bucket,
        )
    return line_factors


def _low_remain_long_thinking_tsumogiri_line_factors(
    round_state: RoundState,
    seat: int,
    *,
    remain_count: float,
) -> dict[tuple[int, int, int], float]:
    """Return inside->outside-style factors from low-remain long-thinking tsumogiri."""

    if remain_count > LOW_REMAIN_LONG_THINK_TSUMOGIRI_MAX_REMAIN_COUNT:
        return {}
    line_factors: dict[tuple[int, int, int], float] = {}
    for discard in round_state.discards.get(seat, []):
        if not discard.tsumogiri or discard.tile_34 is None:
            continue
        thinking_time_ms = getattr(discard, "thinking_time_ms", None)
        if thinking_time_ms is None:
            continue
        try:
            normalized_time_ms = float(thinking_time_ms)
        except (TypeError, ValueError):
            continue
        if normalized_time_ms < LOW_REMAIN_LONG_THINK_TSUMOGIRI_MIN_THINKING_TIME_MS:
            continue
        suited_tile = _tile34_to_suit_and_number(discard.tile_34)
        if suited_tile is None:
            continue
        suit_index, suit_number = suited_tile
        _multiply_line_factor(
            line_factors,
            _line_key_from_left_number(
                suit_index,
                _inside_to_outside_target_left_number(suit_number),
            ),
            INNER_TO_OUTER_LINE_FACTOR,
        )
    return line_factors


def _is_uncalled_lag_source(discard) -> bool:
    """Return whether one discard can create the next-seat lag danger heuristic."""

    if bool(getattr(discard, "is_tsumogiri_estimated", False)):
        return False
    if discard.called:
        return False
    return discard.lagged in {
        LAG_FLAG_UNCONFIRMED,
        LAG_FLAG_TRUE_UNCALLED_PROBABLE,
    }


def _is_no_lag_menzen_alert_source(discard) -> bool:
    """Return whether one discard should count toward the kamicha no-lag menzen score."""

    if bool(getattr(discard, "is_tsumogiri_estimated", False)):
        return False
    if discard.called:
        return False
    if getattr(discard, "lagged", None) == LAG_FLAG_TRUE_CALLED:
        return False
    return not _is_uncalled_lag_source(discard)


def _menzen_alert_tile_score(tile_34: int | None) -> int:
    """Return the per-kind menzen score for one suited 2-8 discard."""

    suited_tile = _tile34_to_suit_and_number(tile_34)
    if suited_tile is None:
        return 0
    _suit_index, suit_number = suited_tile
    normalized_suit_number = _safe_int(suit_number)
    if normalized_suit_number is None or not 2 <= normalized_suit_number <= 8:
        return 0
    return 3 if 3 <= normalized_suit_number <= 7 else 1


def _seat_has_open_meld(round_state: RoundState, seat: int) -> bool:
    """Return whether the target seat has already made any open meld this round."""

    return any(bool(getattr(meld, "is_open", False)) for meld in round_state.melds.get(seat, ()))


def build_kamicha_no_lag_menzen_alert_score(
    round_state: RoundState,
    seat: int,
) -> int:
    """Return one panel seat's cumulative no-lag kamicha discard score while still closed."""

    if _seat_has_open_meld(round_state, seat):
        return 0
    source_seat = (seat - 1) % 4
    score_by_tile_37: dict[int, int] = {}
    for discard in round_state.discards.get(source_seat, ()):
        if not _is_no_lag_menzen_alert_source(discard):
            continue
        tile_score = _menzen_alert_tile_score(getattr(discard, "tile_34", None))
        if tile_score <= 0:
            continue
        tile_37 = _safe_int(getattr(discard, "tile_37", None))
        if tile_37 is None or not 0 <= tile_37 < 37:
            continue
        score_by_tile_37.setdefault(tile_37, tile_score)
    return int(sum(score_by_tile_37.values()))


def build_inner_to_outer_hand_pattern_alert_level(
    round_state: RoundState,
    seat: int,
) -> int:
    """Return player-panel alert severity from progressed inner-to-outer tedashi sequences."""

    tedashi_discards = _tedashi_discard_history(round_state, seat)
    if len(tedashi_discards) < 4:
        return 0
    highest_seen_bucket_by_suit = {0: -1, 1: -1, 2: -1}
    alert_level = 0
    for history_index, discard in enumerate(tedashi_discards):
        suited_tile = _tile34_to_suit_and_number(discard.tile_34)
        if suited_tile is None:
            continue
        suit_index, suit_number = suited_tile
        bucket = _inside_to_outside_bucket(suit_number)
        previous_highest_bucket = highest_seen_bucket_by_suit[suit_index]
        target_left_number = _inside_to_outside_target_left_number(suit_number)
        if (
            target_left_number is not None
            and previous_highest_bucket > bucket
        ):
            followup_tedashi_count = len(tedashi_discards) - 1 - history_index
            if (
                previous_highest_bucket >= 2
                and followup_tedashi_count >= 2
            ) or followup_tedashi_count >= 3:
                return HAND_PATTERN_ALERT_RED_LEVEL
            if followup_tedashi_count >= 2:
                alert_level = max(alert_level, HAND_PATTERN_ALERT_YELLOW_LEVEL)
        highest_seen_bucket_by_suit[suit_index] = max(
            previous_highest_bucket,
            bucket,
        )
    return alert_level


def _is_tedashi_discard(discard) -> bool:
    """Return whether one discard is tedashi, including post-call and later-called discards."""

    return not bool(getattr(discard, "tsumogiri", False)) and getattr(discard, "tile_34", None) is not None


def _is_suited_tedashi_discard(discard) -> bool:
    """Return whether one discard is a suited tedashi, including post-call and later-called discards."""

    if not _is_tedashi_discard(discard):
        return False
    return _tile34_to_suit_and_number(discard.tile_34) is not None


def _has_prior_same_suit_taatsu_drop_neighbor(
    seen_numbers_by_suit: Mapping[int, set[int] | frozenset[int] | Sequence[int]],
    suit_index: int,
    suit_number: int,
) -> bool:
    """Return whether one earlier same-suit tedashi already sat within +/-2 numbers."""

    seen_numbers = seen_numbers_by_suit.get(int(suit_index), ())
    return any(
        abs(int(previous_number) - int(suit_number)) in {1, 2}
        for previous_number in seen_numbers
    )


def _round_state_prefix_until_discard_index(
    round_state: RoundState,
    discard_index: int,
) -> RoundState:
    """Return a shallow round-state prefix containing events visible at one discard timing."""

    prefix_state = RoundState()
    for observed_discard_index, seat, discard in _iter_global_discards(round_state):
        if observed_discard_index > discard_index:
            continue
        prefix_state.discards[seat].append(discard)
    for seat in range(4):
        for meld in round_state.melds.get(seat, ()):
            meld_event_index = _safe_int(getattr(meld, "event_index", None))
            if meld_event_index is not None and meld_event_index >= 0 and meld_event_index > discard_index:
                continue
            prefix_state.melds[seat].append(meld)
    return prefix_state


def _tenpai_probability_cache_signature(
    round_state: RoundState,
) -> tuple[tuple[object, ...], ...]:
    """Return one lightweight cache signature for the current tenpai-estimate inputs."""

    signature: list[tuple[object, ...]] = []
    for seat in range(4):
        discards = tuple(round_state.discards.get(seat, ()))
        melds = tuple(round_state.melds.get(seat, ()))
        signature.append(
            (
                seat,
                len(discards),
                id(discards[-1]) if discards else 0,
                sum(1 for discard in discards if bool(getattr(discard, "called", False))),
                sum(1 for discard in discards if getattr(discard, "riichi_marker_before", False)),
                sum(
                    1
                    for discard in discards
                    if str(getattr(discard, "thinking_time_source", "") or "").strip() == "call"
                ),
                len(melds),
                id(melds[-1]) if melds else 0,
                sum(1 for meld in melds if bool(getattr(meld, "is_open", False))),
                str(getattr(round_state, "reach_state", {}).get(seat, "")),
            )
        )
    return tuple(signature)


def _seat_has_riichi_tenpai(round_state: RoundState, seat: int) -> bool:
    """Return whether the seat should be treated as confirmed tenpai by riichi."""

    if seat in getattr(round_state, "reach_declared", set()):
        return True
    return any(
        bool(getattr(discard, "riichi_marker_before", False))
        for discard in round_state.discards.get(seat, ())
    )


def _open_meld_count(round_state: RoundState, seat: int) -> int:
    """Return one seat's current open-meld count."""

    return sum(
        1
        for meld in round_state.melds.get(seat, ())
        if bool(getattr(meld, "is_open", False))
    )


def _post_call_followup_tedashi_count(round_state: RoundState, seat: int) -> int:
    """Return tedashi count after the first observed call-tedashi for one seat."""

    saw_call_tedashi = False
    followup_tedashi_count = 0
    for discard in round_state.discards.get(seat, ()):
        if not _is_tedashi_discard(discard):
            continue
        if str(getattr(discard, "thinking_time_source", "") or "").strip() == "call":
            saw_call_tedashi = True
            continue
        if saw_call_tedashi:
            followup_tedashi_count += 1
    return followup_tedashi_count


def _red_tint_tenpai_floor_percent(
    highlighted_discard_indices: Sequence[int] | None,
) -> float:
    """Return the minimum tenpai probability implied by visible red-tint tedashi count."""

    highlighted_tedashi_count = len(highlighted_discard_indices or ())
    if highlighted_tedashi_count <= 0:
        return 0.0
    return min(
        MAX_TENPAI_PROBABILITY_PERCENT,
        RED_TINT_TENPAI_FLOOR_BASE_PERCENT
        + max(0, highlighted_tedashi_count - 1) * RED_TINT_TENPAI_FLOOR_INCREMENT_PERCENT,
    )


def _historical_push_count_by_seat(
    round_state: RoundState,
    *,
    threshold_percent: float = 9.0,
    max_target_remain_count: float = PUSH_ALERT_MAX_TARGET_REMAIN_COUNT,
) -> dict[int, int]:
    """Return per-opponent cumulative count of past 9%+ push discards in the current round."""

    cache = _danger_suji_runtime_cache(round_state)
    signature = (
        _tenpai_probability_cache_signature(round_state),
        round(float(threshold_percent), 1),
        round(float(max_target_remain_count), 1),
    )
    if cache.get("historical_push_count_signature") == signature:
        cached_counts = cache.get("historical_push_count_by_seat")
        if isinstance(cached_counts, dict):
            return {
                seat: max(0, int(cached_counts.get(seat, 0) or 0))
                for seat in SUJI_LABEL_SEAT_ORDER
            }

    push_count_by_seat = {seat: 0 for seat in SUJI_LABEL_SEAT_ORDER}
    global_discards = _iter_global_discards(round_state)
    if not global_discards:
        cache["historical_push_count_signature"] = signature
        cache["historical_push_count_by_seat"] = push_count_by_seat
        return dict(push_count_by_seat)

    prefix_state = RoundState(seat_order=list(getattr(round_state, "seat_order", (0, 1, 2, 3))))
    ordered_melds: list[tuple[int, int, Meld]] = []
    for meld_seat in range(4):
        for meld in round_state.melds.get(meld_seat, ()):
            meld_event_index = _safe_int(getattr(meld, "event_index", None))
            ordered_melds.append(
                (
                    meld_event_index if meld_event_index is not None and meld_event_index >= 0 else -1,
                    meld_seat,
                    meld,
                )
            )
    ordered_melds.sort(key=lambda item: (item[0], item[1]))
    meld_cursor = 0
    for discard_index, actor_seat, discard in global_discards:
        while meld_cursor < len(ordered_melds) and ordered_melds[meld_cursor][0] <= discard_index:
            _meld_event_index, meld_seat, meld = ordered_melds[meld_cursor]
            prefix_state.melds[meld_seat].append(meld)
            meld_cursor += 1
        prefix_state.discards[actor_seat].append(discard)
        if actor_seat not in push_count_by_seat:
            continue
        latest_push_alert = build_latest_discard_push_alert_percentages(
            prefix_state,
            threshold_percent=threshold_percent,
            max_target_remain_count=max_target_remain_count,
        ).get(actor_seat)
        if latest_push_alert is None:
            continue
        if max(0.0, float(getattr(latest_push_alert, "percentage", 0.0))) >= threshold_percent:
            push_count_by_seat[actor_seat] += 1

    cache["historical_push_count_signature"] = signature
    cache["historical_push_count_by_seat"] = push_count_by_seat
    return dict(push_count_by_seat)


def build_opponent_tenpai_probability_percentages(
    round_state: RoundState | None,
) -> dict[int, float]:
    """Estimate opponent tenpai probability percentages from riichi, meld, tedashi, and push history."""

    if round_state is None:
        return {}

    cache = _danger_suji_runtime_cache(round_state)
    signature = _tenpai_probability_cache_signature(round_state)
    if cache.get("tenpai_probability_signature") == signature:
        cached_probabilities = cache.get("tenpai_probability_by_seat")
        if isinstance(cached_probabilities, dict):
            return {
                seat: max(
                    0.0,
                    min(
                        MAX_TENPAI_PROBABILITY_PERCENT,
                        float(cached_probabilities.get(seat, 0.0)),
                    ),
                )
                for seat in SUJI_LABEL_SEAT_ORDER
            }

    probabilities_by_seat: dict[int, float] = {}
    red_tint_indices_by_seat = build_discard_red_tint_indices_by_seat(round_state)
    push_count_by_seat = _historical_push_count_by_seat(round_state)
    for seat in SUJI_LABEL_SEAT_ORDER:
        if _seat_has_riichi_tenpai(round_state, seat):
            probabilities_by_seat[seat] = MAX_TENPAI_PROBABILITY_PERCENT
            continue

        open_meld_count = _open_meld_count(round_state, seat)
        push_count = max(0, int(push_count_by_seat.get(seat, 0) or 0))
        red_tint_floor_percent = _red_tint_tenpai_floor_percent(
            red_tint_indices_by_seat.get(seat, ())
        )
        if open_meld_count <= 0:
            if push_count <= 0:
                seat_probability = DEFAULT_TENPAI_PROBABILITY_PERCENT
            else:
                seat_probability = min(
                    MAX_TENPAI_PROBABILITY_PERCENT,
                    MENZEN_PUSH_TENPAI_BASE_PERCENT
                    + max(0, push_count - 1) * MENZEN_PUSH_TENPAI_INCREMENT_PERCENT,
                )
        else:
            base_percent = OPEN_HAND_TENPAI_BASE_PERCENT_BY_MELD_COUNT.get(
                open_meld_count,
                OPEN_HAND_TENPAI_THREE_PLUS_BASE_PERCENT,
            )
            seat_probability = min(
                MAX_TENPAI_PROBABILITY_PERCENT,
                base_percent
                + _post_call_followup_tedashi_count(round_state, seat)
                * POST_CALL_TEDASHI_TENPAI_INCREMENT_PERCENT
                + push_count * OPEN_HAND_PUSH_TENPAI_INCREMENT_PERCENT,
            )

        probabilities_by_seat[seat] = max(
            seat_probability,
            red_tint_floor_percent,
        )

    cache["tenpai_probability_signature"] = signature
    cache["tenpai_probability_by_seat"] = probabilities_by_seat
    return dict(probabilities_by_seat)


def _incremental_red_tint_discard_indices(
    round_state: RoundState,
    seat: int,
) -> tuple[int, ...]:
    """Return one seat's incremental red-tint indices.

    Once any red-tint trigger fires for the seat, the seat stays latched for the rest of the
    round and every later tedashi or call-tedashi becomes a red-tint candidate. This avoids
    rerunning the trigger-family scans after the seat has already entered the red state.
    """

    cache = _refresh_danger_suji_incremental_cache(round_state)
    discards = tuple(round_state.discards.get(seat, ()))
    if not discards:
        return ()
    processed_count = int(cache["red_tint_processed_discard_count_by_seat"].get(seat, 0) or 0)
    if processed_count > len(discards):
        _reset_red_tint_cache_for_seat(cache, seat)
        processed_count = 0
    last_processed_discard_id = int(
        cache["red_tint_last_processed_discard_id_by_seat"].get(seat, 0) or 0
    )
    if processed_count > 0 and id(discards[processed_count - 1]) != last_processed_discard_id:
        _reset_red_tint_cache_for_seat(cache, seat)
        processed_count = 0

    highlight_started = bool(cache["red_tint_highlight_started_by_seat"].get(seat, False))
    highlighted_indices = list(cache["red_tint_highlight_indices_by_seat"].get(seat, ()))
    previous_no_temp_remain_count = float(
        cache["red_tint_previous_no_temp_remain_by_seat"].get(seat, 18.0) or 18.0
    )
    remain_count_cache = dict(cache["red_tint_no_temp_remain_cache_by_seat"].get(seat, {}))
    highest_seen_bucket_by_suit = dict(
        cache["red_tint_inner_highest_seen_bucket_by_seat"].get(
            seat,
            {0: -1, 1: -1, 2: -1},
        )
    )
    seen_suited_numbers_by_suit = {
        int(suit_index): set(numbers)
        for suit_index, numbers in dict(
            cache["red_tint_seen_suited_numbers_by_seat"].get(
                seat,
                {0: set(), 1: set(), 2: set()},
            )
        ).items()
    }
    global_discard_index_by_id = (
        {
            id(discard): observed_discard_index
            for observed_discard_index, _discard_seat, discard in _iter_global_discards(round_state)
        }
        if not highlight_started
        else {}
    )

    for local_discard_index in range(processed_count, len(discards)):
        discard = discards[local_discard_index]
        if highlight_started:
            if _is_tedashi_discard(discard):
                highlighted_indices.append(local_discard_index)
            continue

        current_discard_triggers_red = False
        if _is_tedashi_discard(discard) and str(
            getattr(discard, "thinking_time_source", "") or ""
        ).strip() == "call":
            current_discard_triggers_red = True
        else:
            if _is_suited_tedashi_discard(discard):
                suited_tile = _tile34_to_suit_and_number(discard.tile_34)
                if suited_tile is not None:
                    suit_index, suit_number = suited_tile
                    if _has_prior_same_suit_taatsu_drop_neighbor(
                        seen_suited_numbers_by_suit,
                        suit_index,
                        suit_number,
                    ):
                        current_discard_triggers_red = True
                    bucket = _inside_to_outside_bucket(suit_number)
                    target_left_number = _inside_to_outside_target_left_number(suit_number)
                    if (
                        target_left_number is not None
                        and highest_seen_bucket_by_suit.get(suit_index, -1) > bucket
                    ):
                        current_discard_triggers_red = True
                    highest_seen_bucket_by_suit[suit_index] = max(
                        int(highest_seen_bucket_by_suit.get(suit_index, -1)),
                        bucket,
                    )
                    seen_suited_numbers_by_suit.setdefault(int(suit_index), set()).add(int(suit_number))

            if not current_discard_triggers_red:
                observed_discard_index = global_discard_index_by_id.get(id(discard))
                if observed_discard_index is not None:
                    current_no_temp_remain_count = remain_count_cache.get(int(observed_discard_index))
                    if current_no_temp_remain_count is None:
                        prefix_state = _round_state_prefix_until_discard_index(
                            round_state,
                            observed_discard_index,
                        )
                        current_no_temp_remain_count = max(
                            0.0,
                            float(
                                sum(
                                    _build_weighted_suji_line_map(
                                        prefix_state,
                                        seat,
                                        include_temporary_safe=False,
                                    ).values()
                                )
                            ),
                        )
                        remain_count_cache[int(observed_discard_index)] = current_no_temp_remain_count
                    current_discard_triggers_red = (
                        previous_no_temp_remain_count >= NO_TEMP_REMAIN_RED_TINT_THRESHOLD
                        and current_no_temp_remain_count < NO_TEMP_REMAIN_RED_TINT_THRESHOLD
                    )
                    previous_no_temp_remain_count = current_no_temp_remain_count

        if current_discard_triggers_red:
            highlight_started = True
            if _is_tedashi_discard(discard):
                highlighted_indices.append(local_discard_index)

    cache["red_tint_processed_discard_count_by_seat"][seat] = len(discards)
    cache["red_tint_last_processed_discard_id_by_seat"][seat] = (
        id(discards[-1]) if discards else 0
    )
    cache["red_tint_previous_no_temp_remain_by_seat"][seat] = previous_no_temp_remain_count
    cache["red_tint_highlight_started_by_seat"][seat] = highlight_started
    cache["red_tint_highlight_indices_by_seat"][seat] = highlighted_indices
    cache["red_tint_no_temp_remain_cache_by_seat"][seat] = remain_count_cache
    cache["red_tint_inner_highest_seen_bucket_by_seat"][seat] = highest_seen_bucket_by_suit
    cache["red_tint_seen_suited_numbers_by_seat"][seat] = seen_suited_numbers_by_suit
    return tuple(highlighted_indices)


def build_discard_red_tint_indices_by_seat(
    round_state: RoundState | None,
) -> dict[int, tuple[int, ...]]:
    """Return per-seat discard indexes that enter the river red-tint pipeline.

    A seat enters the red-tint state on the first trigger among:
    - `Remain(no-temp) < 13`,
    - a same-suit tedashi after an earlier same-suit tedashi within +/-2 numbers,
    - the first `inner -> outer` tedashi,
    - the first post-call tedashi.

    After that seat-level latch, every later tedashi and call-tedashi for that player stays in the
    red-tint candidate set for the remainder of the round.
    """

    if round_state is None:
        return {}
    return {
        seat: _incremental_red_tint_discard_indices(round_state, seat)
        for seat in SUJI_LABEL_SEAT_ORDER
    }


def _suit_removed_line_gap(
    line_weights: Mapping[tuple[int, int, int], float],
) -> float:
    """Return the max-minus-min removed-line gap across man/pin/sou."""

    unresolved_count_by_suit = {0: 0.0, 1: 0.0, 2: 0.0}
    for (suit_index, _left_number, _right_number), line_weight in line_weights.items():
        unresolved_count_by_suit[suit_index] += min(
            BASE_SUJI_LINE_COUNT,
            max(0.0, float(line_weight)),
        )
    removed_counts = [
        max(0.0, 6.0 - unresolved_count_by_suit[suit_index])
        for suit_index in range(3)
    ]
    return max(removed_counts) - min(removed_counts)


def build_suit_bias_alert(
    round_state: RoundState,
    seat: int,
) -> bool:
    """Return whether one opponent's suit-by-suit removed-line gap suggests flush/toitoi."""

    line_weights_without_temporary_safe = _build_weighted_suji_line_map(
        round_state,
        seat,
        include_temporary_safe=False,
    )
    return _suit_removed_line_gap(line_weights_without_temporary_safe) >= SUIT_BIAS_ALERT_GAP_THRESHOLD


def build_ryanmen_chi_central_tedashi_alert(
    round_state: RoundState,
    seat: int,
) -> bool:
    """Return whether the seat showed a 3..7 tedashi immediately after a ryanmen chi."""

    open_melds = tuple(round_state.melds.get(seat, ()))
    if not open_melds:
        return False
    for discard in round_state.discards.get(seat, ()):
        if discard.tsumogiri or discard.tile_34 is None:
            continue
        if str(getattr(discard, "thinking_time_source", "") or "").strip() != "call":
            continue
        suited_tile = _tile34_to_suit_and_number(discard.tile_34)
        if suited_tile is None:
            continue
        _suit_index, suit_number = suited_tile
        normalized_suit_number = _safe_int(suit_number)
        if normalized_suit_number is None or not 3 <= normalized_suit_number <= 7:
            continue
        discard_event_index = _safe_int(getattr(discard, "event_index", None))
        candidate_melds = [
            meld
            for meld in open_melds
            if (
                discard_event_index is not None
                and discard_event_index >= 0
                and (_safe_int(getattr(meld, "event_index", None)) or -1) < discard_event_index
            )
        ]
        if discard_event_index is None or discard_event_index < 0 or not candidate_melds:
            candidate_melds = list(open_melds)
        if not candidate_melds:
            continue
        latest_meld = max(candidate_melds, key=lambda meld: _safe_int(getattr(meld, "event_index", None)) or -1)
        chi_shape = _chi_wait_shape(latest_meld)
        if chi_shape is None:
            continue
        _chi_suit_index, _start_number, _called_offset, wait_kind = chi_shape
        if wait_kind == "ryanmen":
            return True
    return False


def build_tedashi_thinking_rise_alert(
    round_state: RoundState,
    seat: int,
    *,
    window_size: int = 3,
) -> bool:
    """Return whether the latest tedashi thinking times are strictly increasing."""

    if window_size < 2:
        return False
    tedashi_thinking_times_ms: list[float] = []
    for discard in round_state.discards.get(seat, ()):
        if bool(getattr(discard, "is_tsumogiri_estimated", False)):
            continue
        if getattr(discard, "tsumogiri", False):
            continue
        if str(getattr(discard, "thinking_time_source", "") or "").strip() == "call":
            continue
        thinking_time_ms = getattr(discard, "thinking_time_ms", None)
        if thinking_time_ms is None:
            continue
        try:
            normalized_time_ms = float(thinking_time_ms)
        except (TypeError, ValueError):
            continue
        if normalized_time_ms <= 0.0:
            continue
        tedashi_thinking_times_ms.append(normalized_time_ms)
    if len(tedashi_thinking_times_ms) < window_size:
        return False
    latest_window = tedashi_thinking_times_ms[-window_size:]
    return all(
        previous_time < current_time
        for previous_time, current_time in zip(latest_window, latest_window[1:])
    )


def _lag_risk_factor_for_discard(discard) -> float:
    """Return the adjacent-line danger factor suggested by one lagged skip."""

    lag_delay_ms = _safe_float(getattr(discard, "lag_delay_ms", None))
    if lag_delay_ms is None:
        return 1.0
    # Fast skip windows usually mean "no uke remains" or "this was never a calling hand", while
    # very long windows mix in off-table causes. Only the middle windows raise suji danger.
    if lag_delay_ms <= LAG_DANGER_NO_BONUS_MAX_DELAY_MS:
        return 1.0
    if lag_delay_ms > LAG_DANGER_BONUS_MAX_DELAY_MS:
        return 1.0
    if lag_delay_ms >= LAG_DANGER_LIGHT_MAX_DELAY_MS:
        return LAG_DANGER_STRONG_LINE_FACTOR
    return LAG_DANGER_LIGHT_LINE_FACTOR


def _lag_neighbor_line_factors(
    round_state: RoundState,
    seat: int,
) -> dict[tuple[int, int, int], float]:
    """Return per-line multiplicative danger factors from the previous seat's lagged skips."""

    previous_seat = (seat - 1) % 4
    line_factors: dict[tuple[int, int, int], float] = {}
    for discard in round_state.discards.get(previous_seat, []):
        if not _is_uncalled_lag_source(discard):
            continue
        lag_factor = _lag_risk_factor_for_discard(discard)
        if lag_factor <= 1.0:
            continue
        suited_tile = _tile34_to_suit_and_number(discard.tile_34)
        if suited_tile is None:
            continue
        suit_index, suit_number = suited_tile
        normalized_suit_index = _safe_int(suit_index)
        normalized_suit_number = _safe_int(suit_number)
        if normalized_suit_index is None or normalized_suit_number is None:
            continue
        lag_line_keys: set[tuple[int, int, int]] = set()
        for adjacent_number in (normalized_suit_number - 1, normalized_suit_number + 1):
            normalized_adjacent_number = _safe_int(adjacent_number)
            if normalized_adjacent_number is None or not 1 <= normalized_adjacent_number <= 9:
                continue
            lag_line_keys.update(
                _line_keys_including_number(normalized_suit_index, normalized_adjacent_number)
            )
        for line_key in lag_line_keys:
            _multiply_line_factor(line_factors, line_key, lag_factor)
    return line_factors


def _line_suppressor_numbers_by_suit(
    round_state: RoundState,
    seat: int,
    *,
    include_temporary_safe: bool = True,
) -> dict[int, set[int]]:
    """Collect suited numbers that currently suppress suji lines for one opponent."""

    discarded_numbers = {0: set(), 1: set(), 2: set()}
    suppressor_tile34 = _line_suppressor_tile34_set(
        round_state,
        seat,
        include_temporary_safe=include_temporary_safe,
    )
    for tile_34 in suppressor_tile34:
        suited_tile = _tile34_to_suit_and_number(tile_34)
        if suited_tile is None:
            continue
        suit_index, suit_number = suited_tile
        discarded_numbers[suit_index].add(suit_number)
    return discarded_numbers


def _discard_order_index(discard, fallback_index: int) -> int:
    """Return a stable global-order index for one discard."""

    round_discard_index = _safe_int(getattr(discard, "round_discard_index", None))
    if round_discard_index is not None:
        return round_discard_index
    event_index = _safe_int(getattr(discard, "event_index", None))
    if event_index is not None and event_index >= 0:
        return event_index
    return int(fallback_index)


def _iter_global_discards(round_state: RoundState) -> list[tuple[int, int, object]]:
    """Return all discards as `(global_index, seat, discard)` in round order."""

    observed: list[tuple[int, int, object]] = []
    fallback_index = 0
    for seat, discards in round_state.discards.items():
        for discard in discards:
            observed.append((_discard_order_index(discard, fallback_index), seat, discard))
            fallback_index += 1
    observed.sort(key=lambda item: (item[0], item[1]))
    return observed


def _riichi_anchor_round_index(round_state: RoundState, seat: int) -> int | None:
    """Return the global discard index where riichi was declared, if any."""

    for fallback_index, discard in enumerate(round_state.discards.get(seat, [])):
        if discard.riichi_marker_before:
            return _discard_order_index(discard, fallback_index)
    return None


def _latest_non_riichi_tedashi_anchor_round_index(round_state: RoundState, seat: int) -> int | None:
    """Return the latest pre-riichi tedashi global discard index, if any."""

    latest_anchor_index: int | None = None
    riichi_index = _riichi_anchor_round_index(round_state, seat)
    for fallback_index, discard in enumerate(round_state.discards.get(seat, [])):
        discard_index = _discard_order_index(discard, fallback_index)
        if riichi_index is not None and discard_index >= riichi_index:
            continue
        if discard.tile_34 is None:
            continue
        if discard.riichi_marker_before:
            continue
        if discard.tsumogiri:
            continue
        latest_anchor_index = discard_index
    return latest_anchor_index


def _latest_non_riichi_tedashi_discard(round_state: RoundState, seat: int):
    """Return the latest pre-riichi tedashi discard object, if any."""

    latest_discard = None
    latest_anchor_index: int | None = None
    riichi_index = _riichi_anchor_round_index(round_state, seat)
    for fallback_index, discard in enumerate(round_state.discards.get(seat, [])):
        discard_index = _discard_order_index(discard, fallback_index)
        if riichi_index is not None and discard_index >= riichi_index:
            continue
        if discard.tile_34 is None:
            continue
        if discard.riichi_marker_before:
            continue
        if discard.tsumogiri:
            continue
        latest_discard = discard
        latest_anchor_index = discard_index
    if latest_anchor_index is None:
        return None
    return latest_discard


def _riichi_safe_tile34_set(round_state: RoundState, seat: int) -> set[int]:
    """Return tile34 values that stay exact-safe after riichi until round end."""

    riichi_index = _riichi_anchor_round_index(round_state, seat)
    if riichi_index is None:
        return set()
    safe_tile34: set[int] = set()
    for discard_index, _discard_seat, discard in _iter_global_discards(round_state):
        if discard_index <= riichi_index:
            continue
        if discard.tile_34 is None:
            continue
        safe_tile34.add(discard.tile_34)
    return safe_tile34


def _self_discard_safe_tile34_set(round_state: RoundState, seat: int) -> set[int]:
    """Return tile34 values already discarded by the target player and therefore exact-safe."""

    safe_tile34: set[int] = set()
    for discard in round_state.discards.get(seat, []):
        if discard.tile_34 is None:
            continue
        safe_tile34.add(discard.tile_34)
    return safe_tile34


def _exact_safe_tile34_set(round_state: RoundState, seat: int) -> set[int]:
    """Return exact-safe tile34 values, excluding temporary-safe-only tiles."""

    return _self_discard_safe_tile34_set(round_state, seat) | _riichi_safe_tile34_set(
        round_state,
        seat,
    )


def _temporary_safe_tile34_set(round_state: RoundState, seat: int) -> set[int]:
    """Return tile34 values that are exact-safe only until the next tedashi."""

    if _riichi_anchor_round_index(round_state, seat) is not None:
        return set()
    latest_anchor_index = _latest_non_riichi_tedashi_anchor_round_index(round_state, seat)
    if latest_anchor_index is None:
        return set()

    safe_tile34: set[int] = set()
    for discard_index, _discard_seat, discard in _iter_global_discards(round_state):
        if discard_index <= latest_anchor_index:
            continue
        if discard.tile_34 is None:
            continue
        safe_tile34.add(discard.tile_34)
    return safe_tile34


def _riichi_visible_suppressor_tile34_set(round_state: RoundState, seat: int) -> set[int]:
    """Return post-riichi exact-safe tiles that still remain visible on the table."""

    riichi_index = _riichi_anchor_round_index(round_state, seat)
    if riichi_index is None:
        return set()
    suppressor_tile34: set[int] = set()
    for discard_index, _discard_seat, discard in _iter_global_discards(round_state):
        if discard_index <= riichi_index:
            continue
        if discard.tile_34 is None:
            continue
        suppressor_tile34.add(discard.tile_34)
    return suppressor_tile34


def _temporary_visible_suppressor_tile34_set(round_state: RoundState, seat: int) -> set[int]:
    """Return temporary exact-safe tiles that still remain visible on the table."""

    if _riichi_anchor_round_index(round_state, seat) is not None:
        return set()
    latest_anchor_index = _latest_non_riichi_tedashi_anchor_round_index(round_state, seat)
    if latest_anchor_index is None:
        return set()

    suppressor_tile34: set[int] = set()
    for discard_index, _discard_seat, discard in _iter_global_discards(round_state):
        if discard_index <= latest_anchor_index:
            continue
        if discard.tile_34 is None:
            continue
        suppressor_tile34.add(discard.tile_34)
    return suppressor_tile34


def _is_suji_anchor_discard(discard) -> bool:
    """Return whether this discard becomes a persistent suji-line anchor.

    `called` is orthogonal to discard type: a later-called discard still remains a public discard
    and continues to suppress the corresponding suji lines.
    """

    return True


def _line_suppressor_tile34_set(
    round_state: RoundState,
    seat: int,
    *,
    include_temporary_safe: bool = True,
) -> set[int]:
    """Return tile34 values whose related suji lines are currently suppressed."""

    suppressor_tile34: set[int] = set()
    for discard in round_state.discards.get(seat, []):
        if discard.tile_34 is None:
            continue
        if _is_suji_anchor_discard(discard):
            suppressor_tile34.add(discard.tile_34)
    suppressor_tile34.update(_riichi_visible_suppressor_tile34_set(round_state, seat))
    if include_temporary_safe:
        suppressor_tile34.update(_temporary_visible_suppressor_tile34_set(round_state, seat))
    return suppressor_tile34


def _tedashi_tile34_history(round_state: RoundState, seat: int) -> list[int]:
    """Return all tedashi tile34 history in chronological order."""

    cache = _ensure_tedashi_history_cache(round_state, seat)
    return list(cache["tedashi_tiles_by_seat"].get(seat, ()))


def _tedashi_discard_history(round_state: RoundState, seat: int) -> list[object]:
    """Return all non-called tedashi discard objects in chronological order, including post-call tedashi."""

    cache = _ensure_tedashi_history_cache(round_state, seat)
    return list(cache["tedashi_discards_by_seat"].get(seat, ()))


def _is_red_five_discard(discard) -> bool:
    """Return whether one discard is a red five and should weaken its matagi lines."""

    tile_37 = _safe_int(getattr(discard, "tile_37", None))
    if tile_37 in (34, 35, 36):
        return True
    return getattr(discard, "tile_136", None) in RED_TILE_IDS_136


def _space_thinned_target_tile34_set(round_state: RoundState, seat: int) -> frozenset[int]:
    """Return same-suit inner-side tiles softened by the latest suited tedashi."""

    tedashi_tiles = _tedashi_tile34_history(round_state, seat)
    if not tedashi_tiles:
        return frozenset()
    suited_tile = _tile34_to_suit_and_number(tedashi_tiles[-1])
    if suited_tile is None:
        return frozenset()

    suit_index, suit_number = suited_tile
    inner_numbers = LATEST_TEDASHI_SPACE_THIN_NUMBERS.get(suit_number)
    if inner_numbers is None:
        return frozenset()

    # This correction only softens ugly waits. It never zeroes them by itself; 0% still comes
    # from physical denial such as 4-visible requirements or 3-visible shanpon exhaustion.
    targets = {
        _tile34_from_suit_and_number(suit_index, candidate_number)
        for candidate_number in inner_numbers
        if 1 <= candidate_number <= 9
    }
    return frozenset(targets)


def _latest_tedashi_non_genbutsu_suji_tile34_set(
    round_state: RoundState,
    seat: int,
) -> frozenset[int]:
    """Return latest-tedashi suji tiles excluding the discard tile itself."""

    latest_tedashi_discard = _latest_non_riichi_tedashi_discard(round_state, seat)
    if latest_tedashi_discard is None:
        return frozenset()
    suited_tile = _tile34_to_suit_and_number(getattr(latest_tedashi_discard, "tile_34", None))
    if suited_tile is None:
        return frozenset()
    suit_index, suit_number = suited_tile
    targets = {
        _tile34_from_suit_and_number(suit_index, candidate_number)
        for _line_suit_index, left_number, right_number in _line_keys_including_number(
            suit_index,
            suit_number,
        )
        for candidate_number in (left_number, right_number)
        if candidate_number != suit_number
    }
    return frozenset(targets)


def _latest_tedashi_suji_ugly_wait_add_percent(
    remaining_suji_count: float,
) -> float:
    """Return the flat ugly-wait add applied to latest-tedashi non-genbutsu suji tiles."""

    return max(
        LATEST_TEDASHI_SUJI_UGLY_WAIT_MIN_PERCENT,
        LATEST_TEDASHI_SUJI_UGLY_WAIT_BASE_PERCENT
        + (
            LATEST_TEDASHI_SUJI_UGLY_WAIT_REMAIN_REFERENCE_COUNT
            - max(0.0, float(remaining_suji_count))
        )
        * LATEST_TEDASHI_SUJI_UGLY_WAIT_REMAIN_STEP_PERCENT,
    )


def _visible_count_for_tile(
    visible_counts_34: Sequence[int],
    tile_34: int | None,
) -> int:
    """Return one tile's total visible count from the normalized 34-index tuple."""

    if tile_34 is None or not 0 <= tile_34 < len(visible_counts_34):
        return 0
    return max(0, int(visible_counts_34[tile_34]))


def _line_visible_count_sum(
    visible_counts_34: Sequence[int],
    line_key: tuple[int, int, int],
) -> int:
    """Return the total visible count of the two endpoint tiles belonging to one suji line."""

    suit_index, left_number, right_number = line_key
    left_tile_34 = _tile34_from_suit_and_number(suit_index, left_number)
    right_tile_34 = _tile34_from_suit_and_number(suit_index, right_number)
    return _visible_count_for_tile(visible_counts_34, left_tile_34) + _visible_count_for_tile(
        visible_counts_34,
        right_tile_34,
    )


def _latest_tedashi_urasuji_ryanmen_candidates(
    tile_34: int | None,
) -> tuple[tuple[tuple[int, int, int], int], ...]:
    """Return `(line_key, inner_tile_34)` pairs for the latest tedashi's urasuji-ryanmen."""

    suited_tile = _tile34_to_suit_and_number(tile_34)
    if suited_tile is None:
        return ()
    suit_index, suit_number = suited_tile
    normalized_suit_index = _safe_int(suit_index)
    normalized_suit_number = _safe_int(suit_number)
    if normalized_suit_index is None or normalized_suit_number is None:
        return ()

    # Only the representative single-side patterns are modeled here. 5 has two symmetric
    # urasuji-ryanmen lines, while every other suited number maps to only one line.
    if normalized_suit_number == 5:
        return (
            (
                (normalized_suit_index, 1, 4),
                _tile34_from_suit_and_number(normalized_suit_index, 3),
            ),
            (
                (normalized_suit_index, 6, 9),
                _tile34_from_suit_and_number(normalized_suit_index, 7),
            ),
        )
    if normalized_suit_number < 5:
        left_number = normalized_suit_number + 1
        inner_number = normalized_suit_number + 2
    else:
        left_number = normalized_suit_number - 4
        inner_number = normalized_suit_number - 2
    line_key = _line_key_from_left_number(normalized_suit_index, left_number)
    normalized_inner_number = _safe_int(inner_number)
    if line_key is None or normalized_inner_number is None or not 1 <= normalized_inner_number <= 9:
        return ()
    return ((line_key, _tile34_from_suit_and_number(normalized_suit_index, normalized_inner_number)),)


def _latest_tedashi_urasuji_ryanmen_factor(
    latest_tile_34: int | None,
    inner_tile_34: int,
    visible_counts_34: Sequence[int],
) -> float:
    """Return the single applicable latest-tedashi urasuji factor for one target line."""

    latest_visible_count = _visible_count_for_tile(visible_counts_34, latest_tile_34)
    inner_visible_count = _visible_count_for_tile(visible_counts_34, inner_tile_34)
    has_two_visible_anchor = latest_visible_count == 2 or inner_visible_count == 2
    if has_two_visible_anchor and latest_visible_count + inner_visible_count >= 3:
        return URASUJI_RYANMEN_HEAVY_VISIBLE_FACTOR
    if has_two_visible_anchor:
        return URASUJI_RYANMEN_TWO_VISIBLE_FACTOR
    return URASUJI_RYANMEN_BASE_FACTOR


def _latest_tedashi_urasuji_ryanmen_line_factors(
    round_state: RoundState,
    seat: int,
    visible_counts_34: Sequence[int],
) -> dict[tuple[int, int, int], float]:
    """Return temporary line factors from one seat's current latest tedashi."""

    tedashi_tiles = _tedashi_tile34_history(round_state, seat)
    if not tedashi_tiles:
        return {}

    # This lookup is seat-local. It never refers to the round's global last discard, and it is
    # recalculated every update so the previous urasuji correction disappears on the next tedashi.
    latest_tile_34 = tedashi_tiles[-1]
    line_factors: dict[tuple[int, int, int], float] = {}
    for line_key, inner_tile_34 in _latest_tedashi_urasuji_ryanmen_candidates(latest_tile_34):
        _multiply_line_factor(
            line_factors,
            line_key,
            _latest_tedashi_urasuji_ryanmen_factor(
                latest_tile_34,
                inner_tile_34,
                visible_counts_34,
            ),
        )
    return line_factors


def _musuji_concentration_factor_for_line(
    visible_counts_34: Sequence[int],
    line_key: tuple[int, int, int],
) -> float:
    """Return the line-count multiplier derived from the line's total visible endpoint count."""

    visible_count_sum = _line_visible_count_sum(visible_counts_34, line_key)
    if visible_count_sum <= 2:
        return MUSUJI_CONCENTRATION_LOW_VISIBLE_FACTOR
    if visible_count_sum == 3:
        return MUSUJI_CONCENTRATION_THREE_VISIBLE_FACTOR
    if visible_count_sum == 4:
        return MUSUJI_CONCENTRATION_FOUR_VISIBLE_FACTOR
    return MUSUJI_CONCENTRATION_FIVE_PLUS_VISIBLE_FACTOR


def _self_hand_count_for_tile(
    self_hand_counts_34: Sequence[int],
    tile_34: int | None,
) -> int:
    """Return one tile's self-hand count from the normalized 34-index tuple."""

    if tile_34 is None or not 0 <= tile_34 < len(self_hand_counts_34):
        return 0
    return max(0, int(self_hand_counts_34[tile_34]))


def _ugly_wait_kanchan_add_percent(
    tile_34: int | None,
    visible_counts_34: Sequence[int],
    space_thinned_target_tile34: frozenset[int],
) -> float:
    """Return the kanchan add percentage for one target tile."""

    suited_tile = _tile34_to_suit_and_number(tile_34)
    if suited_tile is None:
        return 0.0
    suit_index, suit_number = suited_tile
    if suit_number in (1, 9):
        return 0.0
    if _visible_count_for_tile(visible_counts_34, tile_34) >= 4:
        return 0.0

    left_tile_34 = _tile34_from_suit_and_number(suit_index, suit_number - 1)
    right_tile_34 = _tile34_from_suit_and_number(suit_index, suit_number + 1)
    if (
        _visible_count_for_tile(visible_counts_34, left_tile_34) >= 4
        or _visible_count_for_tile(visible_counts_34, right_tile_34) >= 4
    ):
        return 0.0
    if tile_34 in space_thinned_target_tile34:
        return UGLY_WAIT_KANCHAN_THIN_PERCENT
    return UGLY_WAIT_BASE_PERCENT


def _ugly_wait_penchan_add_percent(
    tile_34: int | None,
    visible_counts_34: Sequence[int],
) -> float:
    """Return the penchan add percentage for one target tile."""

    suited_tile = _tile34_to_suit_and_number(tile_34)
    if suited_tile is None:
        return 0.0
    suit_index, suit_number = suited_tile
    if suit_number == 3:
        required_numbers = (1, 2)
    elif suit_number == 7:
        required_numbers = (8, 9)
    else:
        return 0.0
    if _visible_count_for_tile(visible_counts_34, tile_34) >= 4:
        return 0.0
    for required_number in required_numbers:
        if _visible_count_for_tile(
            visible_counts_34,
            _tile34_from_suit_and_number(suit_index, required_number),
        ) >= 4:
            return 0.0
    return UGLY_WAIT_BASE_PERCENT


def _ugly_wait_shanpon_add_percent(
    tile_34: int | None,
    visible_counts_34: Sequence[int],
    space_thinned_target_tile34: frozenset[int],
) -> float:
    """Return the shanpon add percentage for one target tile."""

    visible_count = _visible_count_for_tile(visible_counts_34, tile_34)
    if visible_count >= 3:
        return 0.0
    add_percent = (
        UGLY_WAIT_SHANPON_TWO_VISIBLE_PERCENT
        if visible_count == 2
        else UGLY_WAIT_BASE_PERCENT
    )
    if tile_34 in space_thinned_target_tile34:
        add_percent = min(add_percent, UGLY_WAIT_SHANPON_THIN_PERCENT)
    return add_percent


def _ugly_wait_concentration_bonus_percent(
    tile_34: int | None,
    visible_counts_34: Sequence[int],
    self_hand_counts_34: Sequence[int],
    ugly_wait_add_percent: float,
) -> float:
    """Return the self-hand concentration bonus for one target tile when applicable."""

    if ugly_wait_add_percent <= 0.0:
        return 0.0
    visible_count = _visible_count_for_tile(visible_counts_34, tile_34)
    self_hand_count = _self_hand_count_for_tile(self_hand_counts_34, tile_34)
    if visible_count == 3 and self_hand_count >= 2:
        return UGLY_WAIT_CONCENTRATION_BONUS_PERCENT
    if visible_count == 4 and self_hand_count >= 3:
        return UGLY_WAIT_CONCENTRATION_BONUS_PERCENT
    return 0.0


def _build_ugly_wait_add_percentages(
    round_state: RoundState,
    seat: int,
    safe_tile34: frozenset[int],
    visible_counts_34: Sequence[int],
    self_hand_counts_34: Sequence[int],
    *,
    remaining_suji_count: float,
) -> tuple[float, ...]:
    """Build per-tile ugly-wait add percentages layered on top of base musuji danger."""

    space_thinned_target_tile34 = _space_thinned_target_tile34_set(round_state, seat)
    latest_tedashi_non_genbutsu_suji_tile34 = _latest_tedashi_non_genbutsu_suji_tile34_set(
        round_state,
        seat,
    )
    latest_tedashi_suji_add_percent = _latest_tedashi_suji_ugly_wait_add_percent(
        remaining_suji_count
    )
    ugly_wait_add_percentages = [0.0] * 34
    # Each target tile can accumulate up to three ugly-wait patterns. We add them tile-by-tile so
    # later UI ranking can explain "why this tile stayed dangerous" independently of line weights.
    for tile_34 in range(34):
        if tile_34 in safe_tile34:
            continue
        if _visible_count_for_tile(visible_counts_34, tile_34) >= 4:
            continue

        # Kanchan / shanpon / penchan are scored independently, then the self-hand-heavy
        # concentration case adds one extra point when any ugly shape still survives.
        ugly_wait_add_percent = 0.0
        ugly_wait_add_percent += _ugly_wait_kanchan_add_percent(
            tile_34,
            visible_counts_34,
            space_thinned_target_tile34,
        )
        ugly_wait_add_percent += _ugly_wait_shanpon_add_percent(
            tile_34,
            visible_counts_34,
            space_thinned_target_tile34,
        )
        ugly_wait_add_percent += _ugly_wait_penchan_add_percent(
            tile_34,
            visible_counts_34,
        )
        ugly_wait_add_percent += _ugly_wait_concentration_bonus_percent(
            tile_34,
            visible_counts_34,
            self_hand_counts_34,
            ugly_wait_add_percent,
        )
        if tile_34 in latest_tedashi_non_genbutsu_suji_tile34:
            ugly_wait_add_percent += latest_tedashi_suji_add_percent
        ugly_wait_add_percentages[tile_34] = ugly_wait_add_percent
    return tuple(ugly_wait_add_percentages)


def _build_weighted_suji_line_map(
    round_state: RoundState,
    seat: int,
    *,
    visible_counts_34: Sequence[int] | None = None,
    include_temporary_safe: bool = True,
) -> dict[tuple[int, int, int], float]:
    """Return weighted unresolved suji lines keyed by `(suit_index, left, right)`."""

    # Phase 1: build the unresolved-line map. Exact-safe and persistent suppressors immediately
    # force the affected lines to 0.0, while the remaining unresolved lines start from 1.0 line.
    suppressed_numbers = _line_suppressor_numbers_by_suit(
        round_state,
        seat,
        include_temporary_safe=include_temporary_safe,
    )
    normalized_visible_counts_34 = _normalize_visible_counts_34(visible_counts_34)
    line_weights: dict[tuple[int, int, int], float] = {}
    for suit_index in range(3):
        suit_discards = suppressed_numbers[suit_index]
        for left_number, right_number in SUJI_LINE_NUMBER_PAIRS:
            if left_number in suit_discards or right_number in suit_discards:
                line_weights[(suit_index, left_number, right_number)] = 0.0
                continue
            line_weights[(suit_index, left_number, right_number)] = BASE_SUJI_LINE_COUNT

    # Phase 2: assign at most one matagi line count per still-unresolved line, aging backward
    # through the tedashi history as 100% -> 50% -> 30% of one full line. When a later
    # representative taatsu-drop second tedashi exists, older matagi candidates are kept at 70%.
    assigned_line_weights: dict[tuple[int, int, int], float] = {}
    tedashi_discards = _tedashi_discard_history(round_state, seat)
    tedashi_tiles = [discard.tile_34 for discard in tedashi_discards]
    latest_taatsu_drop_second_index = _representative_taatsu_drop_second_index(tedashi_discards)
    for history_index in range(len(tedashi_tiles) - 1, -1, -1):
        discard = tedashi_discards[history_index]
        tile_34 = tedashi_tiles[history_index]
        followup_tedashi_count = len(tedashi_tiles) - 1 - history_index
        suited_tile = _tile34_to_suit_and_number(tile_34)
        if suited_tile is None:
            continue
        suit_index, suit_number = suited_tile
        for left_number, right_number in _matagi_line_pairs_for_number(suit_number):
            line_key = (suit_index, left_number, right_number)
            if line_weights.get(line_key, 0.0) <= 0.0:
                continue
            if line_key in assigned_line_weights:
                continue
            matagi_line_count = _matagi_line_count(
                followup_tedashi_count,
                taatsu_drop_softened=(
                    latest_taatsu_drop_second_index is not None
                    and history_index < latest_taatsu_drop_second_index
                ),
                red_five_discarded=_is_red_five_discard(discard),
                visible_count=_visible_count_for_tile(normalized_visible_counts_34, tile_34),
            )
            assigned_line_weights[line_key] = matagi_line_count

    for line_key, matagi_line_count in assigned_line_weights.items():
        line_weights[line_key] = matagi_line_count

    # Phase 3: chi-shape correction, inside->outside tedashi correction, and latest-tedashi
    # urasuji-ryanmen all multiply the counted line amount. When multiple AND conditions hit the
    # same line, all percentage-style reductions stack multiplicatively against the current count.
    line_factors: dict[tuple[int, int, int], float] = {}
    for source_factors in (
        _chi_line_factors(round_state, seat),
        _inside_to_outside_line_factors(round_state, seat),
        _latest_tedashi_urasuji_ryanmen_line_factors(
            round_state,
            seat,
            normalized_visible_counts_34,
        ),
    ):
        for line_key, factor in source_factors.items():
            _multiply_line_factor(line_factors, line_key, factor)
    for line_key, factor in line_factors.items():
        if line_weights.get(line_key, 0.0) <= 0.0:
            continue
        line_weights[line_key] *= factor
    current_remain_count = float(sum(line_weights.values()))
    for line_key, factor in _low_remain_long_thinking_tsumogiri_line_factors(
        round_state,
        seat,
        remain_count=current_remain_count,
    ).items():
        if line_weights.get(line_key, 0.0) <= 0.0:
            continue
        line_weights[line_key] *= factor

    # Phase 4: lag only scales the selected neighbor lines. It never revives a suppressed line and
    # never scales unrelated numerator/denominator contributions. Long skip windows strengthen the
    # neighboring lines at 120% or 140%, while <=1400ms and >7000ms apply no lag bonus.
    for line_key, factor in _lag_neighbor_line_factors(round_state, seat).items():
        if line_weights.get(line_key, 0.0) <= 0.0:
            continue
        line_weights[line_key] *= factor
    return line_weights


def build_opponent_suji_danger_profile(
    round_state: RoundState,
    seat: int,
    *,
    visible_counts_34: Sequence[int] | None = None,
    self_hand_counts_34: Sequence[int] | None = None,
) -> OpponentSujiDangerProfile:
    """Build suji danger weights plus ugly-wait adders for one opponent seat."""

    normalized_visible_counts_34 = _normalize_visible_counts_34(visible_counts_34)
    normalized_self_hand_counts_34 = _normalize_visible_counts_34(self_hand_counts_34)
    tile_weights_34 = [0.0] * 34
    line_weights = _build_weighted_suji_line_map(
        round_state,
        seat,
        visible_counts_34=normalized_visible_counts_34,
    )
    safe_tile34 = frozenset(
        _self_discard_safe_tile34_set(round_state, seat)
        | _riichi_safe_tile34_set(round_state, seat)
        | _temporary_safe_tile34_set(round_state, seat)
    )
    # Convert the final line weights back into per-tile danger by adding each line onto its two
    # endpoint tiles. The denominator stays as the total unresolved weighted line count.
    for (suit_index, left_number, right_number), line_weight in line_weights.items():
        if line_weight <= 0.0:
            continue
        tile_weights_34[_tile34_from_suit_and_number(suit_index, left_number)] += line_weight
        tile_weights_34[_tile34_from_suit_and_number(suit_index, right_number)] += line_weight

    corrected_musuji_count = float(sum(line_weights.values()))
    return OpponentSujiDangerProfile(
        seat=seat,
        tile_weights_34=tuple(tile_weights_34),
        corrected_musuji_count=corrected_musuji_count,
        safe_tile34=safe_tile34,
        line_weights=tuple(
            (line_key[0], line_key[1], line_key[2], line_weight)
            for line_key, line_weight in sorted(line_weights.items())
        ),
        visible_counts_34=normalized_visible_counts_34,
        ugly_wait_add_percent_34=_build_ugly_wait_add_percentages(
            round_state,
            seat,
            safe_tile34,
            normalized_visible_counts_34,
            normalized_self_hand_counts_34,
            remaining_suji_count=corrected_musuji_count,
        ),
    )


def build_all_opponent_suji_danger_profiles(
    round_state: RoundState,
    *,
    visible_counts_34: Sequence[int] | None = None,
    self_hand_counts_34: Sequence[int] | None = None,
) -> dict[int, OpponentSujiDangerProfile]:
    """Build suji danger profiles for shimocha/toimen/kamicha."""

    return {
        seat: build_opponent_suji_danger_profile(
            round_state,
            seat,
            visible_counts_34=visible_counts_34,
            self_hand_counts_34=self_hand_counts_34,
        )
        for seat in SUJI_LABEL_SEAT_ORDER
    }


def _profile_line_weight_items(
    profile: OpponentSujiDangerProfile,
) -> tuple[tuple[tuple[int, int, int], float], ...]:
    """Return the profile's final unresolved suji lines as `(line_key, line_weight)` tuples."""

    return tuple(
        (((suit_index, left_number, right_number), line_weight))
        for suit_index, left_number, right_number, line_weight in profile.line_weights
    )


def _tile_base_denominator_count(profile: OpponentSujiDangerProfile) -> float:
    """Return the shared denominator before tile-specific concentration corrections."""

    return max(0.0, float(profile.corrected_musuji_count))


def _tile_base_numerator_count(profile: OpponentSujiDangerProfile, tile_34: int | None) -> float:
    """Return one tile's numerator before tile-specific concentration corrections."""

    if tile_34 is None or not 0 <= tile_34 < len(profile.tile_weights_34):
        return 0.0
    if tile_34 in profile.safe_tile34:
        return 0.0
    return max(0.0, float(profile.tile_weights_34[tile_34]))


def _tile_base_weight_percent_value(profile: OpponentSujiDangerProfile, tile_34: int | None) -> float:
    """Convert one tile's base weighted musuji count into an unrounded percent value."""

    denominator_count = _tile_base_denominator_count(profile)
    if denominator_count <= 0:
        return 0.0
    return max(
        0.0,
        _tile_base_numerator_count(profile, tile_34) / denominator_count * 100.0,
    )


def _tile_adjusted_line_weight_items(
    profile: OpponentSujiDangerProfile,
    tile_34: int | None,
) -> tuple[tuple[tuple[int, int, int], float], ...]:
    """Return tile-specific line weights after optional visible-count concentration correction."""

    line_weight_items = _profile_line_weight_items(profile)
    # The visible-count concentration stage only starts after the tile is already reasonably live
    # as a musuji candidate. Low-base tiles keep the shared line weights unchanged.
    if _tile_base_weight_percent_value(profile, tile_34) <= MUSUJI_CONCENTRATION_TRIGGER_PERCENT:
        return line_weight_items

    adjusted_line_weight_items: list[tuple[tuple[int, int, int], float]] = []
    for line_key, line_weight in line_weight_items:
        adjusted_line_weight_items.append(
            (
                line_key,
                line_weight
                * _musuji_concentration_factor_for_line(profile.visible_counts_34, line_key),
            )
        )
    return tuple(adjusted_line_weight_items)


def _tile_weight_percent_value(profile: OpponentSujiDangerProfile, tile_34: int | None) -> float:
    """Convert one tile's weighted musuji count into an unrounded percent value."""

    denominator_count = _tile_denominator_count(profile, tile_34)
    if denominator_count <= 0.0:
        return 0.0
    numerator_count = _tile_numerator_count(profile, tile_34)
    return max(0.0, numerator_count / denominator_count * 100.0)


def _tile_ugly_wait_percent(profile: OpponentSujiDangerProfile, tile_34: int | None) -> float:
    """Return the ugly-wait additive percentage for one tile."""

    if tile_34 is None or not 0 <= tile_34 < len(profile.ugly_wait_add_percent_34):
        return 0.0
    if tile_34 in profile.safe_tile34:
        return 0.0
    return max(0.0, float(profile.ugly_wait_add_percent_34[tile_34]))


def _tile_total_percent(profile: OpponentSujiDangerProfile, tile_34: int | None) -> float:
    """Return the displayed composite danger percentage for one tile."""

    # Ugly-wait danger is not another numerator/denominator correction. It is a flat additive
    # percentage placed on top of the musuji danger percentage after line-count corrections finish.
    total_percent = max(
        0.0,
        _tile_weight_percent_value(profile, tile_34) + _tile_ugly_wait_percent(profile, tile_34),
    )
    # 100%超えは、残筋本数が実質 1 本相当まで減ったときだけ許容する。複数本が残っている局面では
    # 途中丸めや局所加算の都合で 100 を超えて見えないように、表示値を 100 までに丸める。
    if _tile_denominator_count(profile, tile_34) > 1.0:
        return min(100.0, total_percent)
    return total_percent


def _tile_denominator_count(profile: OpponentSujiDangerProfile, tile_34: int | None) -> float:
    """Return one tile's denominator-side weighted musuji count after concentration correction."""

    if tile_34 is None or tile_34 in profile.safe_tile34:
        return _tile_base_denominator_count(profile)
    return max(
        0.0,
        sum(line_weight for _line_key, line_weight in _tile_adjusted_line_weight_items(profile, tile_34)),
    )


def _tile_numerator_count(profile: OpponentSujiDangerProfile, tile_34: int | None) -> float:
    """Return one tile's weighted musuji contribution on the numerator side."""

    if tile_34 is None or not 0 <= tile_34 < len(profile.tile_weights_34):
        return 0.0
    if tile_34 in profile.safe_tile34:
        return 0.0
    suited_tile = _tile34_to_suit_and_number(tile_34)
    if suited_tile is None:
        return _tile_base_numerator_count(profile, tile_34)
    suit_index, suit_number = suited_tile
    numerator_count = 0.0
    for line_key, line_weight in _tile_adjusted_line_weight_items(profile, tile_34):
        line_suit_index, left_number, right_number = line_key
        if line_suit_index != suit_index:
            continue
        if suit_number not in (left_number, right_number):
            continue
        numerator_count += line_weight
    return max(0.0, numerator_count)


def _top_weighted_line_summaries(
    profile: OpponentSujiDangerProfile,
    line_weights: dict[tuple[int, int, int], float],
    *,
    limit: int = 3,
) -> tuple[OpponentSujiPanelLineSummary, ...]:
    """Return top `Line` rows, keeping suit coverage first and backfilling with leftover live lines."""

    suit_remaining_counts = _suit_remaining_count_by_suit(line_weights)
    candidate_records: list[
        tuple[
            tuple[float, float, float, int, int, int],
            float,
            float,
            tuple[int, int, int],
        ]
    ] = []
    for line_key, line_weight in line_weights.items():
        if line_weight <= 0.0:
            continue
        suit_index, left_number, right_number = line_key
        left_tile_34 = _tile34_from_suit_and_number(suit_index, left_number)
        right_tile_34 = _tile34_from_suit_and_number(suit_index, right_number)
        left_total_percent = round(_tile_total_percent(profile, left_tile_34), 1)
        right_total_percent = round(_tile_total_percent(profile, right_tile_34), 1)
        representative_percent = max(left_total_percent, right_total_percent)
        candidate_ranking_key = (
            -representative_percent,
            -(left_total_percent + right_total_percent),
            -float(line_weight),
            suit_index,
            left_number,
            right_number,
        )
        candidate_records.append(
            (
                candidate_ranking_key,
                representative_percent,
                left_total_percent + right_total_percent,
                line_key,
            )
        )

    best_line_by_suit: dict[
        int,
        tuple[
            tuple[float, float, float, int, int, int],
            float,
            float,
            tuple[int, int, int],
        ],
    ] = {}
    for candidate_record in candidate_records:
        candidate_ranking_key, _representative_percent, _pair_percent_sum, line_key = candidate_record
        suit_index = line_key[0]
        current_best = best_line_by_suit.get(suit_index)
        if current_best is None or candidate_ranking_key < current_best[0]:
            best_line_by_suit[suit_index] = candidate_record

    ranked_lines = sorted(best_line_by_suit.values(), key=lambda item: item[0])
    used_line_keys = {line_key for _ranking_key, _rep_percent, _pair_sum, line_key in ranked_lines}
    if len(ranked_lines) < limit:
        for candidate_record in sorted(candidate_records, key=lambda item: item[0]):
            line_key = candidate_record[3]
            if line_key in used_line_keys:
                continue
            ranked_lines.append(candidate_record)
            used_line_keys.add(line_key)
            if len(ranked_lines) >= limit:
                break

    summaries: list[OpponentSujiPanelLineSummary] = []
    for rank_index, (_ranking_key, representative_percent, _pair_percent_sum, line_key) in enumerate(
        ranked_lines[:limit],
        start=1,
    ):
        suit_index, left_number, right_number = line_key
        suit_label = SUJI_LINE_SUIT_SUFFIX.get(suit_index, "?")
        line_weight = max(0.0, float(line_weights.get(line_key, 0.0)))
        summaries.append(
            OpponentSujiPanelLineSummary(
                rank_text=f"{rank_index}.",
                left_tile_label=f"{left_number}{suit_label}",
                right_tile_label=f"{right_number}{suit_label}",
                suit_label=suit_label,
                line_weight_text=_format_suji_line_weight(line_weight),
                percent_text=_format_composite_percent(representative_percent),
                suit_remaining_count_text=_format_suji_line_weight(
                    suit_remaining_counts[suit_index] if 0 <= suit_index < 3 else 0.0
                ),
            )
        )
    return tuple(summaries)


def _line_summary_to_legacy_label(summary: OpponentSujiPanelLineSummary) -> str:
    """Serialize one structured line summary back into the legacy text format."""

    parts = [
        f"{summary.left_tile_label[:-1]}-{summary.right_tile_label[:-1]}{summary.suit_label}"
    ]
    if summary.suit_label and summary.suit_remaining_count_text:
        parts.append(f"{summary.suit_label}{summary.suit_remaining_count_text}")
    if summary.percent_text:
        parts.append(summary.percent_text)
    return " ".join(parts)


def _top_tile_rank_labels(
    profile: OpponentSujiDangerProfile,
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    """Return grouped tile rankings using the composite danger percentage."""

    ranked_tiles = sorted(
        (
            (tile_34, rounded_total_percent)
            for tile_34 in range(34)
            for rounded_total_percent in (round(_tile_total_percent(profile, tile_34), 1),)
            if rounded_total_percent > 0.0
        ),
        key=lambda item: (-item[1], item[0]),
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
        grouped_labels.append(
            f"{current_rank}. {' '.join(current_tiles[:5])} {_format_composite_percent(last_percent)}"
        )

    for tile_34, total_percent in ranked_tiles:
        tile_label = _format_tile34_label(tile_34)
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


def _top_safe_hand_labels(
    profile: OpponentSujiDangerProfile,
    *,
    self_hand_counts_34: Sequence[int],
    limit: int = 3,
) -> tuple[str, ...]:
    """Return grouped safest tile labels restricted to the current self hand."""

    normalized_self_hand_counts_34 = _normalize_visible_counts_34(self_hand_counts_34)
    ranked_tiles = sorted(
        (
            (tile_34, round(_tile_total_percent(profile, tile_34), 1))
            for tile_34, tile_count in enumerate(normalized_self_hand_counts_34)
            if tile_count > 0
        ),
        key=lambda item: (item[1], item[0]),
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
        grouped_labels.append(
            f"{current_rank}. {' '.join(current_tiles[:5])} {_format_composite_percent(last_percent)}"
        )

    for tile_34, total_percent in ranked_tiles:
        tile_label = _format_tile34_label(tile_34)
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


def build_opponent_suji_panel_summary(
    round_state: RoundState,
    seat: int,
    *,
    visible_counts_34: Sequence[int] | None = None,
    self_hand_counts_34: Sequence[int] | None = None,
) -> OpponentSujiPanelSummary:
    """Build one opponent-panel summary with denominator and top suji lines."""

    normalized_self_hand_counts_34 = _normalize_visible_counts_34(self_hand_counts_34)
    profile = build_opponent_suji_danger_profile(
        round_state,
        seat,
        visible_counts_34=visible_counts_34,
        self_hand_counts_34=normalized_self_hand_counts_34,
    )
    return _build_opponent_suji_panel_summary_from_profile(
        round_state,
        seat,
        profile,
        self_hand_counts_34=normalized_self_hand_counts_34,
    )


def _profile_line_weights_map(
    profile: OpponentSujiDangerProfile,
) -> dict[tuple[int, int, int], float]:
    """Convert one immutable profile's line tuple back into a mapping."""

    return {
        (suit_index, left_number, right_number): float(line_weight)
        for suit_index, left_number, right_number, line_weight in profile.line_weights
    }


def _build_opponent_suji_panel_summary_from_profile(
    round_state: RoundState,
    seat: int,
    profile: OpponentSujiDangerProfile,
    *,
    self_hand_counts_34: Sequence[int] | None = None,
) -> OpponentSujiPanelSummary:
    """Build one panel summary from an already computed suji danger profile."""

    # Reuse the same line map as the self-hand danger bars so the SUMMARY text and bar-side values
    # are always derived from the same final weights.
    line_weights = _profile_line_weights_map(profile)
    denominator_count = max(0.0, float(sum(line_weights.values())))
    line_weights_without_temporary_safe = _build_weighted_suji_line_map(
        round_state,
        seat,
        include_temporary_safe=False,
    )
    denominator_count_without_temporary_safe = max(
        0.0,
        float(sum(line_weights_without_temporary_safe.values())),
    )
    normalized_self_hand_counts_34 = _normalize_visible_counts_34(self_hand_counts_34)
    tenpai_probabilities = build_opponent_tenpai_probability_percentages(round_state)
    top_line_summaries = _top_weighted_line_summaries(
        profile,
        line_weights,
    )
    return OpponentSujiPanelSummary(
        seat=seat,
        denominator_count=denominator_count,
        denominator_count_without_temporary_safe=denominator_count_without_temporary_safe,
        menzen_alert_score=build_kamicha_no_lag_menzen_alert_score(round_state, seat),
        hand_pattern_alert_level=build_inner_to_outer_hand_pattern_alert_level(round_state, seat),
        suit_bias_alert=(
            _suit_removed_line_gap(line_weights_without_temporary_safe)
            >= SUIT_BIAS_ALERT_GAP_THRESHOLD
        ),
        ryanmen_chi_central_tedashi_alert=build_ryanmen_chi_central_tedashi_alert(
            round_state,
            seat,
        ),
        tedashi_thinking_rise_alert=build_tedashi_thinking_rise_alert(round_state, seat),
        tenpai_probability=round(max(0.0, tenpai_probabilities.get(seat, 0.0)), 1),
        top_line_labels=tuple(
            _line_summary_to_legacy_label(summary) for summary in top_line_summaries
        ),
        top_line_summaries=top_line_summaries,
        top_safe_hand_labels=_top_safe_hand_labels(
            profile,
            self_hand_counts_34=normalized_self_hand_counts_34,
        ),
        # Tile rank is built from the final per-tile totals, including ugly-wait adders, so the
        # panel can show both "remaining suji structure" and "actual tile danger" side by side.
        top_tile_rank_labels=_top_tile_rank_labels(profile),
    )


def build_all_opponent_suji_panel_summaries(
    round_state: RoundState,
    *,
    visible_counts_34: Sequence[int] | None = None,
    self_hand_counts_34: Sequence[int] | None = None,
    profiles: Mapping[int, OpponentSujiDangerProfile] | None = None,
) -> dict[int, OpponentSujiPanelSummary]:
    """Build panel summaries for shimocha/toimen/kamicha."""

    normalized_self_hand_counts_34 = _normalize_visible_counts_34(self_hand_counts_34)
    resolved_profiles = (
        dict(profiles)
        if profiles is not None
        else build_all_opponent_suji_danger_profiles(
            round_state,
            visible_counts_34=visible_counts_34,
            self_hand_counts_34=normalized_self_hand_counts_34,
        )
    )
    return {
        seat: _build_opponent_suji_panel_summary_from_profile(
            round_state,
            seat,
            resolved_profiles[seat],
            self_hand_counts_34=normalized_self_hand_counts_34,
        )
        for seat in SUJI_LABEL_SEAT_ORDER
    }


def estimate_tile_suji_danger_percent(
    round_state: RoundState,
    seat: int,
    tile_34: int | None,
    *,
    visible_counts_34: Sequence[int] | None = None,
    self_hand_counts_34: Sequence[int] | None = None,
) -> float:
    """Return one tile's final composite danger percentage against one target seat."""

    if tile_34 is None or not 0 <= tile_34 < 34:
        return 0.0
    profile = build_opponent_suji_danger_profile(
        round_state,
        seat,
        visible_counts_34=visible_counts_34,
        self_hand_counts_34=self_hand_counts_34,
    )
    return round(_tile_total_percent(profile, tile_34), 1)


def _is_late_honor_shonpai_push_trigger(
    round_state: RoundState,
    actor_seat: int,
    discard,
    *,
    discard_index: int | None,
) -> bool:
    """Return whether one latest discard should raise push via late honor shonpai timing."""

    tile_34 = getattr(discard, "tile_34", None)
    if tile_34 is None or not 27 <= tile_34 < 34:
        return False
    if len(round_state.discards.get(actor_seat, ())) < LATE_HONOR_SHONPAI_PUSH_MIN_TURN:
        return False
    if discard_index is None:
        return False
    for observed_discard_index, _seat, observed_discard in _iter_global_discards(round_state):
        if observed_discard_index >= discard_index:
            continue
        if getattr(observed_discard, "tile_34", None) == tile_34:
            return False
    return True


def build_latest_discard_push_alert_percentages(
    round_state: RoundState,
    *,
    visible_counts_34: Sequence[int] | None = None,
    threshold_percent: float = PUSH_ALERT_PERCENT_THRESHOLD,
    riichi_target_threshold_percent: float = PUSH_ALERT_PERCENT_THRESHOLD_AGAINST_RIICHI,
    max_target_remain_count: float = PUSH_ALERT_MAX_TARGET_REMAIN_COUNT,
) -> dict[int, PlayerPushAlertSummary]:
    """Return per-opponent latest-discard danger percentages used by player-panel alerts.

    The actor's latest discard is evaluated against all other seats, including self seat `0`,
    so opponent panels also alert when that discard is a likely push against the local player.
    A push alert is emitted only when at least one threshold-exceeding target currently has
    `Remain <= max_target_remain_count`. Riichi targets use the lower `6%` threshold.
    """

    try:
        resolved_threshold_percent = float(threshold_percent)
    except (TypeError, ValueError):
        resolved_threshold_percent = PUSH_ALERT_PERCENT_THRESHOLD
    if resolved_threshold_percent <= 0.0:
        resolved_threshold_percent = PUSH_ALERT_PERCENT_THRESHOLD
    try:
        resolved_riichi_target_threshold_percent = float(riichi_target_threshold_percent)
    except (TypeError, ValueError):
        resolved_riichi_target_threshold_percent = PUSH_ALERT_PERCENT_THRESHOLD_AGAINST_RIICHI
    if resolved_riichi_target_threshold_percent <= 0.0:
        resolved_riichi_target_threshold_percent = PUSH_ALERT_PERCENT_THRESHOLD_AGAINST_RIICHI
    resolved_riichi_target_threshold_percent = min(
        resolved_threshold_percent,
        resolved_riichi_target_threshold_percent,
    )

    normalized_visible_counts_34 = _normalize_visible_counts_34(visible_counts_34)
    global_discards = _iter_global_discards(round_state)
    latest_global_discard_index = global_discards[-1][0] if global_discards else None
    alert_percentages: dict[int, PlayerPushAlertSummary] = {}
    for actor_seat in SUJI_LABEL_SEAT_ORDER:
        latest_discards = round_state.discards.get(actor_seat, ())
        if not latest_discards:
            alert_percentages[actor_seat] = PlayerPushAlertSummary(seat=actor_seat)
            continue
        latest_discard = latest_discards[-1]
        discard_index = _discard_order_index(latest_discard, len(latest_discards) - 1)
        is_current = latest_global_discard_index is not None and discard_index == latest_global_discard_index
        late_honor_shonpai_push = _is_late_honor_shonpai_push_trigger(
            round_state,
            actor_seat,
            latest_discard,
            discard_index=discard_index,
        )
        tile_34 = latest_discard.tile_34
        if tile_34 is None or not 0 <= tile_34 < 34:
            alert_percentages[actor_seat] = PlayerPushAlertSummary(
                seat=actor_seat,
                discard_index=discard_index,
                is_current=is_current,
            )
            continue
        adjusted_visible_counts_34 = list(normalized_visible_counts_34)
        if adjusted_visible_counts_34[tile_34] > 0 and not latest_discard.called:
            adjusted_visible_counts_34[tile_34] -= 1

        synthetic_self_hand_counts_34 = [0] * 34
        synthetic_self_hand_counts_34[tile_34] = 1
        qualifying_max_percent = 0.0
        qualifying_threshold_percent = resolved_threshold_percent
        qualifying_target_seats: list[int] = []
        exact_safe_target_seats: list[int] = []
        for target_seat in (0, *SUJI_LABEL_SEAT_ORDER):
            if target_seat == actor_seat:
                continue
            profile = build_opponent_suji_danger_profile(
                round_state,
                target_seat,
                visible_counts_34=adjusted_visible_counts_34,
                self_hand_counts_34=synthetic_self_hand_counts_34,
            )
            target_percent = _tile_total_percent(profile, tile_34)
            target_remain_count = max(0.0, float(profile.corrected_musuji_count))
            target_threshold_percent = (
                resolved_riichi_target_threshold_percent
                if _seat_has_riichi_tenpai(round_state, target_seat)
                else resolved_threshold_percent
            )
            if (
                target_percent >= target_threshold_percent
                and target_remain_count <= max_target_remain_count
            ):
                qualifying_max_percent = max(qualifying_max_percent, target_percent)
                qualifying_threshold_percent = min(
                    qualifying_threshold_percent,
                    target_threshold_percent,
                )
                qualifying_target_seats.append(target_seat)
            if (
                not latest_discard.tsumogiri
                and tile_34 in _exact_safe_tile34_set(round_state, target_seat)
            ):
                exact_safe_target_seats.append(target_seat)
        if late_honor_shonpai_push:
            qualifying_max_percent = max(qualifying_max_percent, resolved_threshold_percent)
            qualifying_threshold_percent = min(
                qualifying_threshold_percent,
                resolved_threshold_percent,
            )
        effective_threshold_percent = (
            qualifying_threshold_percent
            if qualifying_max_percent > 0.0
            else resolved_threshold_percent
        )
        alert_percentages[actor_seat] = PlayerPushAlertSummary(
            seat=actor_seat,
            percentage=(
                round(qualifying_max_percent, 1)
                if qualifying_max_percent >= effective_threshold_percent
                else 0.0
            ),
            tile_34=tile_34,
            tile_label=_format_tile34_label(tile_34),
            discard_index=discard_index,
            is_current=is_current,
            threshold_percent=effective_threshold_percent,
            target_seats=tuple(sorted(set(qualifying_target_seats))),
            exact_safe_target_seats=tuple(sorted(set(exact_safe_target_seats))),
        )
    return alert_percentages


def build_hand_tile_suji_danger_metrics(
    state: CaptureState,
    hand_tiles_136: Sequence[int],
    *,
    visible_counts_34: Sequence[int] | None = None,
    self_hand_counts_34: Sequence[int] | None = None,
    profiles: Mapping[int, OpponentSujiDangerProfile] | None = None,
) -> list[dict[int, TileDangerMetric]]:
    """Return per-tile suji percentages and remaining counts keyed by opponent seat."""

    round_state = state.current_round
    if round_state is None:
        return []

    normalized_self_hand_counts_34 = (
        _normalize_visible_counts_34(self_hand_counts_34)
        if self_hand_counts_34 is not None
        else _hand_tile34_counts_from_tile136(hand_tiles_136)
    )
    resolved_profiles = (
        dict(profiles)
        if profiles is not None
        else build_all_opponent_suji_danger_profiles(
            round_state,
            visible_counts_34=visible_counts_34,
            self_hand_counts_34=normalized_self_hand_counts_34,
        )
    )
    tenpai_probability_by_seat = build_opponent_tenpai_probability_percentages(round_state)
    tenpai_rate_by_seat = {
        seat: max(0.0, min(100.0, float(tenpai_probability_by_seat.get(seat, 0.0)))) / 100.0
        for seat in resolved_profiles
    }
    metrics: list[dict[int, TileDangerMetric]] = []
    # The renderer expects one dict per hand tile, keyed by opponent seat. Each dict carries both
    # the displayed percentage and the raw numerator/denominator used by panel summaries.
    for tile_136 in hand_tiles_136:
        tile_34 = tile136_to_tile34_index(tile_136)
        metrics.append(
                {
                    seat: TileDangerMetric(
                        percentage=int(
                            round(
                                _tile_total_percent(profile, tile_34)
                                * tenpai_rate_by_seat.get(seat, 0.0)
                            )
                        ),
                        numerator_count=(
                            _tile_numerator_count(profile, tile_34)
                            * tenpai_rate_by_seat.get(seat, 0.0)
                        ),
                        denominator_count=_tile_denominator_count(profile, tile_34),
                        base_percentage=int(
                            round(
                                _tile_weight_percent_value(profile, tile_34)
                                * tenpai_rate_by_seat.get(seat, 0.0)
                            )
                        ),
                        ugly_wait_percentage=(
                            _tile_ugly_wait_percent(profile, tile_34)
                            * tenpai_rate_by_seat.get(seat, 0.0)
                        ),
                    )
                    for seat, profile in resolved_profiles.items()
                }
        )
    return metrics


def build_hand_tile_suji_danger_percentages(
    state: CaptureState,
    hand_tiles_136: Sequence[int],
) -> list[dict[int, int]]:
    """Return per-tile suji danger percentages keyed by opponent seat."""

    return [
        {seat: metric.percentage for seat, metric in tile_metrics.items()}
        for tile_metrics in build_hand_tile_suji_danger_metrics(state, hand_tiles_136)
    ]
