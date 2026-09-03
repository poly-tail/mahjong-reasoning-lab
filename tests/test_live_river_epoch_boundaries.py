from types import SimpleNamespace

from app.main import build_live_round_identity, build_live_table_snapshot
from capture.live_river_store import RiverResetAuthority
from capture.state import CaptureState, Discard as CaptureDiscard
from sutehai import Discard, DrawType, Player
from ui.table_renderer import (
    _merge_discard_map_with_round_cache,
    _same_round_discard_cache_identity,
)


def _discard(tile_id: int, *, called: bool = False) -> Discard:
    return Discard(tile_id=tile_id, draw_type=DrawType.TEDASHI, called=called)


def test_live_round_identity_changes_on_authoritative_river_reset_even_same_logical_round() -> None:
    state = CaptureState()
    round_state = state.begin_round(started_from_init_like=True)
    round_state.round_id = "game-1-east-1-0"

    before = build_live_round_identity(state)
    state.reset_live_river_for_authoritative_new_round(
        authority=RiverResetAuthority.INIT_NEW_ROUND,
        round_key=round_state.round_key,
    )
    after = build_live_round_identity(state)

    assert before != after
    assert before[0] == "river_epoch"
    assert after[0] == "river_epoch"
    assert after[1] == before[1] + 1


def test_renderer_round_cache_identity_breaks_when_live_river_epoch_changes() -> None:
    assert (
        _same_round_discard_cache_identity(
            ("river_epoch", 1, "round-a"),
            ("river_epoch", 2, "round-a"),
        )
        is False
    )


def test_renderer_does_not_retain_previous_river_when_live_river_epoch_changes() -> None:
    canvas = SimpleNamespace(
        current_round_identity=("river_epoch", 2, "round-b"),
        round_discard_map_cache_identity=("river_epoch", 1, "round-a"),
        round_discard_map_cache={
            Player.JICHA: [_discard(1), _discard(2), _discard(3)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    merged, retained = _merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [_discard(9)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained == 0
    assert [discard.tile_id for discard in merged[Player.JICHA]] == [9]
    assert [discard.tile_id for discard in canvas.round_discard_map_cache[Player.JICHA]] == [9]


def test_renderer_retains_short_projection_only_within_same_live_river_epoch() -> None:
    canvas = SimpleNamespace(
        current_round_identity=("river_epoch", 1, "round-a"),
        round_discard_map_cache_identity=("river_epoch", 1, "round-a"),
        round_discard_map_cache={
            Player.JICHA: [_discard(1), _discard(2), _discard(3)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    merged, retained = _merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [_discard(2)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained >= 1
    assert [discard.tile_id for discard in merged[Player.JICHA]] == [1, 2, 3]
    assert merged[Player.JICHA][0].called is True


def test_build_live_table_snapshot_uses_live_river_store_even_when_tracker_is_empty() -> None:
    state = CaptureState()
    state.begin_round(started_from_init_like=True)
    state.live_river_store.append_discard(
        seat=1,
        discard=CaptureDiscard(tile_136=52, raw_tag="E52"),
    )
    state.tracker.discards[Player.SHIMOCHA] = []

    snapshot = build_live_table_snapshot(state)

    assert snapshot.round_identity[0] == "river_epoch"
    assert [discard.tag for discard in snapshot.discard_map[Player.SHIMOCHA]] == ["E52"]
