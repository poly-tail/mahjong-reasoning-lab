from __future__ import annotations

import copy

import app.main as app_main
from capture.fragment_parser import (
    _mark_called_discard,
    _merge_snapshot_discards_with_previous_history,
    _rebuild_tracker_from_round,
)
from capture.state import CaptureState, Discard as CaptureDiscard, Meld, build_round_id
from sutehai import Discard as UiDiscard, DrawType, Player
from ui.table_renderer import _merge_discard_map_with_round_cache


def _capture_discard(tile_136: int, *, called: bool = False) -> CaptureDiscard:
    return CaptureDiscard(tile_136=tile_136, called=called)


def _bridge_snapshot() -> dict[str, object]:
    return {
        "ok": True,
        "playerNames": ["self", "shimo", "toimen", "kami"],
        "scores": [25000, 25000, 25000, 25000],
        "kyokuIndex": 0,
        "honba": 0,
        "kyotaku": 0,
        "oya": 0,
        "doraIndicators136": [],
        "handTiles136": [0, 4, 8, 12, 20, 24, 28, 32, 36, 40, 44, 48, 56],
        "riverEntriesBySeat": [
            [{"tile34Index": 0, "tsumogiri": False, "riichiMarkerBefore": False}],
            [],
            [],
            [],
        ],
    }


class _Canvas:
    pass


def test_reinit_projection_does_not_consume_uncalled_same_kind_after_called_gap() -> None:
    previous = [_capture_discard(0, called=True)]
    snapshot = [_capture_discard(1, called=False)]

    merged = _merge_snapshot_discards_with_previous_history(snapshot, previous)

    assert len(merged) == 2
    assert merged[0] is previous[0]
    assert merged[0].called is True
    assert merged[1] is snapshot[0]
    assert merged[1].called is False


def test_bridge_existing_round_keeps_called_same_kind_history_as_projection_only() -> None:
    state = CaptureState()
    state.game_id = "game-123"
    round_state = state.begin_round(started_from_init_like=False)
    round_state.kyoku_index = 0
    round_state.honba = 0
    round_state.kyotaku = 0
    round_state.oya = 0
    round_state.round_id = build_round_id("game-123", 0, 0, 0, 0)
    called_history = _capture_discard(0, called=True)
    round_state.discards[0].append(called_history)
    snapshot = copy.deepcopy(_bridge_snapshot())

    summary = app_main._import_tenhou_ui_bridge_table_snapshot(state, snapshot)

    assert summary["importMode"] == "metadata_only"
    assert state.current_round is round_state
    assert round_state.discards[0] == [called_history]
    assert round_state.discards[0][0].called is True
    assert len(round_state.browser_visible_river_projection[0]) == 1
    assert round_state.browser_visible_river_projection[0][0]["tile34Index"] == 0


def test_renderer_round_cache_retains_called_same_kind_gap_as_display_only() -> None:
    canvas = _Canvas()
    cached = UiDiscard(tile_id=1, draw_type=DrawType.TEDASHI, called=True)
    current = UiDiscard(tile_id=1, draw_type=DrawType.TEDASHI, called=False)
    canvas.current_round_identity = ("round-1", 0)
    canvas.round_discard_map_cache_identity = "round-1"
    canvas.round_discard_map_cache = {
        player: ([cached] if player is Player.JICHA else [])
        for player in Player
    }

    merged, retained_count = _merge_discard_map_with_round_cache(
        canvas,
        {Player.JICHA: [current]},
    )

    assert retained_count == 1
    assert merged[Player.JICHA] == [cached, current]
    assert canvas.round_discard_map_cache[Player.JICHA] == [cached, current]


def test_mark_called_discard_same_kind_fallback_updates_metadata_only() -> None:
    state = CaptureState()
    round_state = state.begin_round()
    round_state.discards[0].append(_capture_discard(16))
    _rebuild_tracker_from_round(state)

    meld = Meld(
        who=1,
        raw_m=0,
        meld_type="pon",
        from_who=3,
        called_tile_id=17,
        is_open=True,
    )
    _mark_called_discard(state, round_state, meld)

    assert len(round_state.discards[0]) == 1
    assert round_state.discards[0][0].called is True
    assert state.tracker.discards[Player(0)][0].called is True
