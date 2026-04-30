from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from capture.state import RED_TILE_IDS_136, tile136_to_tile34, tile136_to_tile34_index
from sutehai import Discard, Player

EMPTY_VISIBLE_COUNTS_34_INDEX = (0,) * 34
EMPTY_INFERRED_VISIBLE_COUNTS_34_INDEX = (0.0,) * 34
THREE_VISIBLE_TILES_ENABLED = True

# EMPTY_VISIBLE_COUNTS_34_INDEX の型定義。
EMPTY_VISIBLE_COUNTS_34_INDEX = (0,) * 34
RED_DORA_TILE_IDS_37 = frozenset((10, 20, 30))


def _normalize_visible_count_tuple(values: Sequence[int] | None) -> tuple[int, ...]:
    """Clamp one visible-count sequence into a fixed non-negative 34-entry int tuple."""

    normalized = [0] * 34
    if not values:
        return tuple(normalized)
    for index in range(min(len(values), 34)):
        raw_value = values[index]
        try:
            numeric_value = int(raw_value)
        except (TypeError, ValueError):
            numeric_value = 0
        normalized[index] = max(0, numeric_value)
    return tuple(normalized)


def _derive_four_visible_tile34_index_set(
    visible_counts_34_index: Sequence[int],
    four_visible_tiles: Sequence[int],
) -> frozenset[int]:
    """Return the canonical 0..33 four-visible tile set from counts or legacy tile ids."""

    derived_from_counts = {
        tile_34_index
        for tile_34_index, visible_count in enumerate(visible_counts_34_index)
        if int(visible_count) >= 4
    }
    if derived_from_counts:
        return frozenset(derived_from_counts)
    return frozenset(
        tile_34_index
        for tile_34_index in (
            tile37_to_tile34_index(int(tile_id))
            for tile_id in four_visible_tiles
        )
        if tile_34_index is not None
    )


def _derive_blocked_sequence_tile34_index_set(
    four_visible_tile34_index_set: Sequence[int],
) -> frozenset[int]:
    """Return suited tile kinds that belong to any 4-visible-blocked 3-sequence."""

    blockers = frozenset(int(tile_34_index) for tile_34_index in four_visible_tile34_index_set)
    if not blockers:
        return frozenset()
    blocked_tiles: set[int] = set()
    # 数牌 3スーツ x 連続形 123..789 の 21 通りを先に列挙し、
    # どれか 1 枚でも 4見えが含まれる 3 連形を「物理否定済み」とみなす。
    # 茶色 tint は、その否定済み 3 連形に属する手出し牌へ付ける。
    for suit_index in range(3):
        suit_offset = suit_index * 9
        for sequence_start in range(7):
            sequence_tile34_indexes = tuple(
                suit_offset + sequence_start + offset
                for offset in range(3)
            )
            if not any(tile_34_index in blockers for tile_34_index in sequence_tile34_indexes):
                continue
            blocked_tiles.update(sequence_tile34_indexes)
    return frozenset(blocked_tiles)


def _derive_exhausted_sequence_tile34_index_set(
    four_visible_tile34_index_set: Sequence[int],
) -> frozenset[int]:
    """Return suited tile kinds whose every 3-sequence is blocked by at least one 4-visible tile."""

    blockers = frozenset(int(tile_34_index) for tile_34_index in four_visible_tile34_index_set)
    if not blockers:
        return frozenset()
    blocked_tiles: set[int] = set()
    for suit_index in range(3):
        suit_offset = suit_index * 9
        for suit_number in range(1, 10):
            tile_34_index = suit_offset + (suit_number - 1)
            sequence_starts = range(max(1, suit_number - 2), min(7, suit_number) + 1)
            sequence_tile34_groups = tuple(
                tuple(suit_offset + (sequence_start - 1) + offset for offset in range(3))
                for sequence_start in sequence_starts
            )
            if sequence_tile34_groups and all(
                any(sequence_tile_34_index in blockers for sequence_tile_34_index in sequence_group)
                for sequence_group in sequence_tile34_groups
            ):
                blocked_tiles.add(tile_34_index)
    return frozenset(blocked_tiles)


@dataclass(frozen=True)
class VisibleTileSummary:
    """Visible-tile summary shared by the renderer and danger logic."""

    # three_visible_tiles の一覧。
    three_visible_tiles: list[int]
    # four_visible_tiles の一覧。
    four_visible_tiles: list[int]
    # Danger logic uses 0..33 tile indices, while the legacy renderer still consumes the
    # display-oriented 34-kind ids above. Both views are kept in the same transport object.
    visible_counts_34_index: tuple[int, ...] = field(
        default_factory=lambda: EMPTY_VISIBLE_COUNTS_34_INDEX
    )
    # Red fives are separate dora and should be tracked independently from 34-kind counts.
    visible_red_dora_count: int = 0
    four_visible_tile34_index_set: frozenset[int] = field(default_factory=frozenset)
    blocked_sequence_tile34_index_set: frozenset[int] = field(default_factory=frozenset)
    # self_hand_counts_34_index の並びを保持する。
    self_hand_counts_34_index: tuple[int, ...] = field(
        default_factory=lambda: EMPTY_VISIBLE_COUNTS_34_INDEX
    )

    def __post_init__(self) -> None:
        normalized_visible_counts = _normalize_visible_count_tuple(self.visible_counts_34_index)
        normalized_self_hand_counts = _normalize_visible_count_tuple(self.self_hand_counts_34_index)
        derived_four_visible_set = _derive_four_visible_tile34_index_set(
            normalized_visible_counts,
            self.four_visible_tiles,
        )
        derived_blocked_sequence_set = _derive_exhausted_sequence_tile34_index_set(
            derived_four_visible_set,
        )
        object.__setattr__(self, "visible_counts_34_index", normalized_visible_counts)
        object.__setattr__(self, "self_hand_counts_34_index", normalized_self_hand_counts)
        object.__setattr__(self, "four_visible_tile34_index_set", derived_four_visible_set)
        object.__setattr__(
            self,
            "blocked_sequence_tile34_index_set",
            derived_blocked_sequence_set,
        )


@dataclass(frozen=True)
class VisibleTileInferenceSummary:
    """Derived visible-tile summary after applying inferred float adjustments."""

    global_adjustments_34_index: tuple[float, ...] = field(
        default_factory=lambda: EMPTY_INFERRED_VISIBLE_COUNTS_34_INDEX
    )
    player_adjustments_34_index: dict[int, tuple[float, ...]] = field(default_factory=dict)
    adjusted_visible_counts_34_index: tuple[float, ...] = field(
        default_factory=lambda: EMPTY_INFERRED_VISIBLE_COUNTS_34_INDEX
    )
    rounded_visible_counts_34_index: tuple[int, ...] = field(
        default_factory=lambda: EMPTY_VISIBLE_COUNTS_34_INDEX
    )
    inferred_three_visible_tiles: list[int] = field(default_factory=list)
    inferred_four_visible_tiles: list[int] = field(default_factory=list)


# Legacy display ids used by the existing UI detail panel.
VISIBLE_TILE_IDS_34 = tuple(
    list(range(1, 10)) + list(range(11, 20)) + list(range(21, 30)) + list(range(31, 38))
)


def tile37_to_tile34(tile_id: int) -> int | None:
    """Convert a 1..37 UI tile id into the legacy 34-kind display id."""

    try:
        tile_id = int(tile_id)
    except (TypeError, ValueError):
        return None
    if 1 <= tile_id <= 9:
        return tile_id
    if tile_id == 10:
        return 5
    if 11 <= tile_id <= 19:
        return tile_id
    if tile_id == 20:
        return 15
    if 21 <= tile_id <= 29:
        return tile_id
    if tile_id == 30:
        return 25
    if 31 <= tile_id <= 37:
        return tile_id
    return None


def tile37_to_tile34_index(tile_id: int) -> int | None:
    """Convert a 1..37 UI tile id into the canonical 0..33 tile index."""

    try:
        tile_id = int(tile_id)
    except (TypeError, ValueError):
        return None
    if 1 <= tile_id <= 9:
        return tile_id - 1
    if tile_id == 10:
        return 4
    if 11 <= tile_id <= 19:
        return tile_id - 2
    if tile_id == 20:
        return 13
    if 21 <= tile_id <= 29:
        return tile_id - 3
    if tile_id == 30:
        return 22
    if 31 <= tile_id <= 37:
        return tile_id - 4
    return None


def _counter_to_visible_count_tuple(counter: Counter[int]) -> tuple[int, ...]:
    """Expand a sparse 34-index counter into a fixed 34-entry tuple."""

    return tuple(int(counter.get(tile_34, 0)) for tile_34 in range(34))


def _normalize_float_count_tuple(values: Sequence[float] | None) -> tuple[float, ...]:
    """Clamp one inferred-count sequence into a fixed non-negative 34-entry float tuple."""

    normalized = [0.0] * 34
    if not values:
        return tuple(normalized)
    for index in range(min(len(values), 34)):
        raw_value = values[index]
        try:
            numeric_value = float(raw_value)
        except (TypeError, ValueError):
            numeric_value = 0.0
        normalized[index] = max(0.0, numeric_value)
    return tuple(normalized)


def _round_visible_count_half_up(value: float) -> int:
    """Round one visible-count float to the nearest integer using positive half-up rules."""

    normalized_value = max(0.0, float(value))
    return int(normalized_value + 0.5)


def _tile_ids_with_rounded_visible_count(
    rounded_visible_counts_34_index: Sequence[int],
    target_count: int,
) -> list[int]:
    """Return legacy display tile ids whose rounded visible count matches `target_count`."""

    matched_tiles: list[int] = []
    for tile_id in VISIBLE_TILE_IDS_34:
        tile_34_index = tile37_to_tile34_index(tile_id)
        if tile_34_index is None or tile_34_index >= len(rounded_visible_counts_34_index):
            continue
        if int(rounded_visible_counts_34_index[tile_34_index]) == int(target_count):
            matched_tiles.append(tile_id)
    return matched_tiles


def build_visible_tile_inference_summary(
    visible_summary: VisibleTileSummary,
    *,
    global_adjustments_34_index: Sequence[float] | None = None,
    player_adjustments_34_index: Mapping[int, Sequence[float]] | None = None,
) -> VisibleTileInferenceSummary:
    """Combine actual visible counts with inferred float adjustments.

    When the seat-agnostic global adjustment is omitted, it is derived from the sum of the
    provided per-seat adjustments so the caller can keep player-level bookkeeping as the source of
    truth.
    """

    normalized_player_adjustments = {
        int(seat): _normalize_float_count_tuple(adjustments)
        for seat, adjustments in (player_adjustments_34_index or {}).items()
    }
    if global_adjustments_34_index is None:
        derived_global_adjustments = [0.0] * 34
        for adjustments in normalized_player_adjustments.values():
            for tile_34_index, value in enumerate(adjustments):
                derived_global_adjustments[tile_34_index] += float(value)
        normalized_global_adjustments = _normalize_float_count_tuple(derived_global_adjustments)
    else:
        normalized_global_adjustments = _normalize_float_count_tuple(global_adjustments_34_index)

    adjusted_visible_counts = tuple(
        min(
            4.0,
            float(visible_summary.visible_counts_34_index[tile_34_index])
            + float(normalized_global_adjustments[tile_34_index]),
        )
        for tile_34_index in range(34)
    )
    rounded_visible_counts = tuple(
        _round_visible_count_half_up(value)
        for value in adjusted_visible_counts
    )
    return VisibleTileInferenceSummary(
        global_adjustments_34_index=normalized_global_adjustments,
        player_adjustments_34_index=normalized_player_adjustments,
        adjusted_visible_counts_34_index=adjusted_visible_counts,
        rounded_visible_counts_34_index=rounded_visible_counts,
        inferred_three_visible_tiles=(
            _tile_ids_with_rounded_visible_count(rounded_visible_counts, 3)
            if THREE_VISIBLE_TILES_ENABLED
            else []
        ),
        inferred_four_visible_tiles=_tile_ids_with_rounded_visible_count(rounded_visible_counts, 4),
    )


def _is_red_dora_tile37(tile_id: int) -> bool:
    """Return whether one UI-facing tile id is a red five."""

    return int(tile_id) in RED_DORA_TILE_IDS_37


def collect_visible_tile_summary(
    discard_map: Mapping[Player, Iterable[Discard]],
    hand_tiles: Sequence[int],
    meld_tiles: Sequence[int],
    dora_indicator_tiles: Sequence[int],
) -> VisibleTileSummary:
    """Collect actual visible-tile counts from UI-facing 37-kind tile ids.

    This collector intentionally depends only on self hand, discards, exposed meld tiles, and dora
    indicators. Awaseuchi/public-event markers and inferred visible adjustments are managed on
    separate paths.
    """

    visible_counter: Counter[int] = Counter()
    visible_counter_index: Counter[int] = Counter()
    self_hand_counter_index: Counter[int] = Counter()
    visible_red_dora_count = 0

    # Called discards are already represented inside melds and must not be double-counted here.
    # This keeps visible-count logic aligned with both the renderer's x3/x4 markers and the
    # danger module's 34-kind denominator math.
    for discards in discard_map.values():
        for discard in discards:
            if discard.called:
                continue
            tile34 = tile37_to_tile34(discard.tile_id)
            tile34_index = tile37_to_tile34_index(discard.tile_id)
            if tile34 is not None:
                visible_counter[tile34] += 1
            if tile34_index is not None:
                visible_counter_index[tile34_index] += 1
            if _is_red_dora_tile37(discard.tile_id):
                visible_red_dora_count += 1

    # Hand tiles contribute to both total visible counts and self-hand concentration counts.
    for tile_id in hand_tiles:
        tile34 = tile37_to_tile34(tile_id)
        tile34_index = tile37_to_tile34_index(tile_id)
        if tile34 is not None:
            visible_counter[tile34] += 1
        if tile34_index is not None:
            visible_counter_index[tile34_index] += 1
            self_hand_counter_index[tile34_index] += 1
        if _is_red_dora_tile37(tile_id):
            visible_red_dora_count += 1

    # Meld tiles and dora indicators are only globally visible; they do not count as self hand.
    for tile_id in list(meld_tiles) + list(dora_indicator_tiles):
        tile34 = tile37_to_tile34(tile_id)
        tile34_index = tile37_to_tile34_index(tile_id)
        if tile34 is not None:
            visible_counter[tile34] += 1
        if tile34_index is not None:
            visible_counter_index[tile34_index] += 1
        if _is_red_dora_tile37(tile_id):
            visible_red_dora_count += 1

    return VisibleTileSummary(
        three_visible_tiles=(
            [
                tile_id for tile_id in VISIBLE_TILE_IDS_34 if visible_counter[tile_id] == 3
            ]
            if THREE_VISIBLE_TILES_ENABLED
            else []
        ),
        four_visible_tiles=[
            tile_id for tile_id in VISIBLE_TILE_IDS_34 if visible_counter[tile_id] == 4
        ],
        visible_counts_34_index=_counter_to_visible_count_tuple(visible_counter_index),
        visible_red_dora_count=visible_red_dora_count,
        self_hand_counts_34_index=_counter_to_visible_count_tuple(self_hand_counter_index),
    )


def collect_visible_tile_summary_from_tile136(
    discard_tiles_136: Sequence[int],
    hand_tiles_136: Sequence[int],
    meld_tiles_136: Sequence[int],
    dora_indicator_tiles_136: Sequence[int],
) -> VisibleTileSummary:
    """Collect visible-tile counts from raw 136-kind tile ids."""

    visible_counter: Counter[int] = Counter()
    visible_counter_index: Counter[int] = Counter()
    self_hand_counter_index: Counter[int] = Counter()
    visible_red_dora_count = 0

    # This variant mirrors the UI-facing 37-kind collector above, but starts from raw IDs so DB
    # or parser-side callers can reuse the same visibility semantics without going through UI ids.
    for tile_136 in discard_tiles_136:
        tile34 = tile136_to_tile34(tile_136)
        tile34_index = tile136_to_tile34_index(tile_136)
        if tile34 is not None:
            visible_counter[tile34] += 1
        if tile34_index is not None:
            visible_counter_index[tile34_index] += 1
        if tile_136 in RED_TILE_IDS_136:
            visible_red_dora_count += 1

    for tile_136 in hand_tiles_136:
        tile34 = tile136_to_tile34(tile_136)
        tile34_index = tile136_to_tile34_index(tile_136)
        if tile34 is not None:
            visible_counter[tile34] += 1
        if tile34_index is not None:
            visible_counter_index[tile34_index] += 1
            self_hand_counter_index[tile34_index] += 1
        if tile_136 in RED_TILE_IDS_136:
            visible_red_dora_count += 1

    for tile_136 in list(meld_tiles_136) + list(dora_indicator_tiles_136):
        tile34 = tile136_to_tile34(tile_136)
        tile34_index = tile136_to_tile34_index(tile_136)
        if tile34 is not None:
            visible_counter[tile34] += 1
        if tile34_index is not None:
            visible_counter_index[tile34_index] += 1
        if tile_136 in RED_TILE_IDS_136:
            visible_red_dora_count += 1

    return VisibleTileSummary(
        three_visible_tiles=(
            [
                tile_id for tile_id in VISIBLE_TILE_IDS_34 if visible_counter[tile_id] == 3
            ]
            if THREE_VISIBLE_TILES_ENABLED
            else []
        ),
        four_visible_tiles=[
            tile_id for tile_id in VISIBLE_TILE_IDS_34 if visible_counter[tile_id] == 4
        ],
        visible_counts_34_index=_counter_to_visible_count_tuple(visible_counter_index),
        visible_red_dora_count=visible_red_dora_count,
        self_hand_counts_34_index=_counter_to_visible_count_tuple(self_hand_counter_index),
    )
