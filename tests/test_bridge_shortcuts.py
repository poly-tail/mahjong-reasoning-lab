import unittest
import queue
from types import SimpleNamespace
from unittest.mock import patch

import ui.table_renderer as table_renderer
from app.pystyle_simulator_protocol import PystyleDisplayContext
from app.tenhou_ui_bridge_protocol import TenhouUiBridgeControl, TenhouUiBridgeStatus
from ui.table_renderer import (
    HAND_AUTO_MODE_KIND_BETAORI,
    HAND_AUTO_MODE_KIND_RECOMMENDATION,
    HAND_PYSTYLE_AUTO_THINK_DELAY_S,
    HAND_PYSTYLE_RESPONSE_EXTRA_THINK_DELAY_S,
    HAND_PYSTYLE_TIMEOUT_FALLBACK_DELAY_S,
    HandAutoModeState,
    HandRecommendationItem,
    HandRecommendationPanelData,
    SelfHandBridgeClickSpec,
    _build_hand_betaori_top3_panel_data,
    _build_bridge_action_control_specs,
    _should_request_bridge_ui_snapshot_on_tick,
    _resolve_bridge_toggle_active_state,
    _resolve_hand_auto_discard_delay_s,
    _resolve_hand_auto_mode_button_presentation,
    _resolve_self_hand_tsumogiri_index,
    _select_bridge_skip_control_id,
    _select_hand_auto_discard_candidate,
    _select_hand_betaori_candidate,
    _select_hand_pystyle_honor_fallback_candidate,
    _clear_thread_activity_notice_if_expired,
    _drain_bridge_background_result_queue,
    _sync_hand_auto_mode_bridge_readiness,
    _request_bridge_table_snapshot,
    _request_bridge_ui_snapshot,
    begin_thread_activity_notice,
    finish_thread_activity_notice,
    show_thread_activity_notice,
)


class BridgeShortcutHelperTests(unittest.TestCase):
    class _DummyNoticeCanvas:
        def __init__(self) -> None:
            self.thread_activity_notice_entries = []
            self.thread_activity_notice_text = ""
            self.thread_activity_notice_expires_monotonic_s = 0.0
            self.redraw_in_progress = False
            self.redraw_calls = 0
            self.redraw_action = self._redraw

        def _redraw(self) -> None:
            self.redraw_calls += 1

        def winfo_exists(self) -> bool:
            return True

        def after(self, _delay_ms: int, callback) -> None:
            callback()
            return None

    def test_select_bridge_skip_control_id_prefers_known_pass_control(self) -> None:
        status = TenhouUiBridgeStatus(
            ws_url="ws://127.0.0.1:8765",
            visible_controls=(
                TenhouUiBridgeControl(control_id=2098693, visible=True, text="ron", label="ron"),
                TenhouUiBridgeControl(control_id=2360326, visible=True, text="x", label="x"),
            ),
        )

        self.assertEqual(_select_bridge_skip_control_id(status), 2360326)

    def test_select_bridge_skip_control_id_falls_back_to_text_hint(self) -> None:
        status = TenhouUiBridgeStatus(
            ws_url="ws://127.0.0.1:8765",
            visible_controls=(
                TenhouUiBridgeControl(control_id=555, visible=True, text="skip", label="skip"),
            ),
        )

        self.assertEqual(_select_bridge_skip_control_id(status), 555)

    def test_resolve_self_hand_tsumogiri_index_returns_rightmost_slot(self) -> None:
        click_specs = (
            SelfHandBridgeClickSpec(rect=(0, 0, 10, 10), hand_index=0, tile_37=1),
            SelfHandBridgeClickSpec(rect=(10, 0, 20, 10), hand_index=5, tile_37=2),
            SelfHandBridgeClickSpec(rect=(20, 0, 30, 10), hand_index=13, tile_37=3),
        )

        self.assertEqual(_resolve_self_hand_tsumogiri_index(click_specs), 13)

    def test_resolve_self_hand_tsumogiri_index_infers_missing_draw_slot_from_contiguous_specs(self) -> None:
        click_specs = tuple(
            SelfHandBridgeClickSpec(
                rect=(index * 10, 0, (index + 1) * 10, 10),
                hand_index=index,
                tile_37=index + 1,
            )
            for index in range(13)
        )

        self.assertEqual(_resolve_self_hand_tsumogiri_index(click_specs), 13)

    def test_resolve_bridge_toggle_active_state_uses_override_until_snapshot_matches(self) -> None:
        self.assertEqual(
            _resolve_bridge_toggle_active_state(False, True),
            (True, False),
        )
        self.assertEqual(
            _resolve_bridge_toggle_active_state(True, True),
            (True, True),
        )

    def test_build_bridge_action_control_specs_groups_visible_actions(self) -> None:
        specs = _build_bridge_action_control_specs(
            (
                TenhouUiBridgeControl(control_id=2360328, visible=True, text="tsumo", label="tsumo"),
                TenhouUiBridgeControl(control_id=409606, visible=True, text="", label=""),
                TenhouUiBridgeControl(control_id=409607, visible=True, text="", label=""),
                TenhouUiBridgeControl(control_id=409610, visible=True, text="", label=""),
                TenhouUiBridgeControl(control_id=401412, visible=True, text="", label=""),
            )
        )

        self.assertEqual(
            [(spec.kind, spec.control_id, spec.label) for spec in specs],
            [
                ("tsumo", 2360328, "ツモ"),
                ("pon", 409606, "ポン1"),
                ("pon", 409607, "ポン2"),
                ("chi", 409610, "チー"),
                ("kan", 401412, "カン"),
            ],
        )

    def test_build_bridge_action_control_specs_includes_generic_naki_button(self) -> None:
        specs = _build_bridge_action_control_specs(
            (
                TenhouUiBridgeControl(control_id=3671045, visible=True, text="", label="鳴き"),
                TenhouUiBridgeControl(control_id=2360326, visible=True, text="skip", label="skip"),
            )
        )

        self.assertEqual(
            [(spec.kind, spec.control_id, spec.label) for spec in specs],
            [
                ("naki", 3671045, "鳴き"),
            ],
        )

    def test_select_hand_auto_discard_candidate_accepts_relaxed_open_hand_context(self) -> None:
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_37=11,
                    tile_text="6m",
                    expected_value=1234.0,
                    expected_value_text="1234pt",
                ),
            ),
            hand_key=(1, 2, 3, 11, 12, 13, 21, 22, 23, 31, 32),
            round_token="east1-0",
            request_context_key=("stale",),
        )
        display_context = PystyleDisplayContext(
            round_token="east1-0",
            allow_history_persist=False,
        )

        candidate = _select_hand_auto_discard_candidate(
            (1, 2, 3, 11, 12, 13, 21, 22, 23, 31, 32),
            panel,
            display_context,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.tile_37, 11)
        self.assertEqual(candidate.tile_text, "6m")
        self.assertEqual(candidate.attempt_key[0], "auto_discard_relaxed")
        self.assertEqual(candidate.attempt_key[-1], 11)

    def test_select_hand_betaori_candidate_chooses_lowest_combined_danger_tile(self) -> None:
        candidate = _select_hand_betaori_candidate(
            (1, 11, 21),
            (
                {1: {"percentage": 55}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            ),
            PystyleDisplayContext(round_token="east1-0"),
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.hand_index, 1)
        self.assertEqual(candidate.tile_37, 11)
        self.assertEqual(candidate.attempt_key[0], "betaori_discard")

    def test_build_hand_betaori_top3_panel_data_sorts_safest_unique_tiles(self) -> None:
        panel = _build_hand_betaori_top3_panel_data(
            (1, 11, 11, 21),
            (
                {1: {"percentage": 55}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 5}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            ),
            PystyleDisplayContext(round_token="east1-0"),
        )

        self.assertEqual([item.tile_37 for item in panel.items], [11, 21, 1])
        self.assertEqual([item.rank for item in panel.items], [1, 2, 3])
        self.assertEqual(panel.items[0].expected_value_text, "危険 5.0%")
        self.assertEqual(panel.status_text, "")

    def test_build_hand_betaori_top3_panel_data_excludes_honor_tiles(self) -> None:
        panel = _build_hand_betaori_top3_panel_data(
            (31, 1, 32, 11, 37),
            (
                {1: {"percentage": 1}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 55}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 2}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 3}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            ),
            PystyleDisplayContext(round_token="east1-0"),
        )

        self.assertEqual([item.tile_37 for item in panel.items], [11, 1])
        self.assertEqual(panel.status_text, "")

    def test_select_hand_betaori_candidate_attempt_key_changes_with_turn_context(self) -> None:
        candidate_a = _select_hand_betaori_candidate(
            (1, 11, 21),
            (
                {1: {"percentage": 55}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            ),
            PystyleDisplayContext(
                round_token="east1-0",
                turn_index=4,
                wall_tiles_remaining=52,
            ),
        )
        candidate_b = _select_hand_betaori_candidate(
            (1, 11, 21),
            (
                {1: {"percentage": 55}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            ),
            PystyleDisplayContext(
                round_token="east1-0",
                turn_index=5,
                wall_tiles_remaining=48,
            ),
        )

        self.assertIsNotNone(candidate_a)
        self.assertIsNotNone(candidate_b)
        assert candidate_a is not None
        assert candidate_b is not None
        self.assertNotEqual(candidate_a.attempt_key, candidate_b.attempt_key)

    def test_select_hand_pystyle_honor_fallback_candidate_prefers_lowest_danger_honor(self) -> None:
        candidate = _select_hand_pystyle_honor_fallback_candidate(
            (31, 11, 32, 21),
            (
                {1: {"percentage": 40}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 15}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            ),
            PystyleDisplayContext(round_token="east1-0"),
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.hand_index, 2)
        self.assertEqual(candidate.tile_37, 32)
        self.assertEqual(candidate.attempt_key[0], "pystyle_shanten_honor_discard")

    def test_select_hand_pystyle_honor_fallback_candidate_falls_back_to_betaori_without_honors(self) -> None:
        candidate = _select_hand_pystyle_honor_fallback_candidate(
            (1, 11, 21),
            (
                {1: {"percentage": 55}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            ),
            PystyleDisplayContext(round_token="east1-0"),
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.hand_index, 1)
        self.assertEqual(candidate.tile_37, 11)
        self.assertEqual(candidate.attempt_key[0], "pystyle_shanten_betaori")

    def test_show_thread_activity_notice_keeps_multiple_active_labels(self) -> None:
        canvas = self._DummyNoticeCanvas()

        with patch.object(table_renderer, "_THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS", canvas):
            with patch("ui.table_renderer.time.monotonic", return_value=100.0):
                show_thread_activity_notice("live suji")
            with patch("ui.table_renderer.time.monotonic", return_value=100.5):
                show_thread_activity_notice("inferred visible")

        self.assertEqual(
            [entry["text"] for entry in canvas.thread_activity_notice_entries],
            ["inferred visible", "live suji"],
        )
        self.assertEqual(canvas.redraw_calls, 2)

    def test_show_thread_activity_notice_refreshes_same_label_without_accumulating_count(self) -> None:
        canvas = self._DummyNoticeCanvas()

        with patch.object(table_renderer, "_THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS", canvas):
            with patch("ui.table_renderer.time.monotonic", return_value=200.0):
                show_thread_activity_notice("memo save")
            with patch("ui.table_renderer.time.monotonic", return_value=200.4):
                show_thread_activity_notice("memo save")

        self.assertEqual(len(canvas.thread_activity_notice_entries), 1)
        self.assertEqual(canvas.thread_activity_notice_entries[0]["text"], "memo save")
        self.assertEqual(canvas.thread_activity_notice_entries[0]["count"], 1)
        self.assertEqual(canvas.thread_activity_notice_entries[0]["expires_monotonic_s"], 205.4)

    def test_begin_and_finish_thread_activity_notice_tracks_concurrent_count(self) -> None:
        canvas = self._DummyNoticeCanvas()

        with patch.object(table_renderer, "_THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS", canvas):
            with patch("ui.table_renderer.time.monotonic", return_value=220.0):
                begin_thread_activity_notice("bridge snapshot")
            with patch("ui.table_renderer.time.monotonic", return_value=220.2):
                begin_thread_activity_notice("bridge snapshot")
            with patch("ui.table_renderer.time.monotonic", return_value=220.4):
                finish_thread_activity_notice("bridge snapshot")

        self.assertEqual(len(canvas.thread_activity_notice_entries), 1)
        self.assertEqual(canvas.thread_activity_notice_entries[0]["text"], "bridge snapshot")
        self.assertEqual(canvas.thread_activity_notice_entries[0]["active_count"], 1)
        self.assertEqual(canvas.thread_activity_notice_entries[0]["count"], 1)
        self.assertEqual(canvas.thread_activity_notice_entries[0]["expires_monotonic_s"], 225.4)

    def test_thread_activity_notice_redraw_is_coalesced_for_rapid_updates(self) -> None:
        canvas = self._DummyNoticeCanvas()

        with patch.object(table_renderer, "_THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS", canvas):
            with patch("ui.table_renderer.time.monotonic", return_value=230.0):
                begin_thread_activity_notice("panel alert sound")
            with patch("ui.table_renderer.time.monotonic", return_value=230.1):
                finish_thread_activity_notice("panel alert sound")

        self.assertEqual(canvas.redraw_calls, 1)

    def test_show_thread_activity_notice_keeps_one_bridge_snapshot_entry(self) -> None:
        canvas = self._DummyNoticeCanvas()

        with patch.object(table_renderer, "_THREAD_ACTIVITY_NOTICE_ACTIVE_CANVAS", canvas):
            with patch("ui.table_renderer.time.monotonic", return_value=300.0):
                show_thread_activity_notice("bridge snapshot")
            with patch("ui.table_renderer.time.monotonic", return_value=300.4):
                show_thread_activity_notice("bridge snapshot")

        self.assertEqual(len(canvas.thread_activity_notice_entries), 1)
        self.assertEqual(canvas.thread_activity_notice_entries[0]["text"], "bridge snapshot")
        self.assertEqual(canvas.thread_activity_notice_entries[0]["count"], 1)
        self.assertEqual(canvas.thread_activity_notice_entries[0]["expires_monotonic_s"], 305.4)

    def test_clear_thread_activity_notice_if_expired_drops_only_expired_entries(self) -> None:
        canvas = self._DummyNoticeCanvas()
        canvas.thread_activity_notice_entries = [
            {"text": "new", "count": 1, "expires_monotonic_s": 12.0},
            {"text": "old", "count": 1, "expires_monotonic_s": 9.0},
        ]

        with patch("ui.table_renderer.time.monotonic", return_value=10.0):
            _clear_thread_activity_notice_if_expired(canvas)

        self.assertEqual(canvas.thread_activity_notice_entries, [
            {"text": "new", "count": 1, "expires_monotonic_s": 12.0},
        ])
        self.assertEqual(canvas.thread_activity_notice_text, "new")
        self.assertEqual(canvas.thread_activity_notice_expires_monotonic_s, 12.0)

    def test_request_bridge_ui_snapshot_coalesces_forced_request_while_in_flight(self) -> None:
        canvas = SimpleNamespace(
            bridge_ui_snapshot_action=lambda: {"ok": True},
            bridge_snapshot_in_flight=True,
            bridge_snapshot_pending_force=False,
            bridge_last_snapshot_started_monotonic_s=10.0,
        )

        with patch("ui.table_renderer._queue_bridge_background_action") as queue_action:
            started = _request_bridge_ui_snapshot(canvas, force=True)

        self.assertTrue(started)
        self.assertTrue(canvas.bridge_snapshot_pending_force)
        queue_action.assert_not_called()

    def test_drain_bridge_background_result_queue_flushes_one_pending_snapshot(self) -> None:
        canvas = SimpleNamespace(
            bridge_background_result_queue=queue.Queue(),
            bridge_ui_snapshot_action=lambda: {"ok": True},
            bridge_snapshot_in_flight=True,
            bridge_snapshot_pending_force=True,
            bridge_last_snapshot_started_monotonic_s=12.0,
            bridge_feedback_text="",
            bridge_feedback_is_error=False,
            bridge_feedback_expires_monotonic_s=0.0,
            bridge_toggle_active_overrides={},
        )
        canvas.bridge_background_result_queue.put(
            {
                "kind": "snapshot",
                "ok": True,
                "result_payload": {
                    "result": {"ok": True},
                },
            }
        )

        with patch("ui.table_renderer._queue_bridge_background_action", return_value=True) as queue_action:
            with patch("ui.table_renderer.time.monotonic", return_value=50.0):
                changed = _drain_bridge_background_result_queue(canvas)

        self.assertTrue(changed)
        self.assertTrue(canvas.bridge_snapshot_in_flight)
        self.assertFalse(canvas.bridge_snapshot_pending_force)
        self.assertEqual(canvas.bridge_last_snapshot_started_monotonic_s, 50.0)
        queue_action.assert_called_once()

    def test_drain_bridge_background_result_queue_retries_map_when_table_state_not_ready(self) -> None:
        scheduled_jobs: list[tuple[int, object]] = []

        def after(delay_ms: int, callback):
            scheduled_jobs.append((delay_ms, callback))
            return "retry-job"

        canvas = SimpleNamespace(
            bridge_background_result_queue=queue.Queue(),
            bridge_table_snapshot_action=lambda: {"result": {"ok": True}},
            bridge_feedback_text="",
            bridge_feedback_is_error=False,
            bridge_feedback_expires_monotonic_s=0.0,
            bridge_table_snapshot_retry_count=0,
            bridge_table_snapshot_retry_job=None,
            bridge_table_snapshot_in_flight=True,
            bridge_toggle_active_overrides={},
            after=after,
            after_cancel=lambda _job: None,
        )
        canvas.bridge_background_result_queue.put(
            {
                "kind": "map",
                "ok": True,
                "result_payload": {
                    "result": {
                        "ok": False,
                        "error": "TABLE_STATE_NOT_READY:z,q,U",
                    },
                },
            }
        )

        with patch("ui.table_renderer.time.monotonic", return_value=50.0):
            changed = _drain_bridge_background_result_queue(canvas)

        self.assertTrue(changed)
        self.assertFalse(canvas.bridge_feedback_is_error)
        self.assertIn("waiting for table state", canvas.bridge_feedback_text)
        self.assertFalse(canvas.bridge_table_snapshot_in_flight)
        self.assertEqual(canvas.bridge_table_snapshot_retry_count, 1)
        self.assertEqual(canvas.bridge_table_snapshot_retry_job, "retry-job")
        self.assertEqual(scheduled_jobs[0][0], table_renderer.BRIDGE_TABLE_SNAPSHOT_READY_RETRY_MS)

    def test_request_bridge_table_snapshot_resets_ready_retry_state(self) -> None:
        cancelled_jobs: list[str] = []
        canvas = SimpleNamespace(
            bridge_table_snapshot_action=lambda: {"result": {"ok": True}},
            bridge_feedback_text="waiting",
            bridge_feedback_is_error=False,
            bridge_feedback_expires_monotonic_s=0.0,
            bridge_table_snapshot_retry_count=3,
            bridge_table_snapshot_retry_job="old-retry",
            bridge_table_snapshot_in_flight=False,
            after_cancel=lambda job: cancelled_jobs.append(job),
        )

        with patch("ui.table_renderer._queue_bridge_background_action", return_value=True) as queue_action:
            with patch("ui.table_renderer._refresh_bridge_widgets"):
                started = _request_bridge_table_snapshot(canvas)

        self.assertTrue(started)
        self.assertEqual(cancelled_jobs, ["old-retry"])
        self.assertEqual(canvas.bridge_table_snapshot_retry_count, 0)
        self.assertIsNone(canvas.bridge_table_snapshot_retry_job)
        self.assertTrue(canvas.bridge_table_snapshot_in_flight)
        self.assertFalse(canvas.bridge_feedback_is_error)
        self.assertEqual(canvas.bridge_feedback_text, "Mapping browser table...")
        queue_action.assert_called_once()

    def test_request_bridge_table_snapshot_does_not_queue_while_in_flight(self) -> None:
        canvas = SimpleNamespace(
            bridge_table_snapshot_action=lambda: {"result": {"ok": True}},
            bridge_feedback_text="",
            bridge_feedback_is_error=False,
            bridge_feedback_expires_monotonic_s=0.0,
            bridge_table_snapshot_retry_count=0,
            bridge_table_snapshot_retry_job=None,
            bridge_table_snapshot_in_flight=True,
        )

        with patch("ui.table_renderer._queue_bridge_background_action") as queue_action:
            with patch("ui.table_renderer._refresh_bridge_widgets"):
                started = _request_bridge_table_snapshot(canvas)

        self.assertFalse(started)
        self.assertFalse(canvas.bridge_feedback_is_error)
        self.assertEqual(canvas.bridge_feedback_text, "Bridge map already running")
        queue_action.assert_not_called()

    def test_should_request_bridge_ui_snapshot_on_tick_requires_connected_ready_bridge(self) -> None:
        canvas = SimpleNamespace(
            bridge_snapshot_source_refresh_token=(1, 0),
            bridge_last_requested_source_refresh_token=None,
        )
        self.assertFalse(
            _should_request_bridge_ui_snapshot_on_tick(
                canvas,
                TenhouUiBridgeStatus(
                    ws_url="ws://127.0.0.1:8765",
                    listening=True,
                    connected=False,
                    extension_ready=False,
                )
            )
        )
        self.assertFalse(
            _should_request_bridge_ui_snapshot_on_tick(
                canvas,
                TenhouUiBridgeStatus(
                    ws_url="ws://127.0.0.1:8765",
                    listening=True,
                    connected=True,
                    extension_ready=False,
                )
            )
        )
        self.assertTrue(
            _should_request_bridge_ui_snapshot_on_tick(
                canvas,
                TenhouUiBridgeStatus(
                    ws_url="ws://127.0.0.1:8765",
                    listening=True,
                    connected=True,
                    extension_ready=True,
                    last_event="extension_ready",
                )
            )
        )

    def test_bridge_status_tick_requests_snapshot_when_live_refresh_token_changes(self) -> None:
        canvas = SimpleNamespace(
            bridge_status_tick_job=None,
            bridge_ui_snapshot_action=lambda: {"ok": True},
            bridge_snapshot_source_refresh_token=(5, 0),
            bridge_last_requested_source_refresh_token=(4, 0),
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                listening=True,
                connected=True,
                extension_ready=True,
                last_event="ui_snapshot_result",
                last_result={"type": "ui_snapshot_result", "result": {"ok": True, "tenhouReady": True}},
            ),
        )
        scheduled = []
        canvas.after = lambda delay_ms, callback: scheduled.append((delay_ms, callback)) or "job-1"

        with patch("ui.table_renderer._drain_bridge_background_result_queue", return_value=False):
            with patch("ui.table_renderer._drain_same_jun_match_background_result_queue", return_value=False):
                with patch("ui.table_renderer._sync_hand_auto_mode_bridge_readiness", return_value=False):
                    with patch("ui.table_renderer._refresh_bridge_widgets"):
                        with patch("ui.table_renderer._request_bridge_ui_snapshot", return_value=True) as request_snapshot:
                            table_renderer._bridge_status_tick(canvas)

        request_snapshot.assert_called_once_with(canvas)
        self.assertEqual(canvas.bridge_last_requested_source_refresh_token, (5, 0))
        self.assertEqual(canvas.bridge_status_tick_job, "job-1")
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], table_renderer.BRIDGE_STATUS_TICK_MS)

    def test_bridge_status_tick_skips_snapshot_when_same_refresh_token_is_already_synced(self) -> None:
        canvas = SimpleNamespace(
            bridge_status_tick_job=None,
            bridge_ui_snapshot_action=lambda: {"ok": True},
            bridge_snapshot_source_refresh_token=(5, 0),
            bridge_last_requested_source_refresh_token=(5, 0),
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                listening=True,
                connected=True,
                extension_ready=True,
                last_event="ui_snapshot_result",
                last_result={"type": "ui_snapshot_result", "result": {"ok": True, "tenhouReady": True}},
            ),
        )
        canvas.after = lambda _delay_ms, _callback: "job-2"

        with patch("ui.table_renderer._drain_bridge_background_result_queue", return_value=False):
            with patch("ui.table_renderer._drain_same_jun_match_background_result_queue", return_value=False):
                with patch("ui.table_renderer._sync_hand_auto_mode_bridge_readiness", return_value=False):
                    with patch("ui.table_renderer._refresh_bridge_widgets"):
                        with patch("ui.table_renderer._request_bridge_ui_snapshot", return_value=True) as request_snapshot:
                            table_renderer._bridge_status_tick(canvas)

        request_snapshot.assert_not_called()
        self.assertEqual(canvas.bridge_status_tick_job, "job-2")

    def test_bridge_status_tick_reschedules_before_transient_drain_error(self) -> None:
        canvas = SimpleNamespace(
            bridge_status_tick_job=None,
            bridge_ui_snapshot_action=lambda: {"ok": True},
            bridge_status_provider=lambda: None,
            last_bridge_status_tick_error_text=None,
        )
        scheduled = []
        canvas.after = lambda delay_ms, callback: scheduled.append((delay_ms, callback)) or "job-3"

        with patch(
            "ui.table_renderer._drain_bridge_background_result_queue",
            side_effect=RuntimeError("boom"),
        ):
            with patch("builtins.print") as print_mock:
                table_renderer._bridge_status_tick(canvas)

        self.assertEqual(canvas.bridge_status_tick_job, "job-3")
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], table_renderer.BRIDGE_STATUS_TICK_MS)
        self.assertEqual(canvas.last_bridge_status_tick_error_text, "RuntimeError: boom")
        print_mock.assert_called_once_with("Bridge status tick failed: RuntimeError: boom")

    def test_resolve_hand_auto_discard_delay_s_uses_betaori_random_window(self) -> None:
        class _FixedRng:
            def __init__(self, value: float) -> None:
                self.value = value

            def uniform(self, _lower: float, _upper: float) -> float:
                return self.value

        self.assertEqual(
            _resolve_hand_auto_discard_delay_s(
                HAND_AUTO_MODE_KIND_RECOMMENDATION,
                rng=_FixedRng(0.8),
            ),
            HAND_PYSTYLE_AUTO_THINK_DELAY_S,
        )
        self.assertEqual(
            _resolve_hand_auto_discard_delay_s(
                HAND_AUTO_MODE_KIND_BETAORI,
                rng=_FixedRng(-0.8),
            ),
            0.7,
        )
        self.assertEqual(
            _resolve_hand_auto_discard_delay_s(
                HAND_AUTO_MODE_KIND_BETAORI,
                rng=_FixedRng(0.0),
            ),
            1.5,
        )
        self.assertEqual(
            _resolve_hand_auto_discard_delay_s(
                HAND_AUTO_MODE_KIND_BETAORI,
                rng=_FixedRng(0.8),
            ),
            2.3,
        )

    def test_resolve_hand_auto_discard_delay_s_adds_extra_wait_when_pystyle_response_is_ready(self) -> None:
        self.assertEqual(
            _resolve_hand_auto_discard_delay_s(
                HAND_AUTO_MODE_KIND_RECOMMENDATION,
                has_usable_pystyle_response=True,
            ),
            HAND_PYSTYLE_AUTO_THINK_DELAY_S + HAND_PYSTYLE_RESPONSE_EXTRA_THINK_DELAY_S,
        )

    def test_resolve_hand_auto_discard_delay_s_caps_timeout_fallback_wait(self) -> None:
        self.assertEqual(
            _resolve_hand_auto_discard_delay_s(
                HAND_AUTO_MODE_KIND_RECOMMENDATION,
                recommendation_timeout_elapsed=True,
            ),
            HAND_PYSTYLE_TIMEOUT_FALLBACK_DELAY_S,
        )

    def test_resolve_hand_auto_mode_button_presentation_uses_beta_label(self) -> None:
        self.assertEqual(
            _resolve_hand_auto_mode_button_presentation(
                HandAutoModeState(enabled=True, mode=HAND_AUTO_MODE_KIND_BETAORI),
                target_mode=HAND_AUTO_MODE_KIND_BETAORI,
                label_prefix="ベタオリ",
                action_available=True,
            )[:3],
            ("ベタオリ ON", "#1f5136", "#d7deea"),
        )

    def test_resolve_hand_auto_mode_button_presentation_uses_pystyle_label(self) -> None:
        self.assertEqual(
            _resolve_hand_auto_mode_button_presentation(
                HandAutoModeState(enabled=True, mode=HAND_AUTO_MODE_KIND_RECOMMENDATION),
                target_mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
                label_prefix="pystyle",
                action_available=True,
            )[:3],
            ("pystyle ON", "#1f5136", "#d7deea"),
        )

    def test_sync_hand_auto_mode_bridge_readiness_keeps_dedupe_after_restore(self) -> None:
        canvas = SimpleNamespace(
            bridge_hand_auto_ready=False,
            bridge_hand_auto_rearm_pending=True,
            hand_response_requested_hand_key=("same-hand",),
            hand_response_last_request_started_monotonic_s=12.5,
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
                in_flight=False,
                last_attempt_key=("auto_discard_relaxed", "same-hand", 11),
                last_error="timeout",
            ),
        )
        status = TenhouUiBridgeStatus(
            ws_url="ws://127.0.0.1:8765",
            listening=True,
            connected=True,
            extension_ready=True,
            last_result={
                "type": "ui_snapshot_result",
                "result": {"ok": True, "tenhouReady": True},
            },
        )

        changed = _sync_hand_auto_mode_bridge_readiness(canvas, status)

        self.assertTrue(changed)
        self.assertTrue(canvas.bridge_hand_auto_ready)
        self.assertFalse(canvas.bridge_hand_auto_rearm_pending)
        self.assertEqual(
            canvas.hand_auto_mode_state,
            HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
                in_flight=False,
                last_attempt_key=("auto_discard_relaxed", "same-hand", 11),
                last_error="timeout",
            ),
        )

    def test_sync_hand_auto_mode_bridge_readiness_marks_rearm_pending_when_bridge_drops(self) -> None:
        canvas = SimpleNamespace(
            bridge_hand_auto_ready=True,
            bridge_hand_auto_rearm_pending=False,
            hand_response_requested_hand_key=("same-hand",),
            hand_response_last_request_started_monotonic_s=3.0,
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
                in_flight=True,
                last_attempt_key=("auto_discard_relaxed", "same-hand", 11),
                last_error="",
            ),
        )
        status = TenhouUiBridgeStatus(
            ws_url="ws://127.0.0.1:8765",
            listening=True,
            connected=True,
            extension_ready=True,
            last_result={
                "type": "ui_snapshot_result",
                "result": {"ok": True, "tenhouReady": False},
            },
        )

        changed = _sync_hand_auto_mode_bridge_readiness(canvas, status)

        self.assertTrue(changed)
        self.assertFalse(canvas.bridge_hand_auto_ready)
        self.assertTrue(canvas.bridge_hand_auto_rearm_pending)
        self.assertIsNone(canvas.hand_response_requested_hand_key)
        self.assertIsNone(canvas.hand_response_last_request_started_monotonic_s)
        self.assertEqual(
            canvas.hand_auto_mode_state,
            HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
                in_flight=False,
                last_attempt_key=("auto_discard_relaxed", "same-hand", 11),
                last_error="Bridge not ready",
            ),
        )


if __name__ == "__main__":
    unittest.main()
