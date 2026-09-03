from __future__ import annotations

from capture.fragment_parser import _reinit_requires_new_round
from capture.state import CaptureState, Discard as CaptureDiscard
from sutehai import Discard, DrawType, Player
from ui.table_renderer import (
    _merge_discard_map_with_round_cache,
    _same_round_discard_cache_identity,
)


class DummyCanvas:
    pass


def river(tile_id: int, *, called: bool = False) -> Discard:
    return Discard(tile_id=tile_id, draw_type=DrawType.TEDASHI, called=called)


def empty_map() -> dict[Player, list[Discard]]:
    return {player: [] for player in Player}


def test_init_wrapper_with_same_underlying_round_keeps_renderer_continuity() -> None:
    assert _same_round_discard_cache_identity(
        "game:0:0:0:0",
        (("init", "game:0:0:0:0", 3), 3),
    ) is True


def test_non_empty_shorter_input_is_defensively_merged_even_when_identity_changes() -> None:
    canvas = DummyCanvas()
    canvas.current_round_identity = "old-provisional"
    first = empty_map()
    first[Player.JICHA] = [river(1), river(2), river(3)]
    merged_first, retained_first = _merge_discard_map_with_round_cache(canvas, first)
    assert retained_first == 0
    assert [d.tile_id for d in merged_first[Player.JICHA]] == [1, 2, 3]

    canvas.current_round_identity = (("wgc", "known-round-id", 1), 1)
    short_projection = empty_map()
    short_projection[Player.JICHA] = [river(2)]
    merged_second, retained_second = _merge_discard_map_with_round_cache(canvas, short_projection)

    assert retained_second >= 2
    assert [d.tile_id for d in merged_second[Player.JICHA]][:3] == [1, 2, 3]
    assert merged_second[Player.JICHA][0].called is True
    assert merged_second[Player.JICHA][2].called is True


def test_empty_input_with_changed_identity_resets_renderer_river() -> None:
    canvas = DummyCanvas()
    canvas.current_round_identity = "old-round"
    first = empty_map()
    first[Player.JICHA] = [river(1), river(2)]
    _merge_discard_map_with_round_cache(canvas, first)

    canvas.current_round_identity = "new-round"
    merged, retained = _merge_discard_map_with_round_cache(canvas, empty_map())
    assert retained == 0
    assert all(not merged[player] for player in Player)


def test_empty_input_with_changed_init_wrapper_resets_renderer_river() -> None:
    canvas = DummyCanvas()
    canvas.current_round_identity = (("init", "game:0:0:0:0", 1), 1)
    first = empty_map()
    first[Player.JICHA] = [river(1), river(2)]
    _merge_discard_map_with_round_cache(canvas, first)

    canvas.current_round_identity = (("init", "game:0:0:0:0", 2), 2)
    merged, retained = _merge_discard_map_with_round_cache(canvas, empty_map())
    assert retained == 0
    assert all(not merged[player] for player in Player)


def test_reinit_with_incomplete_current_key_reuses_packet_round_instead_of_resetting() -> None:
    state = CaptureState()
    round_state = state.begin_round(started_from_init_like=False)
    # Current packet-only round has no kyoku/honba/oya yet, but already has a visible discard.
    round_state.discards[0].append(CaptureDiscard(tile_136=0))

    attrs = {
        "seed": "0,0,0,1,2,3",
        "oya": "0",
        # Same tile kind as current discard, but a different physical copy.
        "kawa0": "1",
    }

    assert _reinit_requires_new_round(state, round_state, attrs) is False
