from __future__ import annotations

import app.main as app_main
import pytest
from capture.fragment_parser import _rebuild_tracker_from_round, _reset_live_hanchan_state, parse_fragment
from capture.live_river_store import RiverMutationError, RiverProjectionSource, RiverResetAuthority
from capture.state import CaptureState, Discard, build_round_key
from sutehai import DiscardHistoryMutationError, Player


def _round_state_for_live_snapshot(state: CaptureState) -> None:
    round_state = state.begin_round()
    round_state.round_id = "test-round"
    round_state.kyoku_index = 0
    round_state.honba = 0
    round_state.kyotaku = 0
    round_state.oya = 0
    round_state.oya_rel = 0
    state.live_update_sequence = 1
    state.sync_current_round_context()


def test_live_river_store_survives_round_replacement() -> None:
    state = CaptureState()
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=0))

    state.begin_round()

    assert [discard.tile_136 for discard in state.live_river_store.snapshot_by_seat()[0]] == [0]


def test_live_river_store_survives_reset_live_session() -> None:
    state = CaptureState()
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=0))

    state.reset_live_session()

    assert [discard.tile_136 for discard in state.live_river_store.snapshot_by_seat()[0]] == [0]


def test_reset_live_session_preserves_discard_derived_views_when_base_river_exists() -> None:
    state = CaptureState()
    round_state = state.begin_round()
    round_discard = Discard(tile_136=0)
    round_state.append_discard(0, round_discard)
    state.live_river_store.append_discard(seat=0, discard=round_discard)
    state.tracker.add_discard(Player.JICHA, 1)
    state.live_stable_discard_round_identity = "round"
    state.live_stable_discard_map = {Player.JICHA: [state.tracker.discards[Player.JICHA][0]]}

    state.reset_live_session()

    assert state.current_round is round_state
    assert [discard.tile_136 for discard in state.current_round.discards[0]] == [0]
    assert [discard.tile_id for discard in state.tracker.discards[Player.JICHA]] == [1]
    assert state.live_stable_discard_map


def test_init_force_resets_discard_state_even_when_base_river_exists() -> None:
    state = CaptureState()
    state.game_id = "2026070400gm-test"
    state.go_type = 169
    state.room_class_code = "phoenix"
    state.room_class_label = "houou"
    previous_round = state.begin_round()
    round_discard = Discard(tile_136=0)
    previous_round.append_discard(0, round_discard)
    state.live_river_store.append_discard(seat=0, discard=round_discard)
    state.tracker.add_discard(Player.JICHA, 1)
    state.live_stable_discard_round_identity = "old-round"
    state.live_stable_discard_map = {Player.JICHA: [state.tracker.discards[Player.JICHA][0]]}

    event = parse_fragment(
        state,
        1.0,
        (
            '{"tag":"INIT","seed":"1,0,0,2,0,3","ten":"250,250,250,250",'
            '"oya":"0","hai":"0,4,8,12,16,20,24,28,32,36,40,44,48"}'
        ),
    )

    assert event is not None
    assert event.event_type == "init"
    assert state.current_round is not previous_round
    assert state.game_id == "2026070400gm-test"
    assert state.go_type == 169
    assert state.room_class_code == "phoenix"
    assert state.room_class_label == "houou"
    assert state.live_river_store.counts_by_seat() == {0: 0, 1: 0, 2: 0, 3: 0}
    assert {player: list(state.tracker.discards[player]) for player in Player} == {
        player: [] for player in Player
    }
    assert state.live_stable_discard_map == {}
    assert state.current_round.discards == {0: [], 1: [], 2: [], 3: []}


def test_rebuild_tracker_from_round_prefers_live_river_store_when_present() -> None:
    state = CaptureState()
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=0))
    state.begin_round()

    _rebuild_tracker_from_round(state)

    assert [discard.tile_id for discard in state.tracker.discards[Player.JICHA]] == [1]


def test_tracker_discards_reject_shortening_without_init_or_reinit_reset() -> None:
    state = CaptureState()
    first = state.tracker.add_discard(Player.JICHA, 1)
    state.tracker.add_discard(Player.JICHA, 2)

    with pytest.raises(DiscardHistoryMutationError, match="cannot be shortened"):
        state.tracker.discards[Player.JICHA] = [first]
    with pytest.raises(DiscardHistoryMutationError, match="cannot be cleared"):
        state.tracker.discards[Player.JICHA].clear()
    with pytest.raises(DiscardHistoryMutationError, match="cannot be deleted"):
        state.tracker.discards[Player.JICHA].pop()


def test_tracker_discards_allow_authoritative_init_reinit_reset() -> None:
    state = CaptureState()
    state.tracker.add_discard(Player.JICHA, 1)

    with state.tracker.allow_discard_reset("init_new_round"):
        state.tracker.discards[Player.JICHA].clear()

    state.tracker.add_discard(Player.JICHA, 2)
    with state.tracker.allow_discard_reset("reinit_different_round"):
        state.tracker.discards[Player.JICHA] = []

    assert list(state.tracker.discards[Player.JICHA]) == []


def test_manual_user_reset_cannot_clear_existing_base_river() -> None:
    state = CaptureState()
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=0))
    before_epoch = state.live_river_store.epoch

    with pytest.raises(RiverMutationError, match="non-empty base river reset blocked"):
        state.reset_live_river_for_authoritative_new_round(
            authority=RiverResetAuthority.MANUAL_USER_RESET,
            round_key=None,
        )

    assert state.live_river_store.epoch == before_epoch
    assert [discard.tile_136 for discard in state.live_river_store.snapshot_by_seat()[0]] == [0]


def test_live_hanchan_reset_does_not_clear_existing_base_river() -> None:
    state = CaptureState()
    state.game_id = "g"
    _round_state_for_live_snapshot(state)
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=0))
    before_epoch = state.live_river_store.epoch

    _reset_live_hanchan_state(
        state,
        reason="test hanchan reset",
        preserve_player_metadata=True,
        previous_signature=("a", "b", "c", "d"),
        next_signature=("e", "f", "g", "h"),
        next_game_id="next",
    )

    assert state.live_river_store.epoch == before_epoch
    assert [discard.tile_136 for discard in state.live_river_store.snapshot_by_seat()[0]] == [0]
    assert state.diagnostics[-1]["code"] == "live_hanchan_reset"
    assert state.diagnostics[-1]["blocked_live_river_reset"]


def test_reinit_same_round_is_projection_only_for_base_river() -> None:
    state = CaptureState()
    parse_fragment(
        state,
        1.0,
        (
            '{"tag":"REINIT","seed":"0,0,0,0,0,0","ten":"250,250,250,250","oya":"0",'
            '"hai":"0,1,2,3,4,5,6,7,8,9,10,11,12","kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
        ),
    )
    parse_fragment(state, 2.0, "D0")

    parse_fragment(
        state,
        3.0,
        (
            '{"tag":"REINIT","seed":"0,0,0,0,0,0","ten":"250,250,250,250","oya":"0",'
            '"hai":"0,1,2,3,4,5,6,7,8,9,10,11,12","kawa0":"4","kawa1":"","kawa2":"","kawa3":""}'
        ),
    )

    assert [discard.tile_136 for discard in state.live_river_store.snapshot_by_seat()[0]] == [0]
    projections = state.live_river_store.projection_snapshot_by_source()
    assert [discard.tile_136 for discard in projections[RiverProjectionSource.REINIT_SAME_OR_UNKNOWN.value][0]] == [4]


def test_wgc_projection_does_not_reset_existing_base_river() -> None:
    state = CaptureState()
    state.game_id = "g"
    state.reset_live_river_for_authoritative_new_round(
        authority=RiverResetAuthority.INIT_NEW_ROUND,
        round_key=build_round_key("g", 0, 0, 0, 0),
    )
    state.live_river_store.append_discard(seat=0, discard=Discard(tile_136=0))

    parse_fragment(
        state,
        3.0,
        (
            '{"tag":"WGC","seed":"0,0,0,0,0,0","ten":"250,250,250,250","oya":"0",'
            '"kawa0":"4","kawa1":"","kawa2":"","kawa3":""}'
        ),
    )

    assert [discard.tile_136 for discard in state.live_river_store.snapshot_by_seat()[0]] == [0]
    projections = state.live_river_store.projection_snapshot_by_source()
    assert [discard.tile_136 for discard in projections[RiverProjectionSource.WGC.value][0]] == [4]


def test_non_init_reinit_tag_cannot_reset_existing_base_river(monkeypatch: pytest.MonkeyPatch) -> None:
    state = CaptureState()
    parse_fragment(
        state,
        1.0,
        (
            '{"tag":"REINIT","seed":"0,0,0,0,0,0","ten":"250,250,250,250","oya":"0",'
            '"hai":"0,1,2,3,4,5,6,7,8,9,10,11,12","kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
        ),
    )
    parse_fragment(state, 2.0, "D0")

    def _bad_parse_n(state: CaptureState, timestamp: float | None, parsed: object) -> object | None:
        state.reset_live_river_for_authoritative_new_round(
            authority=RiverResetAuthority.INIT_NEW_ROUND,
            round_key=None,
        )
        return None

    monkeypatch.setattr("capture.fragment_parser.parse_n", _bad_parse_n)

    with pytest.raises(RiverMutationError, match="non-empty base river reset blocked"):
        parse_fragment(state, 3.0, '<N who="1" m="51275"/>')


def test_n_count_guard_logs_discard_disappearance_cause(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = CaptureState()
    round_state = state.begin_round()
    discard = Discard(tile_136=0)
    round_state.append_discard(0, discard)
    state.live_river_store.append_discard(seat=0, discard=discard)
    state.tracker.add_discard(Player.JICHA, 1)
    log_path = tmp_path / "live_capture.log"
    monkeypatch.setattr("capture.fragment_parser.DEFAULT_LIVE_CAPTURE_LOG_PATH", log_path)

    def _bad_parse_n(state: CaptureState, timestamp: float | None, parsed: object) -> object | None:
        state.live_river_store._discards_by_seat[0].pop()
        return state.add_event(
            timestamp,
            "call",
            raw_tag=getattr(parsed, "raw_tag", ""),
        )

    monkeypatch.setattr("capture.fragment_parser.parse_n", _bad_parse_n)

    with pytest.raises(RiverMutationError, match="LiveRiverStore count changed"):
        parse_fragment(state, 3.0, '<N who="1" m="51275"/>')

    diagnostic = state.diagnostics[-1]
    assert diagnostic["code"] == "called_discard_disappearance_guard"
    assert diagnostic["cause"] == "call_event_shortened_discard_history"
    assert {
        "target": "LiveRiverStore",
        "seat": 0,
        "before": 1,
        "after": 0,
        "delta": -1,
    } in diagnostic["changes"]
    log_text = log_path.read_text(encoding="utf-8")
    assert "called_discard_disappearance_guard" in log_text
    assert "call_event_shortened_discard_history" in log_text


def test_live_snapshot_draws_from_live_river_store_when_tracker_is_empty() -> None:
    state = CaptureState()
    _round_state_for_live_snapshot(state)
    state.live_river_store.append_discard(
        seat=int(Player.SHIMOCHA),
        discard=Discard(tile_136=0, round_discard_index=0),
    )
    with state.tracker.allow_discard_reset("test_empty_tracker_regression"):
        state.tracker.discards[Player.SHIMOCHA].clear()

    snapshot = app_main.build_live_table_snapshot(state)

    assert [discard.tile_id for discard in snapshot.discard_map[Player.SHIMOCHA]] == [1]
