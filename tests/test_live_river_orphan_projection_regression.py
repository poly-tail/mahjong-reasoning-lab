from types import SimpleNamespace

from app.main import build_live_round_identity, _import_tenhou_ui_bridge_table_snapshot
from capture.fragment_parser import (
    ParsedTag,
    _reinit_requires_new_round,
    parse_spectator_init,
)
from capture.live_river_store import RiverResetAuthority
from capture.state import Discard, GameState, build_round_key
from ui.table_renderer import (
    Discard as RenderDiscard,
    DrawType,
    Player,
    _merge_discard_map_with_round_cache,
)


def _state_with_orphan_live_river() -> GameState:
    state = GameState()
    state.game_id = "g"
    key = build_round_key("g", 0, 0, 0, 1)
    state.reset_live_river_for_authoritative_new_round(
        authority=RiverResetAuthority.INIT_NEW_ROUND,
        round_key=key,
    )
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=0, raw_tag="D0"))
    state.current_round = None
    return state


def test_reinit_with_orphan_live_river_same_key_is_not_new_round() -> None:
    state = _state_with_orphan_live_river()
    attrs = {"seed": "0,0,0,0,0,0", "oya": "1", "kawa0": "4"}

    assert _reinit_requires_new_round(state, state.current_round, attrs) is False


def test_reinit_with_orphan_live_river_different_complete_key_is_new_round() -> None:
    state = _state_with_orphan_live_river()
    attrs = {"seed": "1,0,0,0,0,0", "oya": "2", "kawa0": "4"}

    assert _reinit_requires_new_round(state, state.current_round, attrs) is True


def test_spectator_projection_does_not_reset_orphan_live_river() -> None:
    state = _state_with_orphan_live_river()
    before_epoch = state.live_river_store.epoch
    parsed = ParsedTag(
        tag_name="WGC",
        raw_tag="<WGC seed='0,0,0,0,0,0' oya='1' kawa0='4' />",
        attrs={"seed": "0,0,0,0,0,0", "oya": "1", "kawa0": "4"},
        source_format="xml",
    )

    parse_spectator_init(state, None, parsed)

    assert state.live_river_store.epoch == before_epoch
    assert state.live_river_store.counts_by_seat()[0] == 1
    assert state.current_round is not None


def test_bridge_projection_does_not_reset_orphan_live_river() -> None:
    state = _state_with_orphan_live_river()
    before_epoch = state.live_river_store.epoch

    result = _import_tenhou_ui_bridge_table_snapshot(
        state,
        {
            "handTiles136": list(range(13)),
            "doraIndicators136": [],
            "riverEntriesBySeat": {
                "0": [{"tile34Index": 1, "tsumogiri": False}],
                "1": [],
                "2": [],
                "3": [],
            },
            "kyokuIndex": 0,
            "honba": 0,
            "kyotaku": 0,
            "oya": 1,
        },
    )

    assert result["importMode"] == "metadata_only"
    assert state.live_river_store.epoch == before_epoch
    assert state.live_river_store.counts_by_seat()[0] == 1


def test_live_round_identity_survives_without_current_round_when_river_exists() -> None:
    state = _state_with_orphan_live_river()

    assert build_live_round_identity(state) == (
        "river_epoch",
        state.live_river_store.epoch,
        state.live_river_store.round_key,
    )


def test_same_epoch_empty_render_input_retains_previous_base_river() -> None:
    canvas = SimpleNamespace(
        current_round_identity=("river_epoch", 3, "round-a"),
        round_discard_map_cache_identity=("river_epoch", 3, "round-a"),
        round_discard_map_cache={
            Player.JICHA: [RenderDiscard(tile_id=0, draw_type=DrawType.TEDASHI)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    merged, retained = _merge_discard_map_with_round_cache(
        canvas,
        {player: [] for player in Player},
    )

    assert retained == 1
    assert len(merged[Player.JICHA]) == 1
    assert merged[Player.JICHA][0].called is True
