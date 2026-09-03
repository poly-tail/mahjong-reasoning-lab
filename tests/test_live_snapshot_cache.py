import unittest
import time
from unittest.mock import patch

import app.main as app_main
import ui.table_renderer as table_renderer
from capture.state import (
    CaptureState,
    Discard as LiveDiscard,
    Event as LiveEvent,
    LAG_FLAG_UNCONFIRMED,
)
from sutehai import Discard, DrawType, Player


def _build_live_capture_state() -> CaptureState:
    state = CaptureState()
    round_state = state.begin_round()
    round_state.round_id = "test-round"
    round_state.kyoku_index = 0
    round_state.honba = 0
    round_state.kyotaku = 0
    round_state.oya = 0
    round_state.oya_rel = 0

    live_discard = LiveDiscard(
        tile_136=0,
        round_discard_index=0,
        tsumogiri=False,
        event_index=0,
    )
    round_state.discards[int(Player.SHIMOCHA)].append(live_discard)
    state.live_river_store.append_discard(seat=int(Player.SHIMOCHA), discard=live_discard)
    tracker_discard = state.tracker.add_discard(Player.SHIMOCHA, 1)
    tracker_discard.round_discard_index = 0
    tracker_discard.event_index = 0
    state.live_update_sequence = 1
    state.sync_current_round_context()
    return state


def _build_round_only_capture_state() -> CaptureState:
    state = CaptureState()
    round_state = state.begin_round()
    round_state.round_id = "test-round"
    round_state.kyoku_index = 0
    round_state.honba = 0
    round_state.kyotaku = 0
    round_state.oya = 0
    round_state.oya_rel = 0
    state.live_update_sequence = 1
    state.sync_current_round_context()
    return state


def _build_render_discard(
    tile_id: int,
    round_discard_index: int,
    *,
    draw_type: DrawType = DrawType.TEDASHI,
    thinking_time_ms: float | None = None,
    lagged: int = 0,
) -> Discard:
    discard = Discard(tile_id=tile_id, draw_type=draw_type)
    discard.round_discard_index = round_discard_index
    discard.thinking_time_ms = thinking_time_ms
    discard.lagged = lagged
    return discard


def _append_live_round_discard(
    state: CaptureState,
    player: Player,
    tile_136: int,
    index: int,
    *,
    tsumogiri: bool = False,
    thinking_time_ms: float | None = None,
    lagged: int = 0,
) -> LiveDiscard:
    assert state.current_round is not None
    live_discard = LiveDiscard(
        tile_136=tile_136,
        round_discard_index=index,
        tsumogiri=tsumogiri,
        raw_tag=f"D{tile_136}",
        thinking_time_ms=thinking_time_ms,
        lagged=lagged,
        event_index=index,
    )
    state.current_round.discards[int(player)].append(live_discard)
    state.live_river_store.append_discard(seat=int(player), discard=live_discard)
    return live_discard


def _tile37_to_non_red_tile136(tile_id: int) -> int:
    tile_id = int(tile_id)
    if 1 <= tile_id <= 9:
        tile34 = tile_id - 1
    elif 11 <= tile_id <= 19:
        tile34 = tile_id - 2
    elif 21 <= tile_id <= 29:
        tile34 = tile_id - 3
    elif 31 <= tile_id <= 37:
        tile34 = tile_id - 4
    elif tile_id == 10:
        tile34 = 4
    elif tile_id == 20:
        tile34 = 13
    elif tile_id == 30:
        tile34 = 22
    else:
        tile34 = max(0, tile_id - 1)
    for copy_index in range(4):
        tile_136 = tile34 * 4 + copy_index
        if tile_136 not in {16, 52, 88}:
            return tile_136
    return tile34 * 4


def _append_render_discard_to_round(
    state: CaptureState,
    player: Player,
    discard: Discard,
) -> LiveDiscard:
    tile_136 = _tile37_to_non_red_tile136(int(discard.tile_id))
    return _append_live_round_discard(
        state,
        player,
        tile_136,
        int(discard.round_discard_index or 0),
        tsumogiri=discard.draw_type is DrawType.TSUMOGIRI,
        thinking_time_ms=discard.thinking_time_ms,
        lagged=int(getattr(discard, "lagged", 0) or 0),
    )


def _append_render_discards_to_round(
    state: CaptureState,
    player: Player,
    discards: list[Discard],
) -> None:
    for discard in discards:
        live_discard = _append_render_discard_to_round(state, player, discard)
        live_discard.called = bool(getattr(discard, "called", False))


def _live_suji_bundle_completed(state: CaptureState) -> bool:
    async_state = getattr(state, "live_suji_async_state", None)
    return int(getattr(async_state, "update_sequence", 0)) > 0


class _BusyStateLock:
    def acquire(self, *, blocking: bool = True) -> bool:
        return False

    def release(self) -> None:
        raise AssertionError("release should not be called for a busy lock")


def _build_minimal_live_table_snapshot(refresh_token: object) -> app_main.LiveTableSnapshot:
    return app_main.LiveTableSnapshot(
        discard_map={player: [] for player in Player},
        discard_red_tint_indices_by_seat={},
        hand_tiles=[],
        hand_draw_tile=None,
        hand_danger_percentages=[],
        opponent_suji_panel_summaries={},
        player_push_alert_percentages={},
        player_alert_indicators_by_seat={},
        player_score_diffs_by_seat={},
        player_names_by_seat={},
        meld_tiles=[],
        dora_indicator_tiles=[],
        round_events=[],
        round_info_panel=table_renderer.RoundInfoPanelData(),
        melds_by_player={player: [] for player in Player},
        visible_summary=app_main.VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
        ),
        round_identity=None,
        refresh_token=refresh_token,
        hand_recommendation_request_context=app_main.PystyleDisplayContext(),
    )


class LiveSnapshotCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        app_main._LIVE_DISCARD_RED_TINT_CACHE_SIGNATURE = None
        app_main._LIVE_DISCARD_RED_TINT_CACHE_VALUE = {}

    def test_build_live_table_snapshot_reuses_cached_snapshot_until_refresh_changes(self) -> None:
        state = _build_live_capture_state()

        with patch(
            "app.main._snapshot_live_capture_state",
            wraps=app_main._snapshot_live_capture_state,
        ) as snapshot_builder:
            first = app_main.build_live_table_snapshot(state)
            second = app_main.build_live_table_snapshot(state)
            state.mark_live_update()
            third = app_main.build_live_table_snapshot(state)

        if second.refresh_token == first.refresh_token and app_main.LIVE_ASYNC_BUNDLE_REFRESH_ENABLED:
            self.assertIs(first, second)
        else:
            if second.refresh_token != first.refresh_token:
                self.assertNotEqual(second.refresh_token, first.refresh_token)
            else:
                self.assertIsNotNone(second)
        self.assertIsNot(second, third)
        self.assertGreaterEqual(snapshot_builder.call_count, 2)

    def test_build_live_table_snapshot_carries_latest_raw_event_type(self) -> None:
        state = _build_live_capture_state()
        state.add_event(None, "initbylog")

        initbylog_snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(initbylog_snapshot.latest_event_type, "initbylog")

        state.add_event(None, "discard", seat=int(Player.SHIMOCHA), tile_136=4)
        discard_snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(discard_snapshot.latest_event_type, "discard")

    def test_build_live_table_snapshot_carries_recent_call_event_type(self) -> None:
        state = _build_live_capture_state()
        state.add_event(None, "call", seat=int(Player.SHIMOCHA), tile_136=72)
        state.add_event(None, "discard", seat=int(Player.SHIMOCHA), tile_136=46)

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(snapshot.latest_event_type, "discard")
        self.assertIn("call", snapshot.recent_event_types)
        self.assertEqual(snapshot.recent_event_types[-1], "discard")

    def test_build_fast_live_table_snapshot_carries_recent_call_event_type(self) -> None:
        state = _build_live_capture_state()
        base_snapshot = app_main.build_live_table_snapshot(state)
        state.add_event(None, "call", seat=int(Player.SHIMOCHA), tile_136=72)
        state.add_event(None, "discard", seat=int(Player.SHIMOCHA), tile_136=46)

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (int(state.live_update_sequence), 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        self.assertEqual(fast_snapshot.latest_event_type, "discard")
        self.assertIn("call", fast_snapshot.recent_event_types)

    def test_build_live_table_snapshot_carries_first_row_fast_trend_alert(self) -> None:
        state = _build_live_capture_state()
        assert state.current_round is not None
        state.hanchan_round_ordinal = 3
        state.current_round.hanchan_round_ordinal = 3
        state.first_row_thinking_avg_history_by_seat[int(Player.SHIMOCHA)] = [
            3000.0,
            2800.0,
        ]
        state.current_round.discards[int(Player.SHIMOCHA)][0].thinking_time_ms = 1200.0
        _append_live_round_discard(
            state,
            Player.SHIMOCHA,
            4,
            1,
            thinking_time_ms=1400.0,
        )
        _append_live_round_discard(
            state,
            Player.SHIMOCHA,
            8,
            2,
            thinking_time_ms=1300.0,
        )
        state.mark_live_update()

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertIn(
            "first_row_fast_trend:active",
            tuple(
                indicator.key
                for indicator in snapshot.player_alert_indicators_by_seat[
                    int(Player.SHIMOCHA)
                ]
            ),
        )

    def test_force_live_table_snapshot_reinit_invalidates_cached_snapshot(self) -> None:
        state = _build_live_capture_state()
        first = app_main.build_live_table_snapshot(state)
        state.cached_live_table_snapshot = first
        state.cached_live_table_snapshot_refresh_token = first.refresh_token
        previous_live_update_sequence = int(state.live_update_sequence)

        returned_refresh_token = app_main.force_live_table_snapshot_reinit(state)

        self.assertEqual(
            returned_refresh_token,
            (
                int(state.live_update_sequence),
                app_main._combined_live_async_update_sequence(state)
                if app_main.LIVE_ASYNC_BUNDLE_REFRESH_ENABLED
                else 0,
            ),
        )
        self.assertEqual(state.live_update_sequence, previous_live_update_sequence + 1)
        self.assertIsNone(state.cached_live_table_snapshot)
        self.assertIsNone(state.cached_live_table_snapshot_refresh_token)

    def test_async_live_table_snapshot_provider_publishes_worker_snapshot(self) -> None:
        state = CaptureState()
        current_token = {"value": (1, 0)}
        built_tokens: list[object] = []
        release_builder = app_main.threading.Event()

        def token_reader(_state: CaptureState) -> object:
            return current_token["value"]

        def snapshot_builder(_state: CaptureState) -> app_main.LiveTableSnapshot:
            token = current_token["value"]
            built_tokens.append(token)
            release_builder.wait(timeout=2.0)
            return _build_minimal_live_table_snapshot(token)

        provider = app_main.AsyncLiveTableSnapshotProvider(
            state,
            _build_minimal_live_table_snapshot((1, 0)),
            snapshot_builder=snapshot_builder,
            refresh_token_reader=token_reader,
            reinit_action=token_reader,
        )
        try:
            self.assertEqual(provider.current_refresh_token(), (1, 0))
            current_token["value"] = (2, 0)
            with provider._lock:
                provider._last_request_latest_monotonic_s = 0.0
            self.assertEqual(provider.current_refresh_token(), (2, 0))
            self.assertEqual(provider.current_snapshot().refresh_token, (2, 0))
            deadline = time.time() + 2.0
            while time.time() < deadline and not built_tokens:
                time.sleep(0.01)
            self.assertEqual(built_tokens, [(2, 0)])

            release_builder.set()
            deadline = time.time() + 2.0
            while time.time() < deadline:
                with provider._lock:
                    heavy_token = provider._latest_snapshot.refresh_token
                if heavy_token == (2, 0):
                    break
                time.sleep(0.01)

            with provider._lock:
                self.assertEqual(provider._latest_snapshot.refresh_token, (2, 0))
                self.assertIsNone(provider._latest_fast_snapshot)
            self.assertIn((2, 0), built_tokens)
        finally:
            release_builder.set()
            provider.stop()

    def test_async_live_table_snapshot_provider_defers_async_only_token_until_heavy_publish(self) -> None:
        state = CaptureState()
        state.live_update_sequence = 20
        completed_refresh_token = (20, 1 << 32)
        builder_started = app_main.threading.Event()
        release_builder = app_main.threading.Event()
        previous_danger = [
            {int(Player.KAMICHA): {"percentage": 17}},
        ]
        completed_danger = [
            {int(Player.KAMICHA): {"percentage": 43}},
        ]
        previous_summary = {
            int(Player.KAMICHA): {
                "is_loading": False,
                "menzen_alert_score": 1,
            }
        }
        completed_summary = {
            int(Player.KAMICHA): {
                "is_loading": False,
                "menzen_alert_score": 3,
            }
        }
        initial_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((19, 0)),
            hand_danger_percentages=previous_danger,
            opponent_suji_panel_summaries=previous_summary,
        )
        completed_snapshot = app_main.replace(
            initial_snapshot,
            refresh_token=completed_refresh_token,
            hand_danger_percentages=completed_danger,
            opponent_suji_panel_summaries=completed_summary,
        )

        def snapshot_builder(_state: CaptureState) -> app_main.LiveTableSnapshot:
            builder_started.set()
            release_builder.wait(timeout=2.0)
            return completed_snapshot

        def fast_snapshot_builder(
            _state: CaptureState,
            base_snapshot: app_main.LiveTableSnapshot,
            refresh_token: object | None,
        ) -> app_main.LiveTableSnapshot:
            return app_main.replace(base_snapshot, refresh_token=refresh_token)

        provider = app_main.AsyncLiveTableSnapshotProvider(
            state,
            initial_snapshot,
            snapshot_builder=snapshot_builder,
            fast_snapshot_builder=fast_snapshot_builder,
        )
        try:
            # A live-state change may already have published a fast frame.  The later async-only
            # change must compare against that effective frame, not the older heavy snapshot.
            live_fast_snapshot = provider.current_snapshot()
            self.assertEqual(live_fast_snapshot.refresh_token, (20, 0))
            self.assertTrue(builder_started.wait(timeout=1.0))

            app_main._get_live_suji_async_state(state).update_sequence = 1
            with provider._lock:
                provider._last_request_latest_monotonic_s = 0.0

            pending_snapshot = provider.current_snapshot()
            pending_token = pending_snapshot.refresh_token
            self.assertEqual(pending_token, (20, 0))
            self.assertEqual(
                pending_snapshot.hand_danger_percentages,
                previous_danger,
            )
            self.assertEqual(
                pending_snapshot.opponent_suji_panel_summaries,
                previous_summary,
            )

            release_builder.set()
            deadline = time.time() + 2.0
            while time.time() < deadline:
                with provider._lock:
                    published_token = provider._latest_snapshot.refresh_token
                if published_token == completed_refresh_token:
                    break
                time.sleep(0.01)

            completed = provider.current_snapshot()
            self.assertNotEqual(completed.refresh_token, pending_token)
            self.assertEqual(completed.hand_danger_percentages, completed_danger)
            self.assertEqual(
                completed.opponent_suji_panel_summaries,
                completed_summary,
            )
            self.assertTrue(
                table_renderer._should_use_live_async_only_refresh(
                    (pending_token, 4),
                    (completed.refresh_token, 4),
                )
            )
        finally:
            release_builder.set()
            provider.stop()

    def test_async_live_table_snapshot_provider_force_reinit_exposes_fast_snapshot(self) -> None:
        state = CaptureState()
        current_token = {"value": (1, 0)}
        release_builder = app_main.threading.Event()

        def token_reader(_state: CaptureState) -> object:
            return current_token["value"]

        def snapshot_builder(_state: CaptureState) -> app_main.LiveTableSnapshot:
            release_builder.wait(timeout=2.0)
            return _build_minimal_live_table_snapshot(current_token["value"])

        def reinit_action(_state: CaptureState) -> object:
            current_token["value"] = (3, 0)
            return current_token["value"]

        provider = app_main.AsyncLiveTableSnapshotProvider(
            state,
            _build_minimal_live_table_snapshot((1, 0)),
            snapshot_builder=snapshot_builder,
            refresh_token_reader=token_reader,
            reinit_action=reinit_action,
        )
        try:
            self.assertEqual(provider.force_reinit(), (3, 0))
            self.assertEqual(provider.current_snapshot().refresh_token, (3, 0))

            release_builder.set()
            deadline = time.time() + 2.0
            while time.time() < deadline:
                with provider._lock:
                    heavy_token = provider._latest_snapshot.refresh_token
                if heavy_token == (3, 0):
                    break
                time.sleep(0.01)

            with provider._lock:
                self.assertEqual(provider._latest_snapshot.refresh_token, (3, 0))
                self.assertIsNone(provider._latest_fast_snapshot)
        finally:
            release_builder.set()
            provider.stop()

    def test_fast_live_table_snapshot_keeps_push_alerts_for_same_round(self) -> None:
        state = _build_live_capture_state()
        base_snapshot = _build_minimal_live_table_snapshot((1, 0))
        base_snapshot = app_main.replace(
            base_snapshot,
            round_identity=app_main.build_live_round_identity(state),
            player_push_alert_percentages={
                int(Player.SHIMOCHA): {
                    "seat": int(Player.SHIMOCHA),
                    "percentage": 12.0,
                    "threshold_percent": 9.0,
                    "discard_index": 7,
                    "kind": "push",
                }
            },
        )
        state.tracker.add_discard(Player.SHIMOCHA, 2).round_discard_index = 1
        _append_live_round_discard(state, Player.SHIMOCHA, 4, 1)
        state.live_update_sequence = 2

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        self.assertEqual(fast_snapshot.refresh_token, (2, 0))
        self.assertEqual(len(fast_snapshot.discard_map[Player.SHIMOCHA]), 2)
        self.assertEqual(
            fast_snapshot.player_push_alert_percentages,
            base_snapshot.player_push_alert_percentages,
        )

    def test_fast_live_table_snapshot_remaps_previous_hand_danger_for_same_round(self) -> None:
        state = _build_live_capture_state()
        previous_danger = [
            {int(Player.KAMICHA): {"percentage": 11}},
            {int(Player.KAMICHA): {"percentage": 12}},
            {int(Player.KAMICHA): {"percentage": 22}},
            {int(Player.KAMICHA): {"percentage": 33}},
        ]
        previous_summary = {
            int(Player.KAMICHA): {
                "is_loading": False,
                "menzen_alert_score": 2,
            }
        }
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=app_main.build_live_round_identity(state),
            hand_tiles=[1, 1, 2, 3],
            hand_danger_percentages=previous_danger,
            opponent_suji_panel_summaries=previous_summary,
        )
        # The new hand reorders both copies of 1m, keeps 2m, and introduces a new 4m.
        state.live_hand_tiles_136 = [0, 4, 1, 12]
        state.live_last_draw_tile_136 = None
        state.live_update_sequence = 2

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        self.assertEqual(fast_snapshot.hand_tiles, [1, 2, 1, 4])
        self.assertEqual(
            fast_snapshot.hand_danger_percentages,
            [
                previous_danger[0],
                previous_danger[2],
                previous_danger[1],
                {},
            ],
        )
        self.assertEqual(
            fast_snapshot.opponent_suji_panel_summaries,
            previous_summary,
        )
        self.assertFalse(fast_snapshot.suji_analysis_is_current)

    def test_fast_live_table_snapshot_does_not_reuse_analysis_across_rounds(self) -> None:
        state = _build_live_capture_state()
        previous_danger = [
            {int(Player.KAMICHA): {"percentage": 17}},
        ]
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=("previous-round",),
            hand_tiles=[1],
            hand_danger_percentages=previous_danger,
            opponent_suji_panel_summaries={
                int(Player.KAMICHA): {
                    "is_loading": False,
                    "menzen_alert_score": 3,
                }
            },
        )
        state.live_hand_tiles_136 = [0]
        state.live_update_sequence = 2

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        self.assertEqual(fast_snapshot.hand_danger_percentages, [])
        normalized_summary = table_renderer._normalize_opponent_suji_panel_summaries(
            fast_snapshot.opponent_suji_panel_summaries
        )
        self.assertTrue(normalized_summary[int(Player.KAMICHA)]["is_loading"])
        self.assertFalse(fast_snapshot.suji_analysis_is_current)

    def test_build_fast_live_table_snapshot_updates_latest_raw_event_type(self) -> None:
        state = _build_live_capture_state()
        base_snapshot = _build_minimal_live_table_snapshot((1, 0))
        state.add_event(None, "initbylog")

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        self.assertEqual(fast_snapshot.latest_event_type, "initbylog")

    def test_fast_live_table_snapshot_uses_round_discards_when_cache_is_longer(self) -> None:
        state = _build_round_only_capture_state()
        base_discards = [
            _build_render_discard(tile_id=index + 1, round_discard_index=index)
            for index in range(6)
        ]
        live_discards = [
            _build_render_discard(
                tile_id=index + 1,
                round_discard_index=index,
                thinking_time_ms=900.0 + index,
            )
            for index in range(4)
        ]
        state.tracker.discards[Player.SHIMOCHA] = list(live_discards)
        _append_render_discards_to_round(state, Player.SHIMOCHA, live_discards)
        state.live_update_sequence = 2
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=app_main.build_live_round_identity(state),
            discard_map={
                player: (list(base_discards) if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        merged_discards = fast_snapshot.discard_map[Player.SHIMOCHA]
        self.assertEqual([discard.tile_id for discard in merged_discards], [1, 2, 3, 4])
        self.assertEqual(merged_discards[3].thinking_time_ms, 903.0)

    def test_build_live_table_snapshot_uses_round_discards_when_cache_is_longer(self) -> None:
        state = _build_round_only_capture_state()
        current_first = _build_render_discard(
            tile_id=1,
            round_discard_index=0,
            thinking_time_ms=444.0,
        )
        cached_second = _build_render_discard(tile_id=2, round_discard_index=1)
        state.tracker.discards[Player.SHIMOCHA] = [current_first]
        _append_render_discards_to_round(state, Player.SHIMOCHA, [current_first])
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=app_main.build_live_round_identity(state),
            discard_map={
                player: (
                    [_build_render_discard(tile_id=1, round_discard_index=0), cached_second]
                    if player is Player.SHIMOCHA
                    else []
                )
                for player in Player
            },
        )
        state.cached_live_table_snapshot = base_snapshot
        state.cached_live_table_snapshot_refresh_token = base_snapshot.refresh_token
        state.live_update_sequence = 2

        snapshot = app_main.build_live_table_snapshot(state)

        merged_discards = snapshot.discard_map[Player.SHIMOCHA]
        self.assertEqual([discard.tile_id for discard in merged_discards], [1])
        self.assertEqual(merged_discards[0].thinking_time_ms, 444.0)

    def test_build_live_table_snapshot_uses_round_discards_from_init_wrapper_to_reinit(self) -> None:
        state = _build_round_only_capture_state()
        assert state.current_round is not None
        state.current_round.snapshot_event_type = "reinit"
        state.current_round.snapshot_bootstrap_sequence = 13
        current_first = _build_render_discard(tile_id=1, round_discard_index=0)
        cached_second = _build_render_discard(tile_id=2, round_discard_index=1)
        state.tracker.discards[Player.SHIMOCHA] = [current_first]
        _append_render_discards_to_round(state, Player.SHIMOCHA, [current_first])
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=(("init", "test-round", 12), 12),
            discard_map={
                player: ([current_first, cached_second] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )
        state.cached_live_table_snapshot = base_snapshot
        state.cached_live_table_snapshot_refresh_token = base_snapshot.refresh_token
        state.live_update_sequence = 2

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(app_main.build_live_round_identity(state), ("river_epoch", 0, "test-round"))
        self.assertEqual(
            [discard.tile_id for discard in snapshot.discard_map[Player.SHIMOCHA]],
            [1],
        )

    def test_build_live_table_snapshot_uses_round_discards_when_cache_prefix_differs(self) -> None:
        state = _build_round_only_capture_state()
        current_first = _build_render_discard(tile_id=3, round_discard_index=0)
        state.tracker.discards[Player.SHIMOCHA] = [current_first]
        _append_render_discards_to_round(state, Player.SHIMOCHA, [current_first])
        cached_first = _build_render_discard(tile_id=1, round_discard_index=0)
        cached_second = _build_render_discard(tile_id=2, round_discard_index=1)
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=app_main.build_live_round_identity(state),
            discard_map={
                player: (
                    [cached_first, cached_second]
                    if player is Player.SHIMOCHA
                    else []
                )
                for player in Player
            },
        )
        state.cached_live_table_snapshot = base_snapshot
        state.cached_live_table_snapshot_refresh_token = base_snapshot.refresh_token
        state.live_update_sequence = 2

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(
            [discard.tile_id for discard in snapshot.discard_map[Player.SHIMOCHA]],
            [3],
        )

    def test_build_live_table_snapshot_does_not_restore_called_gap_from_cache(self) -> None:
        state = _build_round_only_capture_state()
        current_first = _build_render_discard(tile_id=1, round_discard_index=0)
        current_third = _build_render_discard(tile_id=3, round_discard_index=1)
        cached_called = _build_render_discard(tile_id=2, round_discard_index=1)
        cached_called.called = True
        state.tracker.discards[Player.SHIMOCHA] = [current_first, current_third]
        _append_render_discards_to_round(
            state,
            Player.SHIMOCHA,
            [current_first, current_third],
        )
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=app_main.build_live_round_identity(state),
            discard_map={
                player: (
                    [current_first, cached_called, current_third]
                    if player is Player.SHIMOCHA
                    else []
                )
                for player in Player
            },
        )
        state.cached_live_table_snapshot = base_snapshot
        state.cached_live_table_snapshot_refresh_token = base_snapshot.refresh_token
        state.live_update_sequence = 2

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(
            [discard.tile_id for discard in snapshot.discard_map[Player.SHIMOCHA]],
            [1, 3],
        )

    def test_build_live_table_snapshot_uses_round_discards_when_cache_is_missing(self) -> None:
        state = _build_round_only_capture_state()
        first_discard = _build_render_discard(tile_id=1, round_discard_index=0)
        second_discard = _build_render_discard(tile_id=2, round_discard_index=1)
        state.tracker.discards[Player.SHIMOCHA] = [first_discard, second_discard]
        _append_render_discards_to_round(
            state,
            Player.SHIMOCHA,
            [first_discard, second_discard],
        )
        first_snapshot = app_main.build_live_table_snapshot(state)
        self.assertEqual(
            [discard.tile_id for discard in first_snapshot.discard_map[Player.SHIMOCHA]],
            [1, 2],
        )

        state.cached_live_table_snapshot = None
        state.cached_live_table_snapshot_refresh_token = None
        with state.tracker.allow_discard_reset("test_broken_tracker"):
            state.tracker.discards[Player.SHIMOCHA] = [first_discard]
        state.live_update_sequence = 2

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(
            [discard.tile_id for discard in snapshot.discard_map[Player.SHIMOCHA]],
            [1, 2],
        )

    def test_build_live_table_snapshot_rebuilds_from_round_when_cache_is_stale(self) -> None:
        state = _build_round_only_capture_state()
        first_discard = _build_render_discard(tile_id=1, round_discard_index=0)
        second_discard = _build_render_discard(tile_id=2, round_discard_index=1)
        state.tracker.discards[Player.SHIMOCHA] = [first_discard, second_discard]
        _append_render_discards_to_round(
            state,
            Player.SHIMOCHA,
            [first_discard, second_discard],
        )
        first_snapshot = app_main.build_live_table_snapshot(state)
        state.cached_live_table_snapshot = app_main.replace(
            first_snapshot,
            discard_map={
                player: ([first_discard] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )
        state.mark_live_update()

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(
            [discard.tile_id for discard in snapshot.discard_map[Player.SHIMOCHA]],
            [1, 2],
        )

    def test_live_snapshot_with_stable_discard_map_restores_cached_short_snapshot(self) -> None:
        state = _build_round_only_capture_state()
        first_discard = _build_render_discard(tile_id=1, round_discard_index=0)
        second_discard = _build_render_discard(tile_id=2, round_discard_index=1)
        _append_render_discards_to_round(
            state,
            Player.SHIMOCHA,
            [first_discard, second_discard],
        )
        snapshot = app_main.build_live_table_snapshot(state)
        cached_short_snapshot = app_main.replace(
            snapshot,
            discard_map={
                player: ([first_discard] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )

        restored = app_main._live_snapshot_with_stable_discard_map(
            state,
            cached_short_snapshot,
        )

        self.assertEqual(
            [discard.tile_id for discard in restored.discard_map[Player.SHIMOCHA]],
            [1, 2],
        )

    def test_live_snapshot_with_stable_discard_map_restores_called_metadata(self) -> None:
        state = _build_round_only_capture_state()
        called_discard = _build_render_discard(tile_id=2, round_discard_index=0)
        called_discard.called = True
        _append_render_discards_to_round(state, Player.SHIMOCHA, [called_discard])
        snapshot = app_main.build_live_table_snapshot(state)
        uncalled_discard = _build_render_discard(tile_id=2, round_discard_index=0)
        cached_uncalled_snapshot = app_main.replace(
            snapshot,
            discard_map={
                player: ([uncalled_discard] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )

        restored = app_main._live_snapshot_with_stable_discard_map(
            state,
            cached_uncalled_snapshot,
        )

        self.assertTrue(restored.discard_map[Player.SHIMOCHA][0].called)

    def test_live_snapshot_with_stable_discard_map_restores_when_state_lock_busy(self) -> None:
        state = _build_round_only_capture_state()
        first_discard = _build_render_discard(tile_id=1, round_discard_index=0)
        second_discard = _build_render_discard(tile_id=2, round_discard_index=1)
        _append_render_discards_to_round(
            state,
            Player.SHIMOCHA,
            [first_discard, second_discard],
        )
        snapshot = app_main.build_live_table_snapshot(state)
        cached_short_snapshot = app_main.replace(
            snapshot,
            discard_map={
                player: ([first_discard] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )
        state.state_lock = _BusyStateLock()

        restored = app_main._live_snapshot_with_stable_discard_map(
            state,
            cached_short_snapshot,
        )

        self.assertEqual(
            [discard.tile_id for discard in restored.discard_map[Player.SHIMOCHA]],
            [1, 2],
        )

    def test_publish_live_stable_discard_map_returns_previous_when_state_lock_busy(self) -> None:
        state = _build_round_only_capture_state()
        first_discard = _build_render_discard(tile_id=1, round_discard_index=0)
        second_discard = _build_render_discard(tile_id=2, round_discard_index=1)
        round_identity = app_main.build_live_round_identity(state)
        long_map = {
            player: (
                [first_discard, second_discard]
                if player is Player.SHIMOCHA
                else []
            )
            for player in Player
        }
        app_main._publish_live_stable_discard_map(state, round_identity, long_map)
        state.state_lock = _BusyStateLock()

        returned_map = app_main._publish_live_stable_discard_map(
            state,
            round_identity,
            {
                player: ([first_discard] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )

        self.assertEqual(
            [discard.tile_id for discard in returned_map[Player.SHIMOCHA]],
            [1, 2],
        )

    def test_build_live_table_snapshot_repairs_cached_short_snapshot_when_state_lock_busy(self) -> None:
        state = _build_round_only_capture_state()
        first_discard = _build_render_discard(tile_id=1, round_discard_index=0)
        second_discard = _build_render_discard(tile_id=2, round_discard_index=1)
        round_identity = app_main.build_live_round_identity(state)
        state.live_stable_discard_round_identity = round_identity
        state.live_stable_discard_map = {
            player: (
                [first_discard, second_discard]
                if player is Player.SHIMOCHA
                else []
            )
            for player in Player
        }
        state.cached_live_table_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=round_identity,
            discard_map={
                player: ([first_discard] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )
        state.state_lock = _BusyStateLock()

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(
            [discard.tile_id for discard in snapshot.discard_map[Player.SHIMOCHA]],
            [1, 2],
        )

    def test_publish_live_stable_discard_map_does_not_shorten_same_round(self) -> None:
        state = _build_round_only_capture_state()
        first_discard = _build_render_discard(tile_id=1, round_discard_index=0)
        second_discard = _build_render_discard(tile_id=2, round_discard_index=1)
        round_identity = app_main.build_live_round_identity(state)
        long_map = {
            player: (
                [first_discard, second_discard]
                if player is Player.SHIMOCHA
                else []
            )
            for player in Player
        }
        app_main._publish_live_stable_discard_map(state, round_identity, long_map)

        returned_map = app_main._publish_live_stable_discard_map(
            state,
            round_identity,
            {
                player: ([first_discard] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )

        self.assertEqual(
            [discard.tile_id for discard in returned_map[Player.SHIMOCHA]],
            [1, 2],
        )
        self.assertEqual(
            [
                discard.tile_id
                for discard in state.live_stable_discard_map[Player.SHIMOCHA]
            ],
            [1, 2],
        )

    def test_fast_live_table_snapshot_uses_round_discards_across_same_logical_reinit(self) -> None:
        state = _build_round_only_capture_state()
        assert state.current_round is not None
        state.current_round.snapshot_bootstrap_sequence = 2
        live_first = _build_render_discard(tile_id=1, round_discard_index=0)
        cached_second = _build_render_discard(tile_id=2, round_discard_index=1)
        state.tracker.discards[Player.SHIMOCHA] = [live_first]
        _append_render_discards_to_round(state, Player.SHIMOCHA, [live_first])
        state.live_update_sequence = 2
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=("test-round", 1),
            discard_map={
                player: ([live_first, cached_second] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        self.assertEqual(
            [discard.tile_id for discard in fast_snapshot.discard_map[Player.SHIMOCHA]],
            [1],
        )

    def test_fast_live_table_snapshot_does_not_restore_called_gap_from_cache(self) -> None:
        state = _build_round_only_capture_state()
        current_first = _build_render_discard(tile_id=1, round_discard_index=0)
        current_third = _build_render_discard(tile_id=3, round_discard_index=1)
        cached_called = _build_render_discard(tile_id=2, round_discard_index=1)
        cached_called.called = True
        state.tracker.discards[Player.SHIMOCHA] = [current_first, current_third]
        _append_render_discards_to_round(
            state,
            Player.SHIMOCHA,
            [current_first, current_third],
        )
        state.live_update_sequence = 2
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=app_main.build_live_round_identity(state),
            discard_map={
                player: (
                    [current_first, cached_called, current_third]
                    if player is Player.SHIMOCHA
                    else []
                )
                for player in Player
            },
        )

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        self.assertEqual(
            [discard.tile_id for discard in fast_snapshot.discard_map[Player.SHIMOCHA]],
            [1, 3],
        )

    def test_fast_live_table_snapshot_uses_round_discards_over_broken_base(self) -> None:
        state = _build_round_only_capture_state()
        first_discard = _build_render_discard(tile_id=1, round_discard_index=0)
        second_discard = _build_render_discard(tile_id=2, round_discard_index=1)
        state.tracker.discards[Player.SHIMOCHA] = [first_discard, second_discard]
        _append_render_discards_to_round(
            state,
            Player.SHIMOCHA,
            [first_discard, second_discard],
        )
        first_snapshot = app_main.build_live_table_snapshot(state)

        with state.tracker.allow_discard_reset("test_broken_tracker"):
            state.tracker.discards[Player.SHIMOCHA] = [first_discard]
        state.live_update_sequence = 2
        broken_base = app_main.replace(
            first_snapshot,
            discard_map={
                player: ([first_discard] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            broken_base,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        self.assertEqual(
            [discard.tile_id for discard in fast_snapshot.discard_map[Player.SHIMOCHA]],
            [1, 2],
        )

    def test_fast_live_table_snapshot_uses_round_discards_from_init_wrapper_to_reinit(self) -> None:
        state = _build_round_only_capture_state()
        assert state.current_round is not None
        state.current_round.snapshot_event_type = "reinit"
        state.current_round.snapshot_bootstrap_sequence = 13
        live_first = _build_render_discard(tile_id=1, round_discard_index=0)
        cached_second = _build_render_discard(tile_id=2, round_discard_index=1)
        state.tracker.discards[Player.SHIMOCHA] = [live_first]
        _append_render_discards_to_round(state, Player.SHIMOCHA, [live_first])
        state.live_update_sequence = 2
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=(("init", "test-round", 12), 12),
            discard_map={
                player: ([live_first, cached_second] if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        self.assertEqual(app_main.build_live_round_identity(state), ("river_epoch", 0, "test-round"))
        self.assertEqual(
            [discard.tile_id for discard in fast_snapshot.discard_map[Player.SHIMOCHA]],
            [1],
        )

    def test_live_discard_history_preserves_across_init_wrapper_same_round(self) -> None:
        self.assertTrue(
            app_main._same_live_discard_history_round(
                ("test-round", 12),
                (("init", "test-round", 13), 13),
            )
        )
        self.assertTrue(
            app_main._same_live_discard_history_round(
                (("init", "test-round", 12), 12),
                (("init", "test-round", 13), 13),
            )
        )
        self.assertTrue(
            app_main._same_live_discard_history_round(
                (("init", "test-round", 12), 12),
                ("test-round", 13),
            )
        )

    def test_live_discard_history_does_not_preserve_across_init_different_round(self) -> None:
        self.assertFalse(
            app_main._same_live_discard_history_round(
                (("init", "test-round", 12), 12),
                (("init", "next-round", 13), 13),
            )
        )

    def test_live_discard_history_preserves_across_init_wgc_initbylog_wrapper(self) -> None:
        for event_type in ("init", "wgc", "initbylog"):
            with self.subTest(event_type=event_type):
                self.assertTrue(
                    app_main._same_live_discard_history_round(
                        ("test-round", 12),
                        ((event_type, "test-round", 13), 13),
                    )
                )
                self.assertTrue(
                    app_main._same_live_discard_history_round(
                        ((event_type, "test-round", 13), 13),
                        ("test-round", 14),
                    )
                )

    def test_fast_live_table_snapshot_uses_live_tail_for_recent_discard_metadata(self) -> None:
        state = _build_round_only_capture_state()
        base_discards = [
            _build_render_discard(
                tile_id=index + 1,
                round_discard_index=index,
                thinking_time_ms=100.0 + index,
            )
            for index in range(5)
        ]
        live_discards = [
            _build_render_discard(
                tile_id=index + 1,
                round_discard_index=index,
                draw_type=DrawType.TSUMOGIRI if index == 4 else DrawType.TEDASHI,
                thinking_time_ms=800.0 + index,
                lagged=LAG_FLAG_UNCONFIRMED if index == 3 else 0,
            )
            for index in range(6)
        ]
        state.tracker.discards[Player.SHIMOCHA] = list(live_discards)
        _append_render_discards_to_round(state, Player.SHIMOCHA, live_discards)
        state.live_update_sequence = 2
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=app_main.build_live_round_identity(state),
            discard_map={
                player: (list(base_discards) if player is Player.SHIMOCHA else [])
                for player in Player
            },
        )

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        merged_discards = fast_snapshot.discard_map[Player.SHIMOCHA]
        self.assertEqual([discard.tile_id for discard in merged_discards], [1, 2, 3, 4, 5, 6])
        self.assertEqual(merged_discards[2].thinking_time_ms, 802.0)
        self.assertEqual(merged_discards[3].thinking_time_ms, 803.0)
        self.assertEqual(merged_discards[3].lagged, LAG_FLAG_UNCONFIRMED)
        self.assertEqual(merged_discards[4].draw_type, DrawType.TSUMOGIRI)
        self.assertEqual(merged_discards[5].thinking_time_ms, 805.0)

    def test_fast_live_table_snapshot_uses_round_discards_when_tracker_is_short(self) -> None:
        state = _build_round_only_capture_state()
        _append_live_round_discard(state, Player.SHIMOCHA, 52, 0)
        _append_live_round_discard(
            state,
            Player.SHIMOCHA,
            56,
            1,
            tsumogiri=True,
            thinking_time_ms=777.0,
            lagged=LAG_FLAG_UNCONFIRMED,
        )
        first_tile = app_main.tile136_to_tile37(52)
        self.assertIsNotNone(first_tile)
        state.tracker.add_discard(Player.SHIMOCHA, first_tile).round_discard_index = 0
        state.live_update_sequence = 2
        base_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((1, 0)),
            round_identity=app_main.build_live_round_identity(state),
        )

        fast_snapshot = app_main.build_fast_live_table_snapshot(
            state,
            base_snapshot,
            (2, 0),
        )

        self.assertIsNotNone(fast_snapshot)
        assert fast_snapshot is not None
        repaired_discards = fast_snapshot.discard_map[Player.SHIMOCHA]
        self.assertEqual(
            [discard.tile_id for discard in repaired_discards],
            [app_main.tile136_to_tile37(52), app_main.tile136_to_tile37(56)],
        )
        self.assertEqual(repaired_discards[1].draw_type, DrawType.TSUMOGIRI)
        self.assertEqual(repaired_discards[1].thinking_time_ms, 777.0)
        self.assertEqual(repaired_discards[1].lagged, LAG_FLAG_UNCONFIRMED)

    def test_build_live_table_snapshot_uses_round_discards_when_tracker_is_short(self) -> None:
        state = _build_round_only_capture_state()
        _append_live_round_discard(state, Player.SHIMOCHA, 52, 0)
        _append_live_round_discard(
            state,
            Player.SHIMOCHA,
            56,
            1,
            tsumogiri=True,
            thinking_time_ms=888.0,
        )
        first_tile = app_main.tile136_to_tile37(52)
        self.assertIsNotNone(first_tile)
        state.tracker.add_discard(Player.SHIMOCHA, first_tile).round_discard_index = 0
        previous_live_update_sequence = int(state.live_update_sequence)

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(len(state.tracker.discards[Player.SHIMOCHA]), 1)
        self.assertEqual(state.live_update_sequence, previous_live_update_sequence)
        self.assertFalse(
            any(
                diagnostic.get("code") == "live_tracker_repaired_from_round"
                for diagnostic in state.diagnostics
            )
        )
        repaired_discards = snapshot.discard_map[Player.SHIMOCHA]
        self.assertEqual(
            [discard.tile_id for discard in repaired_discards],
            [app_main.tile136_to_tile37(52), app_main.tile136_to_tile37(56)],
        )
        self.assertEqual(repaired_discards[1].draw_type, DrawType.TSUMOGIRI)
        self.assertEqual(repaired_discards[1].thinking_time_ms, 888.0)

    def test_build_live_table_snapshot_ignores_cached_short_tracker_when_round_changed(self) -> None:
        state = _build_round_only_capture_state()
        _append_live_round_discard(state, Player.SHIMOCHA, 52, 0)
        _append_live_round_discard(state, Player.SHIMOCHA, 56, 1)
        first_tile = app_main.tile136_to_tile37(52)
        self.assertIsNotNone(first_tile)
        state.tracker.add_discard(Player.SHIMOCHA, first_tile).round_discard_index = 0
        cached_snapshot = app_main.replace(
            _build_minimal_live_table_snapshot((state.live_update_sequence, 0)),
            discard_map={
                player: (
                    [_build_render_discard(first_tile, 0)]
                    if player is Player.SHIMOCHA
                    else []
                )
                for player in Player
            },
        )
        state.cached_live_table_snapshot = cached_snapshot
        state.cached_live_table_snapshot_refresh_token = cached_snapshot.refresh_token
        state.mark_live_update()

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertIsNot(snapshot, cached_snapshot)
        self.assertEqual(len(snapshot.discard_map[Player.SHIMOCHA]), 2)
        self.assertEqual(len(state.tracker.discards[Player.SHIMOCHA]), 1)

    def test_live_discard_red_tint_cache_reuses_equivalent_round_signature(self) -> None:
        first_state = _build_live_capture_state()
        second_state = _build_live_capture_state()

        with patch(
            "app.main.build_discard_red_tint_indices_by_seat",
            wraps=app_main.build_discard_red_tint_indices_by_seat,
        ) as tint_builder:
            first = app_main.build_live_discard_red_tint_indices_by_seat(first_state)
            second = app_main.build_live_discard_red_tint_indices_by_seat(second_state)

        self.assertEqual(first, second)
        if app_main.LIVE_DISCARD_RED_TINT_ENABLED:
            self.assertEqual(tint_builder.call_count, 1)
        else:
            self.assertEqual(first, {})
            self.assertEqual(tint_builder.call_count, 0)

    def test_build_live_table_snapshot_builds_shared_suji_profiles_once_per_refresh(self) -> None:
        state = _build_live_capture_state()

        with patch(
            "app.main.build_all_opponent_suji_danger_profiles",
            wraps=app_main.build_all_opponent_suji_danger_profiles,
        ) as profile_builder:
            app_main.build_live_table_snapshot(state)
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if _live_suji_bundle_completed(state):
                    break
                time.sleep(0.01)

        self.assertEqual(profile_builder.call_count, 1)

    def test_build_live_table_snapshot_uses_async_suji_bundle_loading_placeholder(self) -> None:
        state = _build_live_capture_state()

        first_snapshot = app_main.build_live_table_snapshot(state)
        normalized_first_summary = table_renderer._normalize_opponent_suji_panel_summaries(
            first_snapshot.opponent_suji_panel_summaries
        )
        self.assertTrue(normalized_first_summary[int(Player.KAMICHA)]["is_loading"])

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if _live_suji_bundle_completed(state):
                break
            time.sleep(0.01)

        self.assertTrue(_live_suji_bundle_completed(state))
        second_snapshot = app_main.build_live_table_snapshot(state)
        normalized_second_summary = table_renderer._normalize_opponent_suji_panel_summaries(
            second_snapshot.opponent_suji_panel_summaries
        )
        self.assertFalse(normalized_second_summary[int(Player.KAMICHA)]["is_loading"])

    def test_build_live_round_info_panel_includes_current_seat_winds(self) -> None:
        state = _build_live_capture_state()
        state.current_round.oya_rel = int(Player.SHIMOCHA)

        round_info_panel = app_main.build_live_round_info_panel(state)

        self.assertEqual(
            round_info_panel.seat_wind_labels_by_seat,
            {
                int(Player.JICHA): "北",
                int(Player.SHIMOCHA): "東",
                int(Player.TOIMEN): "南",
                int(Player.KAMICHA): "西",
            },
        )

    def test_build_live_round_info_panel_includes_reinit_bootstrap_count(self) -> None:
        state = _build_live_capture_state()
        state.current_round.snapshot_bootstrap_sequence = 3
        state.current_round.raw_reinit_attrs = {"tag": "REINIT"}

        round_info_panel = app_main.build_live_round_info_panel(state)
        table_snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(round_info_panel.bootstrap_text, "REINIT #3")
        self.assertEqual(table_snapshot.round_info_panel.bootstrap_text, "REINIT #3")

    def test_live_suji_bundle_tolerates_missing_optional_discard_numbers(self) -> None:
        state = _build_live_capture_state()
        live_discard = state.current_round.discards[int(Player.SHIMOCHA)][0]
        live_discard.tile_37 = None
        live_discard.event_index = None
        live_discard.round_discard_index = None

        visible_summary = app_main.build_live_visible_tile_summary(state)
        analysis_snapshot = app_main._build_live_analysis_snapshot(state, visible_summary)
        bundle = app_main._build_live_suji_computation_bundle(
            analysis_snapshot,
            source_refresh_token=1,
            round_identity=("test-round",),
            input_signature=app_main._build_live_suji_input_signature(state, visible_summary),
        )

        self.assertEqual(bundle.source_refresh_token, 1)
        self.assertIn(int(Player.KAMICHA), bundle.opponent_suji_panel_summaries)

    def test_request_live_suji_bundle_reuses_running_worker_and_sets_wake_event(self) -> None:
        state = _build_live_capture_state()
        visible_summary = app_main.build_live_visible_tile_summary(state)
        analysis_snapshot = app_main._build_live_analysis_snapshot(state, visible_summary)
        async_state = app_main._get_live_suji_async_state(state)
        async_state.worker_running = True
        async_state.wake_event.clear()

        with patch("app.main.threading.Thread") as thread_ctor:
            current_bundle, fallback_bundle = app_main._request_live_suji_bundle(
                state,
                analysis_snapshot,
                source_refresh_token=5,
                round_identity="test-round",
                input_signature=app_main._build_live_suji_input_signature(state, visible_summary),
            )

        self.assertIsNone(current_bundle)
        self.assertIsNone(fallback_bundle)
        self.assertIsNotNone(async_state.pending_job)
        self.assertEqual(async_state.pending_job.source_refresh_token, 5)
        self.assertTrue(async_state.wake_event.is_set())
        thread_ctor.assert_not_called()

    def test_request_live_suji_bundle_reuses_previous_same_round_bundle_as_fallback(self) -> None:
        state = _build_live_capture_state()
        visible_summary = app_main.build_live_visible_tile_summary(state)
        analysis_snapshot = app_main._build_live_analysis_snapshot(state, visible_summary)
        previous_bundle = app_main.LiveSujiComputationBundle(
            source_refresh_token=1,
            round_identity="test-round",
            input_signature=("previous-input",),
            hand_tiles=(1,),
            hand_danger_percentages=[
                {int(Player.KAMICHA): {"percentage": 17}},
            ],
            opponent_suji_panel_summaries={
                int(Player.KAMICHA): {
                    "is_loading": False,
                    "menzen_alert_score": 2,
                }
            },
            player_push_alert_percentages={},
            player_alert_indicators_by_seat={},
        )
        async_state = app_main._get_live_suji_async_state(state)
        async_state.worker_running = True
        async_state.completed_bundle = previous_bundle
        async_state.completed_source_refresh_token = previous_bundle.source_refresh_token
        async_state.completed_round_identity = previous_bundle.round_identity

        with patch("app.main.threading.Thread") as thread_ctor:
            current_bundle, fallback_bundle = app_main._request_live_suji_bundle(
                state,
                analysis_snapshot,
                source_refresh_token=2,
                round_identity="test-round",
                input_signature=("changed-input",),
            )

        self.assertIsNone(current_bundle)
        self.assertIs(fallback_bundle, previous_bundle)
        self.assertIsNotNone(async_state.pending_job)
        self.assertEqual(async_state.pending_job.input_signature, ("changed-input",))
        self.assertTrue(async_state.wake_event.is_set())
        thread_ctor.assert_not_called()

    def test_request_live_suji_bundle_does_not_reuse_previous_bundle_across_rounds(self) -> None:
        state = _build_live_capture_state()
        visible_summary = app_main.build_live_visible_tile_summary(state)
        analysis_snapshot = app_main._build_live_analysis_snapshot(state, visible_summary)
        previous_bundle = app_main.LiveSujiComputationBundle(
            source_refresh_token=1,
            round_identity="previous-round",
            input_signature=("previous-input",),
            hand_tiles=(1,),
            hand_danger_percentages=[
                {int(Player.KAMICHA): {"percentage": 17}},
            ],
            opponent_suji_panel_summaries={
                int(Player.KAMICHA): {
                    "is_loading": False,
                    "menzen_alert_score": 2,
                }
            },
            player_push_alert_percentages={},
            player_alert_indicators_by_seat={},
        )
        async_state = app_main._get_live_suji_async_state(state)
        async_state.worker_running = True
        async_state.completed_bundle = previous_bundle
        async_state.completed_source_refresh_token = previous_bundle.source_refresh_token
        async_state.completed_round_identity = previous_bundle.round_identity

        with patch("app.main.threading.Thread") as thread_ctor:
            current_bundle, fallback_bundle = app_main._request_live_suji_bundle(
                state,
                analysis_snapshot,
                source_refresh_token=2,
                round_identity="next-round",
                input_signature=("changed-input",),
            )

        self.assertIsNone(current_bundle)
        self.assertIsNone(fallback_bundle)
        self.assertIsNotNone(async_state.pending_job)
        self.assertEqual(async_state.pending_job.round_identity, "next-round")
        thread_ctor.assert_not_called()

    def test_build_live_table_snapshot_uses_async_red_tint_bundle_after_worker_completes(self) -> None:
        state = _build_live_capture_state()

        with patch(
            "app.main.build_live_discard_red_tint_indices_by_seat",
            return_value={int(Player.SHIMOCHA): (0,)},
        ) as tint_builder:
            first_snapshot = app_main.build_live_table_snapshot(state)
            self.assertEqual(first_snapshot.discard_red_tint_indices_by_seat, {})

            deadline = time.time() + 2.0
            while time.time() < deadline:
                red_tint_async_state = getattr(state, "live_red_tint_async_state", None)
                if int(getattr(red_tint_async_state, "update_sequence", 0)) > 0:
                    break
                time.sleep(0.01)

            self.assertGreater(
                int(getattr(getattr(state, "live_red_tint_async_state", None), "update_sequence", 0)),
                0,
            )
            second_snapshot = app_main.build_live_table_snapshot(state)

        self.assertGreaterEqual(tint_builder.call_count, 1)
        self.assertEqual(
            second_snapshot.discard_red_tint_indices_by_seat,
            {int(Player.SHIMOCHA): (0,)},
        )

    def test_build_live_table_snapshot_precomputes_render_public_state_off_ui(self) -> None:
        state = _build_live_capture_state()
        table_scores = {int(Player.SHIMOCHA): (2.0,) + (0.0,) * 8}
        same_jun_markers = {int(Player.SHIMOCHA): frozenset({0})}

        with patch(
            "app.main.table_view.TABLE_SITUATION_ENABLED",
            True,
        ), patch(
            "app.main.table_view.AWASEUCHI_MARKERS_ENABLED",
            True,
        ), patch(
            "app.main.table_view._build_table_situation_auto_scores_by_seat",
            return_value=table_scores,
        ) as table_situation_builder, patch(
            "app.main.table_view._same_jun_match_discard_indices_by_seat",
            return_value=same_jun_markers,
        ) as same_jun_builder:
            snapshot = app_main.build_live_table_snapshot(state)

        table_situation_builder.assert_called_once()
        same_jun_builder.assert_called_once()
        self.assertEqual(snapshot.table_situation_auto_scores_by_seat, table_scores)
        self.assertEqual(snapshot.same_jun_marker_indices_by_seat, same_jun_markers)

    def test_request_live_red_tint_bundle_reuses_running_worker_and_sets_wake_event(self) -> None:
        state = _build_live_capture_state()
        visible_summary = app_main.build_live_visible_tile_summary(state)
        analysis_snapshot = app_main._build_live_analysis_snapshot(state, visible_summary)
        async_state = app_main._get_live_red_tint_async_state(state)
        async_state.worker_running = True
        async_state.wake_event.clear()

        with patch("app.main.threading.Thread") as thread_ctor:
            current_indices, fallback_indices = app_main._request_live_red_tint_bundle(
                state,
                analysis_snapshot,
                source_refresh_token=7,
                round_identity="test-round",
            )

        self.assertIsNone(current_indices)
        self.assertIsNone(fallback_indices)
        self.assertIsNotNone(async_state.pending_job)
        self.assertEqual(async_state.pending_job.source_refresh_token, 7)
        self.assertTrue(async_state.wake_event.is_set())
        thread_ctor.assert_not_called()

    def test_build_live_table_snapshot_carries_precomputed_player_alert_rows(self) -> None:
        state = _build_live_capture_state()

        with patch(
            "app.main.table_view.build_player_panel_alert_indicators_by_seat",
            wraps=table_renderer.build_player_panel_alert_indicators_by_seat,
        ) as indicator_builder:
            app_main.build_live_table_snapshot(state)
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if _live_suji_bundle_completed(state):
                    break
                time.sleep(0.01)
            snapshot = app_main.build_live_table_snapshot(state)

        self.assertGreaterEqual(indicator_builder.call_count, 1)
        self.assertEqual(
            snapshot.player_alert_indicators_by_seat,
            table_renderer.build_player_panel_alert_indicators_by_seat(
                table_renderer._normalize_opponent_suji_panel_summaries(
                    snapshot.opponent_suji_panel_summaries
                ),
                table_renderer._normalize_player_push_alert_percentages(
                    snapshot.player_push_alert_percentages
                ),
            ),
        )

    def test_build_live_table_snapshot_carries_awaseuchi_dora_events(self) -> None:
        state = _build_live_capture_state()
        self.assertIsNotNone(state.current_round)
        state.current_round.events.append(
            LiveEvent(
                timestamp=1.0,
                event_type="dora",
                raw_tag='{"tag":"DORA","hai":"3"}',
                attrs={"hai": "3"},
            )
        )
        state.current_round.events.append(
            LiveEvent(
                timestamp=2.0,
                event_type="discard",
                raw_tag="D0",
                tile_136=0,
            )
        )

        snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(
            [event.event_type for event in snapshot.round_events],
            ["dora"],
        )

    def test_build_live_table_snapshot_reuses_previous_bundle_while_next_refresh_computes(self) -> None:
        state = _build_live_capture_state()

        app_main.build_live_table_snapshot(state)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if _live_suji_bundle_completed(state):
                break
            time.sleep(0.01)
        self.assertTrue(_live_suji_bundle_completed(state))

        state.mark_live_update()
        next_snapshot = app_main.build_live_table_snapshot(state)
        normalized_summary = table_renderer._normalize_opponent_suji_panel_summaries(
            next_snapshot.opponent_suji_panel_summaries
        )
        self.assertFalse(normalized_summary[int(Player.KAMICHA)]["is_loading"])

    def test_build_live_table_snapshot_remaps_fallback_danger_to_current_hand(self) -> None:
        state = _build_live_capture_state()
        state.live_hand_tiles_136 = [0, 4, 1, 12]
        state.live_last_draw_tile_136 = None
        state.live_update_sequence = 2
        round_identity = app_main.build_live_round_identity(state)
        previous_danger = [
            {int(Player.KAMICHA): {"percentage": 11}},
            {int(Player.KAMICHA): {"percentage": 12}},
            {int(Player.KAMICHA): {"percentage": 22}},
            {int(Player.KAMICHA): {"percentage": 33}},
        ]
        previous_summary = {
            int(Player.KAMICHA): {
                "is_loading": False,
                "menzen_alert_score": 2,
            }
        }
        previous_bundle = app_main.LiveSujiComputationBundle(
            source_refresh_token=1,
            round_identity=round_identity,
            input_signature=("previous-input",),
            hand_tiles=(1, 1, 2, 3),
            hand_danger_percentages=previous_danger,
            opponent_suji_panel_summaries=previous_summary,
            player_push_alert_percentages={},
            player_alert_indicators_by_seat={},
        )
        async_state = app_main._get_live_suji_async_state(state)
        async_state.worker_running = True
        async_state.completed_bundle = previous_bundle
        async_state.completed_source_refresh_token = previous_bundle.source_refresh_token
        async_state.completed_round_identity = round_identity

        with patch(
            "app.main._request_live_red_tint_bundle",
            return_value=(None, None),
        ):
            snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(snapshot.hand_tiles, [1, 2, 1, 4])
        self.assertEqual(
            snapshot.hand_danger_percentages,
            [
                previous_danger[0],
                previous_danger[2],
                previous_danger[1],
                {},
            ],
        )
        self.assertEqual(
            snapshot.opponent_suji_panel_summaries,
            previous_summary,
        )
        self.assertFalse(snapshot.suji_analysis_is_current)

    def test_build_live_table_snapshot_keeps_previous_bundle_after_lag_metadata_changes(self) -> None:
        state = _build_live_capture_state()
        state.live_hand_tiles_136 = [4]

        app_main.build_live_table_snapshot(state)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if _live_suji_bundle_completed(state):
                break
            time.sleep(0.01)
        self.assertTrue(_live_suji_bundle_completed(state))
        previous_snapshot = app_main.build_live_table_snapshot(state)
        previous_danger = previous_snapshot.hand_danger_percentages
        previous_summary = previous_snapshot.opponent_suji_panel_summaries
        self.assertTrue(previous_danger)
        self.assertTrue(previous_snapshot.suji_analysis_is_current)

        worker_started = app_main.threading.Event()
        release_worker = app_main.threading.Event()
        original_builder = app_main._build_live_suji_computation_bundle

        def blocked_builder(*args: object, **kwargs: object) -> app_main.LiveSujiComputationBundle:
            worker_started.set()
            release_worker.wait(timeout=2.0)
            return original_builder(*args, **kwargs)

        try:
            with patch(
                "app.main._build_live_suji_computation_bundle",
                side_effect=blocked_builder,
            ):
                self.assertIsNotNone(state.current_round)
                assert state.current_round is not None
                state.current_round.discards[int(Player.SHIMOCHA)][0].lagged = LAG_FLAG_UNCONFIRMED
                state.mark_live_update()
                next_snapshot = app_main.build_live_table_snapshot(state)
                self.assertTrue(worker_started.wait(timeout=1.0))

                self.assertEqual(
                    next_snapshot.hand_danger_percentages,
                    previous_danger,
                )
                self.assertEqual(
                    next_snapshot.opponent_suji_panel_summaries,
                    previous_summary,
                )
                self.assertFalse(next_snapshot.suji_analysis_is_current)
        finally:
            release_worker.set()

    def test_build_live_table_snapshot_returns_cached_snapshot_while_state_lock_is_busy(self) -> None:
        state = _build_live_capture_state()
        app_main.build_live_table_snapshot(state)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            latest_snapshot = app_main.build_live_table_snapshot(state)
            if _live_suji_bundle_completed(state):
                break
            time.sleep(0.01)
        cached_snapshot = app_main.build_live_table_snapshot(state)

        acquired = state.state_lock.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            busy_snapshot = app_main.build_live_table_snapshot(state)
            busy_refresh_token = app_main.build_live_refresh_token(state)
        finally:
            if acquired:
                state.state_lock.release()

        self.assertEqual(busy_snapshot.refresh_token, cached_snapshot.refresh_token)
        self.assertEqual(busy_refresh_token, cached_snapshot.refresh_token)

    def test_snapshot_live_capture_state_returns_independent_lightweight_round_copy(self) -> None:
        state = _build_live_capture_state()
        self.assertIsNotNone(state.current_round)
        state.current_round.events.append(
            LiveEvent(
                timestamp=1.0,
                event_type="dora",
                raw_tag='{"tag":"DORA","hai":"3"}',
                attrs={"hai": "3"},
            )
        )
        state.current_round.events.append(
            LiveEvent(
                timestamp=2.0,
                event_type="discard",
                raw_tag="D0",
                tile_136=0,
            )
        )

        snapshot_state, _player_names_by_seat, _refresh_token = app_main._snapshot_live_capture_state(state)

        self.assertIsNotNone(snapshot_state.current_round)
        self.assertEqual(
            [event.event_type for event in snapshot_state.current_round.events],
            ["dora"],
        )
        state.current_round.scores[0] = 12345
        state.current_round.events[0].attrs["hai"] = "9"

        self.assertEqual(snapshot_state.current_round.scores[0], 25000)
        self.assertEqual(snapshot_state.current_round.events[0].attrs["hai"], "3")


class SameJunMatchCacheTest(unittest.TestCase):
    def test_same_jun_cache_ignores_refresh_token_when_public_state_is_same(self) -> None:
        canvas = type("CanvasStub", (), {})()
        canvas.current_round_identity = "test-round"
        canvas.current_refresh_token = ("capture", 1)
        canvas.same_jun_match_cache_key = None
        canvas.same_jun_match_cache_value = {}

        discard = Discard(tile_id=1, draw_type=DrawType.TEDASHI)
        discard.round_discard_index = 0
        discard_map = {
            Player.JICHA: [discard],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }

        with patch(
            "ui.table_renderer._same_jun_match_discard_indices_by_seat",
            wraps=table_renderer._same_jun_match_discard_indices_by_seat,
        ) as same_jun_builder:
            first = table_renderer._same_jun_match_discard_indices_by_seat_cached(
                canvas,
                discard_map,
            )
            canvas.current_refresh_token = ("capture", 2)
            second = table_renderer._same_jun_match_discard_indices_by_seat_cached(
                canvas,
                discard_map,
            )

        self.assertEqual(first, second)
        self.assertEqual(same_jun_builder.call_count, 1)

    def test_same_jun_marker_state_extends_public_event_stream_without_full_rebuild(self) -> None:
        canvas = type("CanvasStub", (), {})()
        canvas.current_round_identity = "test-round"
        canvas.same_jun_public_event_source_state = None
        canvas.same_jun_match_candidate_cache_key = None
        canvas.same_jun_match_candidate_cache_value = {}
        canvas.same_jun_match_candidate_event_stream = ()
        canvas.same_jun_match_candidate_recent_public_events = ()
        canvas.same_jun_match_confirmed_cache_key = None
        canvas.same_jun_match_confirmed_cache_value = {}
        canvas.same_jun_match_async_in_flight = False
        canvas.same_jun_match_async_pending_key = None

        first_discard = Discard(tile_id=1, draw_type=DrawType.TEDASHI)
        first_discard.round_discard_index = 0
        first_discard.event_index = 0
        second_discard = Discard(tile_id=2, draw_type=DrawType.TEDASHI)
        second_discard.round_discard_index = 1
        second_discard.event_index = 1
        first_map = {
            Player.JICHA: [first_discard],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }
        second_map = {
            Player.JICHA: [first_discard, second_discard],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }

        with patch(
            "ui.table_renderer._same_jun_public_event_stream",
            wraps=table_renderer._same_jun_public_event_stream,
        ) as stream_builder, patch(
            "ui.table_renderer._queue_same_jun_confirmation",
        ):
            table_renderer._same_jun_marker_indices_by_seat(canvas, first_map)
            table_renderer._same_jun_marker_indices_by_seat(canvas, second_map)

        self.assertEqual(stream_builder.call_count, 1)
        self.assertEqual(len(canvas.same_jun_match_candidate_event_stream), 2)

    def test_same_jun_marker_indices_do_not_queue_confirmation_without_candidates(self) -> None:
        canvas = type("CanvasStub", (), {})()
        canvas.current_round_identity = "test-round"
        canvas.same_jun_public_event_source_state = None
        canvas.same_jun_match_candidate_cache_key = None
        canvas.same_jun_match_candidate_cache_value = {}
        canvas.same_jun_match_candidate_event_stream = ()
        canvas.same_jun_match_candidate_recent_public_events = ()
        canvas.same_jun_match_confirmed_cache_key = None
        canvas.same_jun_match_confirmed_cache_value = {}
        canvas.same_jun_match_async_in_flight = False
        canvas.same_jun_match_async_pending_key = None

        discard = Discard(tile_id=1, draw_type=DrawType.TEDASHI)
        discard.round_discard_index = 0
        discard.event_index = 0
        discard_map = {
            Player.JICHA: [discard],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }

        with patch("ui.table_renderer._queue_same_jun_confirmation") as queue_confirmation:
            result = table_renderer._same_jun_marker_indices_by_seat(canvas, discard_map)

        queue_confirmation.assert_not_called()
        self.assertEqual(
            result,
            {int(player): frozenset() for player in Player},
        )
        self.assertIsInstance(canvas.same_jun_match_confirmed_cache_key, tuple)
        self.assertEqual(canvas.same_jun_match_confirmed_cache_key[0], canvas.current_round_identity)

    def test_same_jun_marker_indices_queue_confirmation_when_candidate_exists(self) -> None:
        canvas = type("CanvasStub", (), {})()
        canvas.current_round_identity = "test-round"
        canvas.same_jun_public_event_source_state = None
        canvas.same_jun_match_candidate_cache_key = None
        canvas.same_jun_match_candidate_cache_value = {}
        canvas.same_jun_match_candidate_event_stream = ()
        canvas.same_jun_match_candidate_recent_public_events = ()
        canvas.same_jun_match_confirmed_cache_key = None
        canvas.same_jun_match_confirmed_cache_value = {}
        canvas.same_jun_match_async_in_flight = False
        canvas.same_jun_match_async_pending_key = None

        first_discard = Discard(tile_id=1, draw_type=DrawType.TEDASHI)
        first_discard.round_discard_index = 0
        first_discard.event_index = 0
        revealing_discard = Discard(tile_id=1, draw_type=DrawType.TEDASHI)
        revealing_discard.round_discard_index = 1
        revealing_discard.event_index = 1
        matching_discard = Discard(tile_id=1, draw_type=DrawType.TEDASHI)
        matching_discard.round_discard_index = 2
        matching_discard.event_index = 2
        discard_map = {
            Player.JICHA: [first_discard, matching_discard],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [revealing_discard],
            Player.KAMICHA: [],
        }

        with patch("ui.table_renderer._queue_same_jun_confirmation") as queue_confirmation:
            result = table_renderer._same_jun_marker_indices_by_seat(canvas, discard_map)

        queue_confirmation.assert_called_once()
        self.assertEqual(result[int(Player.JICHA)], frozenset({1}))
        queued_key = queue_confirmation.call_args.args[1]
        self.assertIsInstance(queued_key, tuple)
        self.assertEqual(queued_key[0], canvas.current_round_identity)


if __name__ == "__main__":
    unittest.main()
