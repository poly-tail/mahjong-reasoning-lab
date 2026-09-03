from __future__ import annotations

import pytest

from capture.discard_ledger import DiscardMutationError
from capture.state import Discard, RoundState


def test_round_state_discard_ledger_blocks_physical_shortening() -> None:
    round_state = RoundState()
    round_state.append_discard(0, Discard(tile_136=0))

    with pytest.raises(DiscardMutationError):
        round_state.discards[0].clear()
    with pytest.raises(DiscardMutationError):
        del round_state.discards[0][0]
    with pytest.raises(DiscardMutationError):
        round_state.discards[0] = []
    with pytest.raises(DiscardMutationError):
        round_state.discards = {0: []}

    assert [discard.tile_136 for discard in round_state.discards[0]] == [0]


def test_projection_import_is_append_only_and_marks_omitted_discards_called() -> None:
    round_state = RoundState()
    first = Discard(tile_136=0)
    second = Discard(tile_136=4)
    round_state.append_discard(0, first)
    round_state.append_discard(0, second)

    round_state.apply_discard_projection_non_destructive(
        projection_by_seat={0: [Discard(tile_136=4), Discard(tile_136=8)]},
        source="test_projection",
    )

    assert [(discard.tile_136, discard.called) for discard in round_state.discards[0]] == [
        (0, True),
        (4, False),
        (8, False),
    ]


def test_called_marking_is_metadata_only_and_prefers_exact_tile_id() -> None:
    round_state = RoundState()
    first_copy = Discard(tile_136=0)
    second_copy = Discard(tile_136=1)
    round_state.append_discard(0, first_copy)
    round_state.append_discard(0, second_copy)

    marked_index = round_state.mark_discard_called(source_seat=0, called_tile_136=0, lagged=2)

    assert marked_index == 0
    assert [(discard.tile_136, discard.called) for discard in round_state.discards[0]] == [
        (0, True),
        (1, False),
    ]
    assert len(round_state.discards[0]) == 2


def test_snapshot_by_seat_is_read_only() -> None:
    round_state = RoundState()
    round_state.append_discard(0, Discard(tile_136=0))

    snapshot = round_state.discard_ledger.snapshot_by_seat()

    assert snapshot[0][0].tile_136 == 0
    with pytest.raises(TypeError):
        snapshot[0] = ()
