from __future__ import annotations

from capture.fragment_parser import (
    ParsedTag,
    _reinit_requires_new_round,
    parse_spectator_init,
)
from capture.live_river_store import RiverProjectionSource
from capture.state import Discard as CaptureDiscard
from capture.state import GameState
from sutehai import Discard, DrawType, Player
from ui import table_renderer


class DummyCanvas:
    pass


def _ui_discard(tile_id: int, *, called: bool = False) -> Discard:
    return Discard(tile_id=tile_id, draw_type=DrawType.TEDASHI, called=called)


def test_render_cache_retains_same_round_short_projection_and_marks_gap_called() -> None:
    canvas = DummyCanvas()
    canvas.current_round_identity = ("round-1", 0)
    canvas.round_discard_map_cache_identity = table_renderer._round_discard_cache_identity(
        canvas.current_round_identity
    )
    canvas.round_discard_map_cache = {
        Player.JICHA: [_ui_discard(1)],
        Player.SHIMOCHA: [],
        Player.TOIMEN: [],
        Player.KAMICHA: [],
    }

    merged, retained = table_renderer._merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [_ui_discard(2)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained == 1
    assert [discard.tile_id for discard in merged[Player.JICHA]] == [1, 2]
    assert merged[Player.JICHA][0].called is True
    assert merged[Player.JICHA][1].called is False


def test_render_cache_does_not_let_called_same_kind_consume_later_visible_discard() -> None:
    canvas = DummyCanvas()
    canvas.current_round_identity = ("round-1", 0)
    canvas.round_discard_map_cache_identity = table_renderer._round_discard_cache_identity(
        canvas.current_round_identity
    )
    canvas.round_discard_map_cache = {
        Player.JICHA: [_ui_discard(5, called=True)],
        Player.SHIMOCHA: [],
        Player.TOIMEN: [],
        Player.KAMICHA: [],
    }

    merged, retained = table_renderer._merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [_ui_discard(5, called=False)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained == 1
    assert [discard.tile_id for discard in merged[Player.JICHA]] == [5, 5]
    assert merged[Player.JICHA][0].called is True
    assert merged[Player.JICHA][1].called is False


def test_reinit_round_reuse_compares_kawa_by_tile_kind_not_136_copy() -> None:
    state = GameState()
    round_state = state.begin_round(started_from_init_like=False)
    round_state.discards[0].append(CaptureDiscard(tile_136=0))  # 1m copy 0

    assert _reinit_requires_new_round(state, round_state, {"kawa0": "1"}) is False


def test_spectator_same_round_snapshot_preserves_called_discard_gap() -> None:
    state = GameState(parser_mode="spectator_live")
    round_state = state.begin_round(started_from_init_like=False)
    discard = CaptureDiscard(tile_136=0, called=True)
    round_state.discards[0].append(discard)
    state.live_river_store.append_discard(seat=0, discard=discard)

    parse_spectator_init(
        state,
        None,
        ParsedTag(
            tag_name="WGC",
            raw_tag='<WGC kawa0="4">',
            attrs={"kawa0": "4"},
            source_format="xmlish",
        ),
    )

    assert state.current_round is round_state
    assert [discard.tile_136 for discard in round_state.discards[0]] == [0]
    assert [discard.called for discard in round_state.discards[0]] == [True]
    assert [
        discard.tile_136
        for discard in state.live_river_store.snapshot_by_seat()[0]
    ] == [0]
    projections = state.live_river_store.projection_snapshot_by_source()
    assert [
        discard.tile_136
        for discard in projections[RiverProjectionSource.WGC.value][0]
    ] == [4]
