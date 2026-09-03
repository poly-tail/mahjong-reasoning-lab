from capture.fragment_parser import parse_fragment
from capture.live_river_store import RiverResetAuthority
from capture.state import Discard, GameState, build_round_key
from app.main import (
    _import_tenhou_ui_bridge_table_snapshot,
    build_discard_map_from_live_river_store,
)
from sutehai import Player


def _river_tiles(state: GameState, seat: int = 0) -> list[int | None]:
    return [
        getattr(discard, "tile_136", None)
        for discard in state.live_river_store.snapshot_by_seat().get(seat, ())
    ]


def test_init_resets_long_lived_river_and_seeds_kawa() -> None:
    state = GameState()
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=8))

    parse_fragment(
        state,
        None,
        '<INIT seed="0,0,0,0,0,0" ten="250,250,250,250" oya="0" kawa0="16" />',
    )

    assert _river_tiles(state, 0) == [16]


def test_spectator_initbylog_projection_does_not_reset_existing_live_river() -> None:
    state = GameState()
    state.game_id = "g"
    state.reset_live_river_for_authoritative_new_round(
        authority=RiverResetAuthority.INIT_NEW_ROUND,
        round_key=build_round_key("g", 0, 0, 0, 0),
    )
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=8))

    parse_fragment(
        state,
        None,
        (
            '<INITBYLOG seed="0,0,0,0,0,0" ten="250,250,250,250" '
            'oya="0" kawa0="16" />'
        ),
    )

    assert _river_tiles(state, 0) == [8]


def test_bridge_projection_does_not_reset_existing_live_river_store() -> None:
    state = GameState()
    state.game_id = "g"
    state.reset_live_river_for_authoritative_new_round(
        authority=RiverResetAuthority.INIT_NEW_ROUND,
        round_key=build_round_key("g", 1, 0, 0, 0),
    )
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=8))

    result = _import_tenhou_ui_bridge_table_snapshot(
        state,
        {
            "riverEntriesBySeat": [[{"tile34Index": 0, "tsumogiri": False}], [], [], []],
            "handTiles136": [],
            "doraIndicators136": [],
            "playerNames": ["a", "b", "c", "d"],
            "scores": [25000, 25000, 25000, 25000],
            "kyokuIndex": 0,
            "honba": 0,
            "kyotaku": 0,
            "oya": 0,
        },
    )

    assert result["importMode"] == "metadata_only"
    assert _river_tiles(state, 0) == [8]
    render_map = build_discard_map_from_live_river_store(state)
    assert len(render_map[Player.JICHA]) == 1


def test_bridge_same_round_projection_does_not_shorten_live_river() -> None:
    state = GameState()
    parse_fragment(
        state,
        None,
        '<INIT seed="0,0,0,0,0,0" ten="250,250,250,250" oya="0" kawa0="0,4" />',
    )
    before = _river_tiles(state, 0)

    result = _import_tenhou_ui_bridge_table_snapshot(
        state,
        {
            "riverEntriesBySeat": [[{"tile34Index": 1, "tsumogiri": False}], [], [], []],
            "handTiles136": [],
            "doraIndicators136": [],
            "playerNames": ["a", "b", "c", "d"],
            "scores": [25000, 25000, 25000, 25000],
            "kyokuIndex": 0,
            "honba": 0,
            "kyotaku": 0,
            "oya": 0,
        },
    )

    assert result["importMode"] == "metadata_only"
    assert _river_tiles(state, 0) == before


def test_packet_first_round_appends_without_resetting_existing_live_river_store() -> None:
    state = GameState()
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=8))

    parse_fragment(state, None, "D0")

    assert _river_tiles(state, 0) == [8, 0]
