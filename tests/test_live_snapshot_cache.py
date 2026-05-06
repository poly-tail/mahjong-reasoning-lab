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
    tracker_discard = state.tracker.add_discard(Player.SHIMOCHA, 1)
    tracker_discard.round_discard_index = 0
    tracker_discard.event_index = 0
    state.live_update_sequence = 1
    state.sync_current_round_context()
    return state


def _live_suji_bundle_completed(state: CaptureState) -> bool:
    async_state = getattr(state, "live_suji_async_state", None)
    return int(getattr(async_state, "update_sequence", 0)) > 0


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

        def token_reader(_state: CaptureState) -> object:
            return current_token["value"]

        def snapshot_builder(_state: CaptureState) -> app_main.LiveTableSnapshot:
            token = current_token["value"]
            built_tokens.append(token)
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
            self.assertEqual(provider.current_refresh_token(), (1, 0))

            deadline = time.time() + 2.0
            while time.time() < deadline:
                if provider.current_snapshot().refresh_token == (2, 0):
                    break
                time.sleep(0.01)

            self.assertEqual(provider.current_snapshot().refresh_token, (2, 0))
            self.assertIn((2, 0), built_tokens)
        finally:
            provider.stop()

    def test_async_live_table_snapshot_provider_force_reinit_defers_publish_until_built(self) -> None:
        state = CaptureState()
        current_token = {"value": (1, 0)}

        def token_reader(_state: CaptureState) -> object:
            return current_token["value"]

        def snapshot_builder(_state: CaptureState) -> app_main.LiveTableSnapshot:
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
            self.assertEqual(provider.force_reinit(), (1, 0))

            deadline = time.time() + 2.0
            while time.time() < deadline:
                if provider.current_snapshot().refresh_token == (3, 0):
                    break
                time.sleep(0.01)

            self.assertEqual(provider.current_snapshot().refresh_token, (3, 0))
        finally:
            provider.stop()

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
        bundle = app_main._build_live_suji_computation_bundle(
            state,
            visible_summary,
            source_refresh_token=1,
            round_identity=("test-round",),
            input_signature=app_main._build_live_suji_input_signature(state, visible_summary),
        )

        self.assertEqual(bundle.source_refresh_token, 1)
        self.assertIn(int(Player.KAMICHA), bundle.opponent_suji_panel_summaries)

    def test_request_live_suji_bundle_reuses_running_worker_and_sets_wake_event(self) -> None:
        state = _build_live_capture_state()
        visible_summary = app_main.build_live_visible_tile_summary(state)
        async_state = app_main._get_live_suji_async_state(state)
        async_state.worker_running = True
        async_state.wake_event.clear()

        with patch("app.main.threading.Thread") as thread_ctor:
            current_bundle, fallback_bundle = app_main._request_live_suji_bundle(
                state,
                state,
                visible_summary,
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

    def test_request_live_red_tint_bundle_reuses_running_worker_and_sets_wake_event(self) -> None:
        state = _build_live_capture_state()
        async_state = app_main._get_live_red_tint_async_state(state)
        async_state.worker_running = True
        async_state.wake_event.clear()

        with patch("app.main.threading.Thread") as thread_ctor:
            current_indices, fallback_indices = app_main._request_live_red_tint_bundle(
                state,
                state,
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

    def test_build_live_table_snapshot_does_not_reuse_stale_bundle_after_lag_metadata_changes(self) -> None:
        state = _build_live_capture_state()

        app_main.build_live_table_snapshot(state)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if _live_suji_bundle_completed(state):
                break
            time.sleep(0.01)
        self.assertTrue(_live_suji_bundle_completed(state))

        state.current_round.discards[int(Player.SHIMOCHA)][0].lagged = LAG_FLAG_UNCONFIRMED
        state.mark_live_update()
        next_snapshot = app_main.build_live_table_snapshot(state)
        normalized_summary = table_renderer._normalize_opponent_suji_panel_summaries(
            next_snapshot.opponent_suji_panel_summaries
        )

        self.assertTrue(normalized_summary[int(Player.KAMICHA)]["is_loading"])

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
