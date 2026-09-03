from capture.fragment_parser import ParsedTag, parse_spectator_init
from capture.live_river_store import RiverResetAuthority
from capture.state import Discard, GameState


def _parsed(tag: str, attrs: dict[str, object]) -> ParsedTag:
    return ParsedTag(tag_name=tag, raw_tag=f"<{tag}/>", attrs=dict(attrs), source_format="xml")


def _seed_live_river(
    state: GameState,
    *,
    game_id: str = "old",
    round_tuple: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> None:
    kyoku, honba, kyotaku, oya = round_tuple
    state.game_id = game_id
    state.live_river_store.reset_for_authoritative_new_round(
        authority=RiverResetAuthority.INIT_NEW_ROUND,
        round_key=(game_id, kyoku, honba, kyotaku, oya),
        allow_non_empty_clear=True,
        reset_source="test_seed",
    )
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=0))


def test_spectator_initbylog_different_game_id_resets_non_empty_live_river_and_seeds_snapshot() -> None:
    state = GameState(parser_mode="spectator_live")
    _seed_live_river(state, game_id="old-game", round_tuple=(0, 0, 0, 0))

    parse_spectator_init(
        state,
        None,
        _parsed(
            "INITBYLOG",
            {
                "log": "new-game",
                "seed": "0,0,0,0,0,0",
                "oya": "0",
                "kawa0": "8",
            },
        ),
    )

    snapshot = state.live_river_store.snapshot_by_seat()
    assert [discard.tile_136 for discard in snapshot[0]] == [8]
    assert state.live_river_store.round_key is not None
    assert state.live_river_store.round_key[0] == "new-game"


def test_spectator_wgc_same_game_same_round_is_projection_only_and_does_not_shorten_live_river() -> None:
    state = GameState(parser_mode="spectator_live")
    _seed_live_river(state, game_id="same-game", round_tuple=(0, 0, 0, 0))

    parse_spectator_init(
        state,
        None,
        _parsed(
            "WGC",
            {
                "log": "same-game",
                "seed": "0,0,0,0,0,0",
                "oya": "0",
                "kawa0": "8",
            },
        ),
    )

    snapshot = state.live_river_store.snapshot_by_seat()
    assert [discard.tile_136 for discard in snapshot[0]] == [0]


def test_spectator_initbylog_different_round_tuple_resets_non_empty_live_river() -> None:
    state = GameState(parser_mode="spectator_live")
    _seed_live_river(state, game_id="same-game", round_tuple=(0, 0, 0, 0))

    parse_spectator_init(
        state,
        None,
        _parsed(
            "INITBYLOG",
            {
                "log": "same-game",
                "seed": "1,0,0,0,0,0",
                "oya": "1",
                "kawa0": "12",
            },
        ),
    )

    snapshot = state.live_river_store.snapshot_by_seat()
    assert [discard.tile_136 for discard in snapshot[0]] == [12]
