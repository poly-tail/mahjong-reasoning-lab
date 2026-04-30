from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

from capture.state import tile136_to_tile34_index

# TERMINAL_AND_HONOR_TILE_34 の並びを定義する。
TERMINAL_AND_HONOR_TILE_34: tuple[int, ...] = (
    0,
    8,
    9,
    17,
    18,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
)
# MAX_HAND_GROUP_COUNT の定義。
MAX_HAND_GROUP_COUNT = 4


@dataclass(frozen=True)
class ShantenBreakdown:
    """Shanten values for the three standard hand families."""

    # overall を保持する。
    overall: int | None
    # normal を保持する。
    normal: int | None
    # chiitoitsu を保持する。
    chiitoitsu: int | None
    # kokushi を保持する。
    kokushi: int | None
    # completed_meld_count を保持する。
    completed_meld_count: int


@dataclass(frozen=True)
class RyanmenFixedAnalysis:
    """Result of checking whether one discard fixes a two-sided wait shape."""

    # is_ryanmen_fixed を保持する。
    is_ryanmen_fixed: bool
    # left_tile_34 を保持する。
    left_tile_34: int | None = None
    # right_tile_34 を保持する。
    right_tile_34: int | None = None


def tiles136_to_counts34(hand_tiles_136: Iterable[int]) -> tuple[int, ...]:
    """Build 34-kind tile counts from raw 136-tile ids."""

    counts_34 = [0] * 34
    for tile_136 in hand_tiles_136:
        tile_34 = tile136_to_tile34_index(tile_136)
        if tile_34 is None:
            continue
        counts_34[tile_34] += 1
    return tuple(counts_34)


def infer_open_meld_count_from_pre_discard_hand_size(
    concealed_tile_count: int,
) -> int | None:
    """Infer how many open meld groups already left the concealed hand at discard time.

    Normal discard-time concealed counts are `14 / 11 / 8 / 5 / 2`. Kakan is the notable
    exception action, but after rinshan draw it still falls back into the same count bands.
    """

    missing_tile_count = 14 - concealed_tile_count
    if missing_tile_count < 0 or missing_tile_count % 3 != 0:
        return None
    completed_meld_count = missing_tile_count // 3
    if not 0 <= completed_meld_count <= MAX_HAND_GROUP_COUNT:
        return None
    return completed_meld_count


def infer_completed_meld_count_from_post_discard_hand_size(
    concealed_tile_count: int,
) -> int | None:
    """Legacy helper kept for older callers that still reason from post-discard hand sizes."""

    missing_tile_count = 13 - concealed_tile_count
    if missing_tile_count < 0 or missing_tile_count % 3 != 0:
        return None
    completed_meld_count = missing_tile_count // 3
    if not 0 <= completed_meld_count <= MAX_HAND_GROUP_COUNT:
        return None
    return completed_meld_count


def calculate_shanten_from_tiles_136(
    hand_tiles_136: Sequence[int],
    *,
    open_meld_count: int = 0,
) -> ShantenBreakdown:
    """Calculate shanten from a concealed hand represented by raw 136-tile ids."""

    return calculate_shanten_from_counts_34(
        tiles136_to_counts34(hand_tiles_136),
        open_meld_count=open_meld_count,
    )


def calculate_shanten_from_counts_34(
    counts_34: Sequence[int],
    *,
    open_meld_count: int = 0,
) -> ShantenBreakdown:
    """Calculate normal / chiitoitsu / kokushi shanten from 34-kind tile counts."""

    normalized_counts = _normalize_counts_34(counts_34)
    if not 0 <= open_meld_count <= MAX_HAND_GROUP_COUNT:
        raise ValueError(f"open_meld_count must be in 0..4: {open_meld_count}")

    normal = _normal_hand_shanten(normalized_counts, open_meld_count)

    # Chiitoitsu and kokushi are only valid for fully closed hands.
    chiitoitsu = _chiitoitsu_shanten(normalized_counts) if open_meld_count == 0 else None
    kokushi = _kokushi_shanten(normalized_counts) if open_meld_count == 0 else None

    candidates = [value for value in (normal, chiitoitsu, kokushi) if value is not None]
    overall = min(candidates) if candidates else None
    return ShantenBreakdown(
        overall=overall,
        normal=normal,
        chiitoitsu=chiitoitsu,
        kokushi=kokushi,
        completed_meld_count=open_meld_count,
    )


def find_tenpai_wait_tiles_34_from_tiles_136(
    hand_tiles_136: Sequence[int],
    *,
    open_meld_count: int = 0,
) -> tuple[int, ...]:
    """Return 0..33 wait tile indices for a tenpai concealed-hand snapshot."""

    return find_tenpai_wait_tiles_34_from_counts_34(
        tiles136_to_counts34(hand_tiles_136),
        open_meld_count=open_meld_count,
    )


def find_tenpai_wait_tiles_34_from_counts_34(
    counts_34: Sequence[int],
    *,
    open_meld_count: int = 0,
) -> tuple[int, ...]:
    """Return every tile kind that completes a hand currently at shanten 0."""

    normalized_counts = _normalize_counts_34(counts_34)
    shanten = calculate_shanten_from_counts_34(
        normalized_counts,
        open_meld_count=open_meld_count,
    )
    if shanten.overall != 0:
        return ()

    wait_tiles_34: list[int] = []
    for tile_34, count in enumerate(normalized_counts):
        if count >= 4:
            continue
        candidate_counts = list(normalized_counts)
        candidate_counts[tile_34] += 1
        completed = calculate_shanten_from_counts_34(
            tuple(candidate_counts),
            open_meld_count=open_meld_count,
        )
        if completed.overall == -1:
            wait_tiles_34.append(tile_34)
    return tuple(wait_tiles_34)


def detect_ryanmen_fixed_discard(
    pre_discard_tiles_136: Sequence[int],
    discard_tile_136: int,
) -> RyanmenFixedAnalysis:
    """Return whether the discard turns an adjacent duplicate shape into a pure ryanmen."""

    discard_tile_34 = tile136_to_tile34_index(discard_tile_136)
    if discard_tile_34 is None or not 0 <= discard_tile_34 < 27:
        return RyanmenFixedAnalysis(is_ryanmen_fixed=False)

    # Ryanmen-fix is defined by the pre-discard 3-tile local shape, so rebuild the post-discard
    # hand first and then inspect the resulting two-tile shape.
    post_discard_tiles_136 = list(pre_discard_tiles_136)
    try:
        post_discard_tiles_136.remove(discard_tile_136)
    except ValueError:
        removed = False
        for index, tile_136 in enumerate(post_discard_tiles_136):
            if tile136_to_tile34_index(tile_136) != discard_tile_34:
                continue
            del post_discard_tiles_136[index]
            removed = True
            break
        if not removed:
            return RyanmenFixedAnalysis(is_ryanmen_fixed=False)

    post_counts_34 = list(tiles136_to_counts34(post_discard_tiles_136))

    # The discarded tile must have been the duplicate side of the shape, so one copy remains.
    if post_counts_34[discard_tile_34] != 1:
        return RyanmenFixedAnalysis(is_ryanmen_fixed=False)

    suit_offset = (discard_tile_34 // 9) * 9
    discard_rank = discard_tile_34 - suit_offset + 1
    candidate_pairs: list[tuple[int, int]] = []

    for neighbor_delta in (-1, 1):
        neighbor_tile_34 = discard_tile_34 + neighbor_delta
        if not suit_offset <= neighbor_tile_34 < suit_offset + 9:
            continue
        if post_counts_34[neighbor_tile_34] != 1:
            continue

        neighbor_rank = neighbor_tile_34 - suit_offset + 1
        low_rank = min(discard_rank, neighbor_rank)
        high_rank = max(discard_rank, neighbor_rank)

        # Only 23..78 are true two-sided waits. 12 and 89 are penchan and excluded.
        if low_rank <= 1 or high_rank >= 9:
            continue

        left_outer_tile_34 = suit_offset + (low_rank - 2)
        right_outer_tile_34 = suit_offset + high_rank

        # The local shape must stay as two tiles only, not already extend into a 3-tile run.
        if post_counts_34[left_outer_tile_34] > 0 or post_counts_34[right_outer_tile_34] > 0:
            continue

        candidate_pairs.append((suit_offset + low_rank - 1, suit_offset + high_rank - 1))

    if len(candidate_pairs) != 1:
        return RyanmenFixedAnalysis(is_ryanmen_fixed=False)

    left_tile_34, right_tile_34 = candidate_pairs[0]
    return RyanmenFixedAnalysis(
        is_ryanmen_fixed=True,
        left_tile_34=left_tile_34,
        right_tile_34=right_tile_34,
    )


def _normalize_counts_34(counts_34: Sequence[int]) -> tuple[int, ...]:
    if len(counts_34) != 34:
        raise ValueError(f"counts_34 must contain 34 entries: {len(counts_34)}")

    normalized_counts: list[int] = []
    for tile_34, count in enumerate(counts_34):
        normalized_count = int(count)
        if not 0 <= normalized_count <= 4:
            raise ValueError(f"counts_34[{tile_34}] must be in 0..4: {normalized_count}")
        normalized_counts.append(normalized_count)
    return tuple(normalized_counts)


def _chiitoitsu_shanten(counts_34: tuple[int, ...]) -> int:
    pair_type_count = sum(1 for count in counts_34 if count >= 2)
    unique_tile_type_count = sum(1 for count in counts_34 if count > 0)
    return 6 - pair_type_count + max(0, 7 - unique_tile_type_count)


def _kokushi_shanten(counts_34: tuple[int, ...]) -> int:
    terminal_unique_count = sum(1 for tile_34 in TERMINAL_AND_HONOR_TILE_34 if counts_34[tile_34] > 0)
    has_pair = any(counts_34[tile_34] >= 2 for tile_34 in TERMINAL_AND_HONOR_TILE_34)
    return 13 - terminal_unique_count - (1 if has_pair else 0)


def _normal_hand_shanten(counts_34: tuple[int, ...], open_meld_count: int) -> int:
    return _normal_shanten_dfs(counts_34, open_meld_count, 0, 0)


@lru_cache(maxsize=None)
def _normal_shanten_dfs(
    counts_34: tuple[int, ...],
    meld_count: int,
    taatsu_count: int,
    pair_count: int,
) -> int:
    first_tile_34 = next((tile_34 for tile_34, count in enumerate(counts_34) if count > 0), -1)
    if first_tile_34 < 0:
        effective_taatsu = min(taatsu_count, MAX_HAND_GROUP_COUNT - meld_count)
        return 8 - meld_count * 2 - effective_taatsu - pair_count

    best_shanten = 8
    tile_count = counts_34[first_tile_34]

    # Branch 1: ignore one copy of the current tile and continue decomposing the rest.
    next_counts = list(counts_34)
    next_counts[first_tile_34] -= 1
    best_shanten = min(
        best_shanten,
        _normal_shanten_dfs(tuple(next_counts), meld_count, taatsu_count, pair_count),
    )

    # Branch 2: consume complete melds first when possible.
    if meld_count < MAX_HAND_GROUP_COUNT and tile_count >= 3:
        next_counts = list(counts_34)
        next_counts[first_tile_34] -= 3
        best_shanten = min(
            best_shanten,
            _normal_shanten_dfs(tuple(next_counts), meld_count + 1, taatsu_count, pair_count),
        )
    if (
        meld_count < MAX_HAND_GROUP_COUNT
        and first_tile_34 < 27
        and first_tile_34 % 9 <= 6
        and counts_34[first_tile_34 + 1] > 0
        and counts_34[first_tile_34 + 2] > 0
    ):
        next_counts = list(counts_34)
        next_counts[first_tile_34] -= 1
        next_counts[first_tile_34 + 1] -= 1
        next_counts[first_tile_34 + 2] -= 1
        best_shanten = min(
            best_shanten,
            _normal_shanten_dfs(tuple(next_counts), meld_count + 1, taatsu_count, pair_count),
        )

    # Branch 3: head and taatsu candidates only matter until four total groups are filled.
    if tile_count >= 2 and pair_count == 0:
        next_counts = list(counts_34)
        next_counts[first_tile_34] -= 2
        best_shanten = min(
            best_shanten,
            _normal_shanten_dfs(tuple(next_counts), meld_count, taatsu_count, 1),
        )
    if taatsu_count < MAX_HAND_GROUP_COUNT and tile_count >= 2:
        next_counts = list(counts_34)
        next_counts[first_tile_34] -= 2
        best_shanten = min(
            best_shanten,
            _normal_shanten_dfs(tuple(next_counts), meld_count, taatsu_count + 1, pair_count),
        )
    if (
        taatsu_count < MAX_HAND_GROUP_COUNT
        and first_tile_34 < 27
        and first_tile_34 % 9 <= 7
        and counts_34[first_tile_34 + 1] > 0
    ):
        next_counts = list(counts_34)
        next_counts[first_tile_34] -= 1
        next_counts[first_tile_34 + 1] -= 1
        best_shanten = min(
            best_shanten,
            _normal_shanten_dfs(tuple(next_counts), meld_count, taatsu_count + 1, pair_count),
        )
    if (
        taatsu_count < MAX_HAND_GROUP_COUNT
        and first_tile_34 < 27
        and first_tile_34 % 9 <= 6
        and counts_34[first_tile_34 + 2] > 0
    ):
        next_counts = list(counts_34)
        next_counts[first_tile_34] -= 1
        next_counts[first_tile_34 + 2] -= 1
        best_shanten = min(
            best_shanten,
            _normal_shanten_dfs(tuple(next_counts), meld_count, taatsu_count + 1, pair_count),
        )

    return best_shanten
