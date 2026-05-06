import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.pystyle_simulator_protocol import PystyleDisplayContext
import ui.table_renderer as table_renderer
from ui.table_renderer import (
    HAND_AUTO_MODE_KIND_BETAORI,
    HAND_AUTO_MODE_KIND_RECOMMENDATION,
    HandResponsePanelState,
    HandResponseRenderState,
    HandRecommendationItem,
    HandRecommendationPanelData,
    LagMarkerReferenceButtonSpec,
    LiveAsyncRenderState,
    PlayerPanelButtonSpec,
    SidePanelRenderCache,
    SelfHandValueAlertState,
    _cached_layout_runtime_guard_reason,
    _cached_layout_skip_reason,
    _force_manual_ui_reinit,
    _format_phase_timing_breakdown,
    _format_hand_recommendation_value_text,
    _has_usable_current_hand_recommendation,
    _hand_recommendation_request_display_key,
    _render_table_using_cached_layout_if_possible,
    _redraw_live_async_regions_if_possible,
    _hand_recommendation_request_context_key,
    _redraw_hand_response_controls_if_possible,
    _resolve_hand_response_panel_state_for_auto_mode,
    _resolve_request_hand_index_by_tile37,
    _maybe_auto_force_ui_reinit,
    _should_retry_hand_recommendation_for_auto,
    _should_highlight_hand_recommendation_row,
    _should_use_hand_response_only_refresh,
    _should_use_live_async_only_refresh,
    _should_use_pystyle_error_fallback,
    _should_use_pystyle_timeout_fallback,
    _select_hand_auto_discard_candidate,
)


class HandAutoModeTest(unittest.TestCase):
    def test_format_phase_timing_breakdown_sorts_by_elapsed_descending(self) -> None:
        self.assertEqual(
            _format_phase_timing_breakdown(
                (
                    ("overlay", 3.2),
                    ("render_table", 120.4),
                    ("state_prepare", 18.0),
                ),
                top_n=2,
            ),
            "render_table=120.4ms, state_prepare=18.0ms",
        )

    def test_should_use_hand_response_only_refresh_when_only_recommendation_token_changes(self) -> None:
        self.assertTrue(
            _should_use_hand_response_only_refresh(
                ((20, 0), 4),
                ((20, 0), 5),
            )
        )

    def test_should_use_live_async_only_refresh_when_only_async_subtoken_changes(self) -> None:
        self.assertTrue(
            _should_use_live_async_only_refresh(
                ((20, 0), 4),
                ((20, 1), 4),
            )
        )

    def test_should_not_use_live_async_only_refresh_when_live_or_recommendation_changes(self) -> None:
        self.assertFalse(
            _should_use_live_async_only_refresh(
                ((20, 0), 4),
                ((21, 1), 4),
            )
        )
        self.assertFalse(
            _should_use_live_async_only_refresh(
                ((20, 0), 4),
                ((20, 1), 5),
            )
        )

    def test_should_not_use_hand_response_only_refresh_when_live_token_changes(self) -> None:
        self.assertFalse(
            _should_use_hand_response_only_refresh(
                ((20, 0), 4),
                ((21, 0), 5),
            )
        )
        self.assertFalse(
            _should_use_hand_response_only_refresh(
                20,
                21,
            )
        )

    def test_redraw_hand_response_controls_if_possible_uses_cached_render_state(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.hand_response_render_state = HandResponseRenderState(
                    hand_rect=(10.0, 20.0, 30.0, 40.0),
                    button_anchor_right=55.0,
                    hand_visual_top=22.0,
                    baseline_y=38.0,
                    dora_indicator_tiles=(31,),
                    visible_summary=None,
                    recommendation_request_tiles=(11, 12, 13, 14),
                    round_identity=("east1", 0),
                    self_melds=(),
                )
                self.hand_recommendation_panel_provider = lambda: HandRecommendationPanelData(
                    status_text="loading",
                    is_loading=True,
                )
                self.current_hand_recommendation_panel = HandRecommendationPanelData()
                self.current_refresh_token = ((20, 0), 5)
                self.hand_response_panel_state = HandResponsePanelState(visible=True)
                self.redraw_in_progress = False
                self.deleted_tags = []

            def winfo_exists(self) -> bool:
                return True

            def delete(self, tag: str) -> None:
                self.deleted_tags.append(tag)

        canvas = CanvasStub()
        alert_state = SelfHandValueAlertState(kind="warning_ev", label="EV<800")

        with patch(
            "ui.table_renderer._build_self_hand_value_alert_state",
            return_value=alert_state,
        ) as build_alert, patch(
            "ui.table_renderer._should_evaluate_alert_audio_for_refresh_token",
            return_value=True,
        ) as should_audio, patch(
            "ui.table_renderer._play_self_hand_value_alert_sound_if_needed",
        ) as play_audio, patch(
            "ui.table_renderer._draw_hand_response_button_and_panel",
        ) as draw_controls:
            self.assertTrue(_redraw_hand_response_controls_if_possible(canvas))

        build_alert.assert_called_once()
        should_audio.assert_called_once_with(canvas, ((20, 0), 5))
        play_audio.assert_called_once_with(canvas, alert_state)
        self.assertEqual(canvas.deleted_tags, ["hand_response_ui"])
        draw_controls.assert_called_once()
        self.assertEqual(
            draw_controls.call_args.kwargs["canvas_tag"],
            "hand_response_ui",
        )
        self.assertFalse(draw_controls.call_args.kwargs["draw_common_table_situation_panel"])

    def test_redraw_live_async_regions_if_possible_redraws_only_tagged_regions(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.live_async_render_state = LiveAsyncRenderState(
                    layout={"hand_rect": (10.0, 20.0, 40.0, 50.0)},
                    discard_map={},
                    melds_by_player={},
                    dora_indicator_tiles=(31,),
                    visible_summary=SimpleNamespace(),
                    hand_tiles=(11, 12, 13),
                    hand_draw_tile=None,
                    hand_recommendation_panel=HandRecommendationPanelData(),
                    player_score_diffs_by_seat={1: 0, 2: 0, 3: 0},
                    player_names_by_seat={1: "A", 2: "B", 3: "C"},
                    round_events=(),
                    self_hand_value_alert=SelfHandValueAlertState(),
                )
                self.detail_panel_state = SimpleNamespace()
                self.hand_response_panel_state = HandResponsePanelState(visible=False)
                self.image_table = object()
                self.base_image_table = object()
                self.current_round_identity = ("east1", 0)
                self.deleted_tags = []
                self.current_player_names_by_seat = {}
                self.current_player_alert_indicators_by_seat = {}

            def winfo_exists(self) -> bool:
                return True

            def delete(self, tag: str) -> None:
                self.deleted_tags.append(tag)

            def find_all(self) -> tuple[int, ...]:
                return ()

            def addtag_withtag(self, _tag: str, _item_id: int) -> None:
                return None

        canvas = CanvasStub()
        with patch(
            "ui.table_renderer._inferred_visible_runtime_enabled",
            return_value=False,
        ), patch(
            "ui.table_renderer._build_visible_tile_inference_summary_for_canvas",
            return_value=(SimpleNamespace(), ()),
        ), patch(
            "ui.table_renderer._draw_side_panels",
        ) as draw_side_panels, patch(
            "ui.table_renderer._draw_discards",
        ) as draw_discards, patch(
            "ui.table_renderer._draw_hand",
        ) as draw_hand:
            self.assertTrue(
                _redraw_live_async_regions_if_possible(
                    canvas,
                    hand_danger_percentages=[],
                    opponent_suji_panel_summaries={},
                    player_push_alert_percentages={},
                    push_marker_alert_percentages={},
                    player_alert_indicators_by_seat={},
                    discard_red_tint_indices_by_seat={},
                )
            )

        self.assertEqual(
            canvas.deleted_tags,
            [
                "live_async_side_panels",
                "live_async_discards",
                "live_async_hand",
                "hand_response_ui",
            ],
        )
        draw_side_panels.assert_called_once()
        draw_discards.assert_called_once()
        draw_hand.assert_called_once()

    def test_redraw_live_async_regions_if_possible_skips_unchanged_side_panels(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.live_async_render_state = LiveAsyncRenderState(
                    layout={"hand_rect": (10.0, 20.0, 40.0, 50.0)},
                    discard_map={},
                    melds_by_player={},
                    dora_indicator_tiles=(31,),
                    visible_summary=SimpleNamespace(),
                    hand_tiles=(11, 12, 13),
                    hand_draw_tile=None,
                    hand_recommendation_panel=HandRecommendationPanelData(),
                    player_score_diffs_by_seat={1: 0, 2: 0, 3: 0},
                    player_names_by_seat={1: "A", 2: "B", 3: "C"},
                    round_events=(),
                    self_hand_value_alert=SelfHandValueAlertState(),
                )
                self.side_panel_render_cache = SidePanelRenderCache(
                    signature="same-side-panel",
                    player_panel_button_specs=(
                        PlayerPanelButtonSpec(seat=1, label="DETAIL", rect=(1.0, 2.0, 3.0, 4.0)),
                    ),
                    lag_marker_reference_button_specs=(
                        LagMarkerReferenceButtonSpec(kind="blue", center=(8.0, 9.0), radius=5.0),
                    ),
                    detail_images=(object(),),
                )
                self.detail_panel_state = SimpleNamespace()
                self.hand_response_panel_state = HandResponsePanelState(visible=False)
                self.image_table = object()
                self.base_image_table = object()
                self.current_round_identity = ("east1", 0)
                self.deleted_tags = []
                self.current_player_names_by_seat = {}
                self.current_player_alert_indicators_by_seat = {}
                self.player_panel_button_specs = []
                self.lag_marker_reference_button_specs = []
                self.detail_images = []

            def winfo_exists(self) -> bool:
                return True

            def delete(self, tag: str) -> None:
                self.deleted_tags.append(tag)

            def find_all(self) -> tuple[int, ...]:
                return ()

            def addtag_withtag(self, _tag: str, _item_id: int) -> None:
                return None

        canvas = CanvasStub()
        with patch(
            "ui.table_renderer._inferred_visible_runtime_enabled",
            return_value=False,
        ), patch(
            "ui.table_renderer._build_visible_tile_inference_summary_for_canvas",
            return_value=(SimpleNamespace(), ()),
        ), patch(
            "ui.table_renderer._build_side_panel_render_signature",
            return_value="same-side-panel",
        ), patch(
            "ui.table_renderer._draw_side_panels",
        ) as draw_side_panels, patch(
            "ui.table_renderer._draw_discards",
        ) as draw_discards, patch(
            "ui.table_renderer._draw_hand",
        ) as draw_hand:
            self.assertTrue(
                _redraw_live_async_regions_if_possible(
                    canvas,
                    hand_danger_percentages=[],
                    opponent_suji_panel_summaries={},
                    player_push_alert_percentages={},
                    push_marker_alert_percentages={},
                    player_alert_indicators_by_seat={},
                    discard_red_tint_indices_by_seat={},
                )
            )

        self.assertEqual(
            canvas.deleted_tags,
            [
                "live_async_discards",
                "live_async_hand",
                "hand_response_ui",
            ],
        )
        draw_side_panels.assert_not_called()
        draw_discards.assert_called_once()
        draw_hand.assert_called_once()
        self.assertEqual(
            canvas.player_panel_button_specs,
            [PlayerPanelButtonSpec(seat=1, label="DETAIL", rect=(1.0, 2.0, 3.0, 4.0))],
        )
        self.assertEqual(
            canvas.lag_marker_reference_button_specs,
            [LagMarkerReferenceButtonSpec(kind="blue", center=(8.0, 9.0), radius=5.0)],
        )
        self.assertEqual(len(canvas.detail_images), 1)

    def test_cached_layout_skip_reason_reports_layout_delta(self) -> None:
        canvas = SimpleNamespace(
            last_render_layout_signature=(670, 640, 1.0, "stable"),
            last_render_layout={
                "detail_content_rect": (0.0, 0.0, 10.0, 10.0),
                "hand_rect": (0.0, 0.0, 10.0, 10.0),
            },
            layout_drag_enabled=False,
        )

        with patch("ui.table_renderer._inferred_visible_runtime_enabled", return_value=False):
            reason = _cached_layout_skip_reason(canvas, (800, 640, 1.0, "stable"))

        self.assertEqual(reason, "width=670->800")

    def test_cached_layout_runtime_guard_reason_reports_destroyed_canvas(self) -> None:
        canvas = SimpleNamespace(
            layout_drag_enabled=False,
            last_render_layout={
                "detail_content_rect": (0.0, 0.0, 10.0, 10.0),
                "hand_rect": (0.0, 0.0, 10.0, 10.0),
            },
            winfo_exists=lambda: False,
        )

        with patch("ui.table_renderer._inferred_visible_runtime_enabled", return_value=False):
            reason = _cached_layout_runtime_guard_reason(canvas)

        self.assertEqual(reason, "canvas_destroyed")

    def test_force_manual_ui_reinit_clears_redraw_flags_and_resets_caches(self) -> None:
        canvas = SimpleNamespace(
            redraw_in_progress=True,
            redraw_request_pending=True,
            last_redraw_started_monotonic_s=10.0,
            last_redraw_request_monotonic_s=12.0,
            current_refresh_token=("current", 1),
            last_completed_redraw_refresh_token=("old", 1),
            live_async_render_state=object(),
            last_render_layout={"detail_content_rect": (0.0, 0.0, 1.0, 1.0)},
            last_render_layout_signature=("layout", 1),
            last_render_detail_content_rect=(0.0, 0.0, 1.0, 1.0),
            side_panel_render_cache=object(),
        )
        request_redraw_calls: list[dict[str, object]] = []
        reinit_calls: list[str] = []

        reason = _force_manual_ui_reinit(
            canvas,
            request_redraw=lambda **kwargs: request_redraw_calls.append(dict(kwargs)),
            table_snapshot_reinit_action=lambda: reinit_calls.append("called"),
        )

        self.assertEqual(
            reason,
            "snapshot_cache_invalidated,cleared_redraw_in_progress,cleared_pending_redraw_request,cleared_ui_render_cache",
        )
        self.assertFalse(canvas.redraw_in_progress)
        self.assertFalse(canvas.redraw_request_pending)
        self.assertEqual(canvas.last_redraw_started_monotonic_s, 0.0)
        self.assertEqual(canvas.last_redraw_request_monotonic_s, 0.0)
        self.assertIsNone(canvas.live_async_render_state)
        self.assertIsNone(canvas.last_render_layout)
        self.assertIsNone(canvas.last_render_layout_signature)
        self.assertIsNone(canvas.last_render_detail_content_rect)
        self.assertIsNone(canvas.side_panel_render_cache)
        self.assertEqual(reinit_calls, ["called"])
        self.assertEqual(request_redraw_calls, [{"replace_pending": True}])

    def test_force_manual_ui_reinit_still_requests_redraw_without_stale_flags(self) -> None:
        canvas = SimpleNamespace(
            redraw_in_progress=False,
            redraw_request_pending=False,
            last_redraw_started_monotonic_s=0.0,
            last_redraw_request_monotonic_s=0.0,
            current_refresh_token=("current", 2),
            last_completed_redraw_refresh_token=("old", 1),
            live_async_render_state=None,
            last_render_layout={"detail_content_rect": (0.0, 0.0, 1.0, 1.0)},
            last_render_layout_signature=("layout", 2),
            last_render_detail_content_rect=(0.0, 0.0, 1.0, 1.0),
            side_panel_render_cache=object(),
        )
        request_redraw_calls: list[dict[str, object]] = []

        reason = _force_manual_ui_reinit(
            canvas,
            request_redraw=lambda **kwargs: request_redraw_calls.append(dict(kwargs)),
            table_snapshot_reinit_action=None,
        )

        self.assertEqual(reason, "cleared_ui_render_cache")
        self.assertEqual(request_redraw_calls, [{"replace_pending": True}])

    def test_force_manual_ui_reinit_updates_refresh_token_and_restarts_mapping(self) -> None:
        canvas = SimpleNamespace(
            redraw_in_progress=False,
            redraw_request_pending=False,
            last_redraw_started_monotonic_s=0.0,
            last_redraw_request_monotonic_s=0.0,
            current_refresh_token=("old", 1),
            last_refresh_token_change_monotonic_s=0.0,
            live_async_render_state=object(),
            last_render_layout={"detail_content_rect": (0.0, 0.0, 1.0, 1.0)},
            last_render_layout_signature=("layout", 3),
            last_render_detail_content_rect=(0.0, 0.0, 1.0, 1.0),
            side_panel_render_cache=object(),
        )
        request_redraw_calls: list[dict[str, object]] = []
        mapping_calls: list[str] = []

        with patch("ui.table_renderer.time.monotonic", return_value=42.0):
            reason = _force_manual_ui_reinit(
                canvas,
                request_redraw=lambda **kwargs: request_redraw_calls.append(dict(kwargs)),
                table_snapshot_reinit_action=lambda: ("new", 2),
                realtime_mapping_request=lambda: mapping_calls.append("called") or True,
            )

        self.assertEqual(
            reason,
            "snapshot_cache_invalidated,refresh_token_updated,realtime_mapping_requested,cleared_ui_render_cache",
        )
        self.assertEqual(canvas.current_refresh_token, ("new", 2))
        self.assertEqual(canvas.last_refresh_token_change_monotonic_s, 42.0)
        self.assertEqual(mapping_calls, ["called"])
        self.assertEqual(request_redraw_calls, [{"replace_pending": True}])

    def test_auto_force_ui_reinit_uses_same_reinit_path_after_stalled_redraw(self) -> None:
        canvas = SimpleNamespace(
            redraw_in_progress=True,
            redraw_request_pending=True,
            last_redraw_started_monotonic_s=10.0,
            last_redraw_request_monotonic_s=11.0,
            last_refresh_token_change_monotonic_s=12.0,
            last_auto_reinit_monotonic_s=0.0,
            last_auto_reinit_reason=None,
            current_refresh_token=("current", 3),
            last_completed_redraw_refresh_token=("old", 2),
            live_async_render_state=object(),
            last_render_layout={"detail_content_rect": (0.0, 0.0, 1.0, 1.0)},
            last_render_layout_signature=("layout", 3),
            last_render_detail_content_rect=(0.0, 0.0, 1.0, 1.0),
            side_panel_render_cache=object(),
        )
        request_redraw_calls: list[dict[str, object]] = []
        reinit_calls: list[str] = []

        with patch("ui.table_renderer._log_auto_ui_reinit") as log_auto:
            reason = _maybe_auto_force_ui_reinit(
                canvas,
                now_monotonic=25.5,
                request_redraw=lambda **kwargs: request_redraw_calls.append(dict(kwargs)),
                table_snapshot_reinit_action=lambda: reinit_calls.append("called"),
            )

        self.assertEqual(
            reason,
            "auto_redraw_in_progress_stalled,snapshot_cache_invalidated,cleared_redraw_in_progress,cleared_pending_redraw_request,cleared_ui_render_cache",
        )
        self.assertEqual(canvas.last_auto_reinit_monotonic_s, 25.5)
        self.assertEqual(canvas.last_auto_reinit_reason, reason)
        self.assertFalse(canvas.redraw_in_progress)
        self.assertFalse(canvas.redraw_request_pending)
        self.assertEqual(reinit_calls, ["called"])
        self.assertEqual(request_redraw_calls, [{"replace_pending": True}])
        log_auto.assert_called_once()

    def test_auto_force_ui_reinit_restarts_realtime_mapping_after_stalled_redraw(self) -> None:
        canvas = SimpleNamespace(
            redraw_in_progress=False,
            redraw_request_pending=True,
            last_redraw_started_monotonic_s=0.0,
            last_redraw_request_monotonic_s=10.0,
            last_refresh_token_change_monotonic_s=12.0,
            last_auto_reinit_monotonic_s=0.0,
            last_auto_reinit_reason=None,
            current_refresh_token=("current", 5),
            last_completed_redraw_refresh_token=("old", 4),
            live_async_render_state=object(),
            last_render_layout={"detail_content_rect": (0.0, 0.0, 1.0, 1.0)},
            last_render_layout_signature=("layout", 5),
            last_render_detail_content_rect=(0.0, 0.0, 1.0, 1.0),
            side_panel_render_cache=object(),
        )
        request_redraw_calls: list[dict[str, object]] = []
        reinit_calls: list[str] = []
        mapping_calls: list[str] = []

        with patch("ui.table_renderer._log_auto_ui_reinit"):
            reason = _maybe_auto_force_ui_reinit(
                canvas,
                now_monotonic=25.5,
                request_redraw=lambda **kwargs: request_redraw_calls.append(dict(kwargs)),
                table_snapshot_reinit_action=lambda: reinit_calls.append("called"),
                realtime_mapping_request=lambda: mapping_calls.append("called") or True,
            )

        self.assertEqual(
            reason,
            "auto_redraw_request_pending_stalled,snapshot_cache_invalidated,realtime_mapping_requested,cleared_pending_redraw_request,cleared_ui_render_cache",
        )
        self.assertEqual(reinit_calls, ["called"])
        self.assertEqual(mapping_calls, ["called"])
        self.assertEqual(request_redraw_calls, [{"replace_pending": True}])

    def test_auto_force_ui_reinit_uses_first_uncompleted_refresh_time(self) -> None:
        canvas = SimpleNamespace(
            redraw_in_progress=False,
            redraw_request_pending=False,
            last_redraw_started_monotonic_s=0.0,
            last_redraw_request_monotonic_s=0.0,
            last_refresh_token_change_monotonic_s=24.0,
            uncompleted_refresh_token_started_monotonic_s=10.0,
            last_auto_reinit_monotonic_s=0.0,
            last_auto_reinit_reason=None,
            current_refresh_token=("current", 6),
            last_completed_redraw_refresh_token=("old", 5),
            live_async_render_state=object(),
            last_render_layout={"detail_content_rect": (0.0, 0.0, 1.0, 1.0)},
            last_render_layout_signature=("layout", 6),
            last_render_detail_content_rect=(0.0, 0.0, 1.0, 1.0),
            side_panel_render_cache=object(),
        )
        request_redraw_calls: list[dict[str, object]] = []

        with patch("ui.table_renderer._log_auto_ui_reinit"):
            reason = _maybe_auto_force_ui_reinit(
                canvas,
                now_monotonic=25.5,
                request_redraw=lambda **kwargs: request_redraw_calls.append(dict(kwargs)),
                table_snapshot_reinit_action=lambda: None,
            )

        self.assertEqual(
            reason,
            "auto_refresh_token_stalled,snapshot_cache_invalidated,cleared_ui_render_cache",
        )
        self.assertEqual(request_redraw_calls, [{"replace_pending": True}])

    def test_auto_force_ui_reinit_starts_uncompleted_refresh_timer_without_firing(self) -> None:
        canvas = SimpleNamespace(
            redraw_in_progress=False,
            redraw_request_pending=False,
            last_redraw_started_monotonic_s=0.0,
            last_redraw_request_monotonic_s=0.0,
            last_refresh_token_change_monotonic_s=24.0,
            uncompleted_refresh_token_started_monotonic_s=0.0,
            last_auto_reinit_monotonic_s=0.0,
            last_auto_reinit_reason=None,
            current_refresh_token=("current", 7),
            last_completed_redraw_refresh_token=("old", 6),
            live_async_render_state=object(),
            last_render_layout={"detail_content_rect": (0.0, 0.0, 1.0, 1.0)},
            last_render_layout_signature=("layout", 7),
            last_render_detail_content_rect=(0.0, 0.0, 1.0, 1.0),
            side_panel_render_cache=object(),
        )

        reason = _maybe_auto_force_ui_reinit(
            canvas,
            now_monotonic=25.5,
            request_redraw=lambda **_kwargs: None,
            table_snapshot_reinit_action=lambda: None,
        )

        self.assertIsNone(reason)
        self.assertEqual(canvas.uncompleted_refresh_token_started_monotonic_s, 25.5)

    def test_auto_force_ui_reinit_respects_cooldown(self) -> None:
        canvas = SimpleNamespace(
            redraw_in_progress=True,
            redraw_request_pending=False,
            last_redraw_started_monotonic_s=10.0,
            last_redraw_request_monotonic_s=0.0,
            last_refresh_token_change_monotonic_s=0.0,
            last_auto_reinit_monotonic_s=20.0,
            last_auto_reinit_reason="previous",
            current_refresh_token=("current", 4),
            last_completed_redraw_refresh_token=("old", 3),
            live_async_render_state=object(),
            last_render_layout={"detail_content_rect": (0.0, 0.0, 1.0, 1.0)},
            last_render_layout_signature=("layout", 4),
            last_render_detail_content_rect=(0.0, 0.0, 1.0, 1.0),
            side_panel_render_cache=object(),
        )
        request_redraw_calls: list[dict[str, object]] = []

        with patch("ui.table_renderer._log_auto_ui_reinit") as log_auto:
            reason = _maybe_auto_force_ui_reinit(
                canvas,
                now_monotonic=30.0,
                request_redraw=lambda **kwargs: request_redraw_calls.append(dict(kwargs)),
                table_snapshot_reinit_action=None,
            )

        self.assertIsNone(reason)
        self.assertEqual(request_redraw_calls, [])
        log_auto.assert_not_called()

    def test_render_table_using_cached_layout_allows_active_redraw_pass(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.redraw_in_progress = True
                self.layout_drag_enabled = False
                self.current_round_identity = ("east1", 0)
                self.current_ui_scale = 1.0
                self.last_render_layout = {
                    "detail_content_rect": (1.0, 2.0, 3.0, 4.0),
                    "hand_rect": (10.0, 20.0, 30.0, 40.0),
                    "center_panel": (0.0, 0.0, 1.0, 1.0),
                }
                self.deleted_tags = []

            def winfo_exists(self) -> bool:
                return True

            def delete(self, tag: str) -> None:
                self.deleted_tags.append(tag)

            def find_all(self) -> tuple[int, ...]:
                return ()

            def addtag_withtag(self, _tag: str, _item_id: int) -> None:
                return None

        canvas = CanvasStub()

        with patch(
            "ui.table_renderer._inferred_visible_runtime_enabled",
            return_value=False,
        ), patch(
            "ui.table_renderer._build_visible_tile_inference_summary_for_canvas",
            return_value=(SimpleNamespace(), ()),
        ), patch(
            "ui.table_renderer._redraw_side_panels_if_needed",
        ) as redraw_side_panels, patch(
            "ui.table_renderer._draw_center_panel",
        ), patch(
            "ui.table_renderer._draw_meld_zones",
        ), patch(
            "ui.table_renderer._draw_discard_zones",
        ), patch(
            "ui.table_renderer._draw_seat_labels",
        ), patch(
            "ui.table_renderer._draw_melds",
        ), patch(
            "ui.table_renderer._draw_discards",
        ), patch(
            "ui.table_renderer._draw_table_situation_seat_panels",
        ), patch(
            "ui.table_renderer._draw_inferred_visible_sections",
        ), patch(
            "ui.table_renderer._draw_hand",
        ):
            reused, detail_rect = _render_table_using_cached_layout_if_possible(
                canvas,
                img_table=object(),
                discard_map={},
                hand_tiles=[],
                hand_draw_tile=None,
                hand_recommendation_panel=HandRecommendationPanelData(),
                hand_danger_percentages=[],
                opponent_suji_panel_summaries={},
                player_push_alert_percentages={},
                push_marker_alert_percentages={},
                player_alert_indicators_by_seat={},
                player_score_diffs_by_seat={},
                discard_red_tint_indices_by_seat={},
                player_names_by_seat={},
                meld_tiles=[],
                dora_indicator_tiles=[],
                round_events=(),
                round_info_panel=SimpleNamespace(),
                melds_by_player={},
                visible_summary=SimpleNamespace(),
                self_hand_value_alert=SelfHandValueAlertState(),
            )

        self.assertTrue(reused)
        self.assertEqual(detail_rect, (1.0, 2.0, 3.0, 4.0))
        redraw_side_panels.assert_called_once()

    def test_recommendation_auto_mode_forces_ai_top3_panel_visible(self) -> None:
        self.assertEqual(
            _resolve_hand_response_panel_state_for_auto_mode(
                None,
                auto_mode_enabled=True,
                auto_mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            HandResponsePanelState(visible=True),
        )

    def test_non_recommendation_auto_mode_does_not_auto_open_ai_top3_panel(self) -> None:
        self.assertEqual(
            _resolve_hand_response_panel_state_for_auto_mode(
                None,
                auto_mode_enabled=True,
                auto_mode=HAND_AUTO_MODE_KIND_BETAORI,
            ),
            HandResponsePanelState(visible=False),
        )

    def test_manual_ai_top3_panel_visibility_survives_auto_mode_disable(self) -> None:
        self.assertEqual(
            _resolve_hand_response_panel_state_for_auto_mode(
                HandResponsePanelState(visible=True),
                auto_mode_enabled=False,
                auto_mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            HandResponsePanelState(visible=True),
        )

    def test_format_hand_recommendation_value_text_includes_agari_rate(self) -> None:
        recommendation = HandRecommendationItem(
            rank=1,
            tile_37=25,
            tile_text="5s",
            expected_value=3200.0,
            expected_value_text="3200pt",
            win_probability=0.1234,
        )

        self.assertEqual(
            _format_hand_recommendation_value_text(recommendation),
            "3200pt 12.3%",
        )

    def test_highlight_hand_recommendation_row_for_entries_within_fifty_points(self) -> None:
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_37=11,
                    tile_text="6m",
                    expected_value=3200.0,
                    expected_value_text="3200pt",
                ),
                HandRecommendationItem(
                    rank=2,
                    tile_37=12,
                    tile_text="7m",
                    expected_value=3155.0,
                    expected_value_text="3155pt",
                ),
                HandRecommendationItem(
                    rank=3,
                    tile_37=13,
                    tile_text="8m",
                    expected_value=3149.0,
                    expected_value_text="3149pt",
                ),
            ),
            top_expected_value=3200.0,
        )

        self.assertTrue(
            _should_highlight_hand_recommendation_row(
                panel,
                panel.items[0],
                0,
            )
        )
        self.assertTrue(
            _should_highlight_hand_recommendation_row(
                panel,
                panel.items[1],
                1,
            )
        )
        self.assertFalse(
            _should_highlight_hand_recommendation_row(
                panel,
                panel.items[2],
                2,
            )
        )

    def test_select_auto_discard_candidate_requires_exact_current_snapshot(self) -> None:
        display_context = PystyleDisplayContext(
            turn_index=7,
            turn_source="remaining_wall_formula",
            wall_tiles_remaining=42,
            round_wind=27,
            seat_wind=27,
            dora_indicator_tiles_37=(31,),
            round_token="east-1",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_37=25,
                    tile_text="5s",
                    expected_value=3200.0,
                    expected_value_text="3200pt",
                ),
            ),
            hand_key=(1, 2, 3, 25),
            round_token="east-1",
            request_context_key=_hand_recommendation_request_context_key(display_context),
        )

        candidate = _select_hand_auto_discard_candidate(
            [3, 2, 25, 1],
            panel,
            display_context,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.tile_37, 25)
        self.assertEqual(candidate.tile_text, "5s")
        self.assertEqual(candidate.attempt_key[-1], 25)

    def test_select_auto_discard_candidate_skips_post_discard_reuse_context(self) -> None:
        display_context = PystyleDisplayContext(
            round_token="east-1",
            request_fallback_tile_37=19,
            allow_history_persist=False,
        )
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_37=19,
                    tile_text="9p",
                    expected_value=1200.0,
                    expected_value_text="1200pt",
                ),
            ),
            hand_key=(11, 12, 13, 19),
            round_token="east-1",
            request_context_key=_hand_recommendation_request_context_key(display_context),
        )

        self.assertIsNone(
            _select_hand_auto_discard_candidate(
                [11, 12, 13, 19],
                panel,
                display_context,
            )
        )

    def test_select_auto_discard_candidate_accepts_stale_context_key_when_same_hand_is_visible(self) -> None:
        display_context = PystyleDisplayContext(
            turn_index=6,
            wall_tiles_remaining=46,
            round_token="east-2",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_37=9,
                    tile_text="9m",
                    expected_value=1800.0,
                    expected_value_text="1800pt",
                ),
            ),
            hand_key=(1, 2, 3, 9),
            round_token="east-2",
            request_context_key=("stale",),
        )

        candidate = _select_hand_auto_discard_candidate(
            [1, 2, 3, 9],
            panel,
            display_context,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.tile_37, 9)
        self.assertEqual(candidate.attempt_key[0], "auto_discard_relaxed")

    def test_select_auto_discard_candidate_accepts_same_round_core_context(self) -> None:
        display_context = PystyleDisplayContext(
            turn_index=9,
            wall_tiles_remaining=34,
            round_wind=27,
            seat_wind=27,
            dora_indicator_tiles_37=(31,),
            round_token="east-3",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_37=7,
                    tile_text="7m",
                    expected_value=2400.0,
                    expected_value_text="2400pt",
                ),
            ),
            hand_key=(1, 2, 3, 7),
            round_token="east-3",
            request_context_key=(
                8,
                "remaining_wall_formula",
                38,
                27,
                27,
                (31,),
                (),
                (),
                "east-3",
            ),
        )

        candidate = _select_hand_auto_discard_candidate(
            [1, 2, 3, 7],
            panel,
            display_context,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.tile_37, 7)

    def test_retry_hand_recommendation_for_auto_when_same_hand_has_no_items(self) -> None:
        display_context = PystyleDisplayContext(
            round_token="east-1",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(),
            hand_key=(1, 2, 3, 4),
            round_token="east-1",
            status_text="HTTP 502",
            is_loading=False,
        )
        current_request_key = ("request", "east-1", (1, 2, 3, 4))

        self.assertTrue(
            _should_retry_hand_recommendation_for_auto(
                [1, 2, 3, 4],
                panel,
                display_context,
                current_request_key,
                current_request_key,
                0.0,
                auto_mode_enabled=True,
            )
        )

    def test_pystyle_timeout_fallback_starts_after_three_seconds_from_turn_start(self) -> None:
        display_context = PystyleDisplayContext(
            round_token="east-1",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(),
            hand_key=(31, 11, 32, 21),
            round_token="east-1",
            status_text="loading",
            is_loading=True,
        )
        current_request_key = _hand_recommendation_request_display_key(
            panel.hand_key,
            display_context,
        )

        self.assertTrue(
            _should_use_pystyle_timeout_fallback(
                panel.hand_key,
                panel,
                display_context,
                current_request_key,
                current_request_key,
                10.0,
                timeout_fallback_applied_turn_key=None,
                now_monotonic_s=13.1,
            )
        )

    def test_pystyle_timeout_fallback_waits_before_three_seconds_from_turn_start(self) -> None:
        display_context = PystyleDisplayContext(
            round_token="east-1",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(),
            hand_key=(31, 11, 32, 21),
            round_token="east-1",
            status_text="loading",
            is_loading=True,
        )
        current_request_key = _hand_recommendation_request_display_key(
            panel.hand_key,
            display_context,
        )

        self.assertFalse(
            _should_use_pystyle_timeout_fallback(
                panel.hand_key,
                panel,
                display_context,
                current_request_key,
                current_request_key,
                10.0,
                timeout_fallback_applied_turn_key=None,
                now_monotonic_s=12.9,
            )
        )

    def test_pystyle_timeout_fallback_does_not_repeat_after_same_turn_already_fallbacked(self) -> None:
        display_context = PystyleDisplayContext(
            round_token="east-1",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(),
            hand_key=(31, 11, 32, 21),
            round_token="east-1",
            status_text="loading",
            is_loading=True,
        )
        current_request_key = _hand_recommendation_request_display_key(
            panel.hand_key,
            display_context,
        )

        self.assertFalse(
            _should_use_pystyle_timeout_fallback(
                panel.hand_key,
                panel,
                display_context,
                current_request_key,
                current_request_key,
                10.0,
                timeout_fallback_applied_turn_key=current_request_key,
                now_monotonic_s=13.5,
            )
        )

    def test_pystyle_error_fallback_starts_after_two_seconds_for_same_hand_error_state(self) -> None:
        display_context = PystyleDisplayContext(
            round_token="east-1",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(),
            hand_key=(31, 11, 32, 21),
            round_token="east-1",
            status_text="HTTP 502",
            is_loading=False,
        )
        current_request_key = _hand_recommendation_request_display_key(
            panel.hand_key,
            display_context,
        )

        self.assertTrue(
            _should_use_pystyle_error_fallback(
                panel.hand_key,
                panel,
                display_context,
                current_request_key,
                current_request_key,
                10.0,
                now_monotonic_s=12.1,
            )
        )

    def test_pystyle_error_fallback_waits_while_error_response_is_still_fresh(self) -> None:
        display_context = PystyleDisplayContext(
            round_token="east-1",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(),
            hand_key=(31, 11, 32, 21),
            round_token="east-1",
            status_text="HTTP 502",
            is_loading=False,
        )
        current_request_key = _hand_recommendation_request_display_key(
            panel.hand_key,
            display_context,
        )

        self.assertFalse(
            _should_use_pystyle_error_fallback(
                panel.hand_key,
                panel,
                display_context,
                current_request_key,
                current_request_key,
                10.0,
                now_monotonic_s=11.9,
            )
        )

    def test_has_usable_current_hand_recommendation_rejects_different_round_core(self) -> None:
        display_context = PystyleDisplayContext(
            round_wind=27,
            seat_wind=27,
            dora_indicator_tiles_37=(31,),
            round_token="east-4",
            allow_history_persist=True,
        )
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_37=4,
                    tile_text="4m",
                    expected_value=1800.0,
                    expected_value_text="1800pt",
                ),
            ),
            hand_key=(1, 2, 3, 4),
            round_token="east-4",
            request_context_key=(
                7,
                "remaining_wall_formula",
                42,
                28,
                27,
                (31,),
                (),
                (),
                "east-4",
            ),
        )

        self.assertFalse(
            _has_usable_current_hand_recommendation(
                [1, 2, 3, 4],
                panel,
                display_context,
            )
        )

    def test_resolve_request_hand_index_by_tile37_falls_back_between_normal_and_red_fives(self) -> None:
        self.assertEqual(
            _resolve_request_hand_index_by_tile37([1, 10, 11], 5),
            1,
        )
        self.assertEqual(
            _resolve_request_hand_index_by_tile37([1, 2, 20, 21], 15),
            2,
        )


if __name__ == "__main__":
    unittest.main()
