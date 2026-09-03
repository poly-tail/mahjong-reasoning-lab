from __future__ import annotations

from sutehai import Discard, DrawType, Player
from ui import table_renderer


class DummyCanvas:
    pass


def _discard(tile_id: int, *, called: bool = False) -> Discard:
    return Discard(tile_id=tile_id, draw_type=DrawType.TEDASHI, called=called)


def _identity(epoch: int, logical: object) -> tuple[object, int, object]:
    return ("river_epoch", epoch, logical)


def test_same_live_river_epoch_preserves_cache_despite_logical_identity_change() -> None:
    assert (
        table_renderer._same_round_discard_cache_identity(
            _identity(7, ("round", 1)),
            _identity(7, ("wgc", "different-wrapper")),
        )
        is True
    )


def test_epoch_change_breaks_cache_even_when_logical_identity_same() -> None:
    assert (
        table_renderer._same_round_discard_cache_identity(
            _identity(7, ("round", 1)),
            _identity(8, ("round", 1)),
        )
        is False
    )


def test_same_epoch_empty_projection_does_not_wipe_previous_base_river() -> None:
    canvas = DummyCanvas()
    canvas.round_discard_map_cache_identity = _identity(11, ("round", 1))
    canvas.current_round_identity = _identity(11, ("bridge-empty-projection", 1))
    canvas.round_discard_map_cache = {
        Player.JICHA: [_discard(1), _discard(2)],
        Player.SHIMOCHA: [],
        Player.TOIMEN: [],
        Player.KAMICHA: [],
    }

    merged, retained = table_renderer._merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained == 2
    assert [discard.tile_id for discard in merged[Player.JICHA]] == [1, 2]
    assert all(discard.called for discard in merged[Player.JICHA])


def test_epoch_change_empty_river_resets_previous_base_river() -> None:
    canvas = DummyCanvas()
    canvas.round_discard_map_cache_identity = _identity(11, ("round", 1))
    canvas.current_round_identity = _identity(12, ("round", 2))
    canvas.round_discard_map_cache = {
        Player.JICHA: [_discard(1), _discard(2)],
        Player.SHIMOCHA: [],
        Player.TOIMEN: [],
        Player.KAMICHA: [],
    }

    merged, retained = table_renderer._merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained == 0
    assert merged[Player.JICHA] == []


def test_unknown_identity_empty_projection_restores_from_render_backup() -> None:
    canvas = DummyCanvas()
    canvas.round_discard_map_cache_identity = None
    canvas.current_round_identity = None
    canvas.round_discard_map_cache = {
        Player.JICHA: [],
        Player.SHIMOCHA: [],
        Player.TOIMEN: [],
        Player.KAMICHA: [],
    }
    canvas.base_river_render_backup_identity = _identity(11, ("round", 1))
    canvas.base_river_render_backup_map = {
        Player.JICHA: [_discard(1), _discard(2)],
        Player.SHIMOCHA: [],
        Player.TOIMEN: [],
        Player.KAMICHA: [],
    }

    merged, retained = table_renderer._merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained == 2
    assert [discard.tile_id for discard in merged[Player.JICHA]] == [1, 2]
    assert all(discard.called for discard in merged[Player.JICHA])
    assert canvas.round_discard_map_cache_identity == _identity(11, ("round", 1))


def test_epoch_change_empty_input_does_not_restore_from_render_backup() -> None:
    canvas = DummyCanvas()
    canvas.round_discard_map_cache_identity = None
    canvas.current_round_identity = _identity(12, ("round", 2))
    canvas.round_discard_map_cache = {
        Player.JICHA: [],
        Player.SHIMOCHA: [],
        Player.TOIMEN: [],
        Player.KAMICHA: [],
    }
    canvas.base_river_render_backup_identity = _identity(11, ("round", 1))
    canvas.base_river_render_backup_map = {
        Player.JICHA: [_discard(1), _discard(2)],
        Player.SHIMOCHA: [],
        Player.TOIMEN: [],
        Player.KAMICHA: [],
    }

    merged, retained = table_renderer._merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained == 0
    assert merged[Player.JICHA] == []
    assert canvas.round_discard_map_cache_identity == _identity(12, ("round", 2))
