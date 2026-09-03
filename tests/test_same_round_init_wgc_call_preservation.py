from __future__ import annotations

from app.main import _same_live_discard_history_round
from sutehai import Discard, DrawType, Player
from ui.table_renderer import (
    _merge_discard_map_with_round_cache,
    _same_round_discard_cache_identity,
)


class DummyCanvas:
    pass


def _discard(tile_id: int, *, called: bool = False) -> Discard:
    return Discard(tile_id=tile_id, draw_type=DrawType.TEDASHI, called=called)


def test_init_to_wgc_same_underlying_round_keeps_renderer_continuity() -> None:
    previous_identity = (("init", "game-a:0:0:0:1", 1), 1)
    current_identity = (("wgc", "game-a:0:0:0:1", 2), 2)

    assert _same_round_discard_cache_identity(previous_identity, current_identity) is True
    assert _same_live_discard_history_round(previous_identity, current_identity) is True


def test_init_to_different_init_round_does_not_keep_renderer_continuity() -> None:
    previous_identity = (("init", "game-a:0:0:0:1", 1), 1)
    current_identity = (("init", "game-a:1:0:0:2", 2), 2)

    assert _same_round_discard_cache_identity(previous_identity, current_identity) is False
    assert _same_live_discard_history_round(previous_identity, current_identity) is False


def test_renderer_keeps_called_gap_when_same_round_wgc_projection_is_shorter() -> None:
    canvas = DummyCanvas()
    previous_identity = (("init", "game-a:0:0:0:1", 1), 1)
    current_identity = (("wgc", "game-a:0:0:0:1", 2), 2)
    canvas.round_discard_map_cache_identity = previous_identity[0]
    canvas.current_round_identity = current_identity
    canvas.round_discard_map_cache = {
        Player.JICHA: [_discard(1)],
        Player.SHIMOCHA: [],
        Player.TOIMEN: [],
        Player.KAMICHA: [],
    }

    merged, retained = _merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [_discard(2)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained == 1
    assert [discard.tile_id for discard in merged[Player.JICHA]] == [1, 2]
    assert merged[Player.JICHA][0].called is True
    assert merged[Player.JICHA][1].called is False
