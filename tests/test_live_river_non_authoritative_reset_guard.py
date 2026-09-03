from __future__ import annotations

import pytest

from capture.fragment_parser import _reset_live_hanchan_state
from capture.live_river_store import (
    LiveRiverStore,
    RiverMutationError,
    RiverResetAuthority,
)
from capture.state import Discard, GameState


def _discard(tile: int = 0) -> Discard:
    return Discard(tile_136=tile)


def test_non_empty_live_river_cannot_be_cleared_by_generic_init_authority_without_opt_in() -> None:
    store = LiveRiverStore()
    store.append_discard(seat=0, discard=_discard(0))
    before_epoch = store.epoch
    before_counts = store.counts_by_seat()

    with pytest.raises(RiverMutationError):
        store.reset_for_authoritative_new_round(
            authority=RiverResetAuthority.INIT_NEW_ROUND,
            round_key=("game", 0, 0, 0, 0),
            reset_source="bridge_or_wgc_projection",
        )

    assert store.epoch == before_epoch
    assert store.counts_by_seat() == before_counts


def test_actual_init_path_can_clear_non_empty_live_river_with_explicit_opt_in() -> None:
    store = LiveRiverStore()
    store.append_discard(seat=0, discard=_discard(0))

    store.reset_for_authoritative_new_round(
        authority=RiverResetAuthority.INIT_NEW_ROUND,
        round_key=("game", 1, 0, 0, 1),
        allow_non_empty_clear=True,
        reset_source="parse_init",
    )

    assert store.epoch == 1
    assert store.counts_by_seat() == {0: 0, 1: 0, 2: 0, 3: 0}


def test_confirmed_different_reinit_can_clear_non_empty_live_river_with_explicit_opt_in() -> None:
    store = LiveRiverStore()
    store.append_discard(seat=0, discard=_discard(0))

    store.reset_for_authoritative_new_round(
        authority=RiverResetAuthority.REINIT_DIFFERENT_ROUND_CONFIRMED,
        round_key=("game", 2, 0, 0, 2),
        allow_non_empty_clear=True,
        reset_source="parse_reinit_different_round",
    )

    assert store.epoch == 1
    assert store.counts_by_seat() == {0: 0, 1: 0, 2: 0, 3: 0}


def test_live_hanchan_resync_cannot_clear_non_empty_live_river() -> None:
    state = GameState()
    state.live_river_store.append_discard(seat=0, discard=_discard(0))
    before_epoch = state.live_river_store.epoch
    before_counts = state.live_river_store.counts_by_seat()

    _reset_live_hanchan_state(
        state,
        reason="unit test resync",
        preserve_player_metadata=True,
    )

    assert state.live_river_store.epoch == before_epoch
    assert state.live_river_store.counts_by_seat() == before_counts
    assert any(
        diagnostic.get("code") == "live_hanchan_reset"
        and diagnostic.get("blocked_live_river_reset")
        for diagnostic in state.diagnostics
    )
