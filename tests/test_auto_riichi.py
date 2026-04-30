from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.pystyle_simulator_protocol import PystyleDisplayContext
from app.tenhou_ui_bridge_protocol import (
    TenhouUiBridgeControl,
    TenhouUiBridgeStatus,
    TenhouUiBridgeToggleControl,
)
from ui.table_renderer import (
    BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
    BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
    HAND_PYSTYLE_AUTO_THINK_DELAY_S,
    HAND_PYSTYLE_RESPONSE_EXTRA_THINK_DELAY_S,
    HAND_PYSTYLE_TIMEOUT_FALLBACK_DELAY_S,
    HAND_AUTO_MODE_KIND_RECOMMENDATION,
    HandAutoModeState,
    HandRecommendationItem,
    HandRecommendationPanelData,
    _build_pystyle_auto_discard_action_with_riichi_guard,
    _build_bridge_action_control_specs,
    _hand_recommendation_request_context_key,
    _maybe_start_hand_auto_discard,
    _place_bridge_action_controls_frame,
    _reset_hand_auto_mode_volatile_state,
    _restart_hand_recommendation_request_after_error,
    _restart_hand_recommendation_request_after_timeout,
)


class AutoRiichiTests(unittest.TestCase):
    def test_place_bridge_action_controls_frame_hides_empty_frame(self) -> None:
        class _FakeChild:
            def __init__(self, manager: str) -> None:
                self._manager = manager

            def winfo_manager(self) -> str:
                return self._manager

        class _FakeFrame:
            def __init__(self) -> None:
                self.place_forget_called = 0

            def winfo_exists(self) -> bool:
                return True

            def winfo_children(self) -> list[object]:
                return [_FakeChild("")]

            def place_forget(self) -> None:
                self.place_forget_called += 1

        frame = _FakeFrame()
        canvas = SimpleNamespace(
            bridge_action_controls_frame=frame,
            current_hand_rect=(0.0, 0.0, 10.0, 10.0),
        )

        _place_bridge_action_controls_frame(canvas)

        self.assertEqual(frame.place_forget_called, 1)

    def test_bridge_action_specs_include_riichi_button(self) -> None:
        specs = _build_bridge_action_control_specs(
            (
                TenhouUiBridgeControl(control_id=2359814, visible=True, text="", label=""),
            )
        )

        self.assertEqual([(spec.kind, spec.control_id) for spec in specs], [("riichi", 2359814)])

    def test_pystyle_auto_enables_auto_agari_before_other_actions(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=False,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=False,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (1, 2, 3, 11, 12, 13, 21, 22, 23, 24, 25, 31, 32, 33)
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
            hand_key=request_tiles,
            round_token="east1-0",
        )
        display_context = PystyleDisplayContext(round_token="east1-0")

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                (),
                (),
            )

        start_action.assert_called_once()
        self.assertEqual(start_action.call_args.kwargs["current_mode"], HAND_AUTO_MODE_KIND_RECOMMENDATION)
        self.assertEqual(start_action.call_args.kwargs["attempt_key"][:2], ("auto_auto_agari_on", 1183752))

    def test_pystyle_auto_enables_naki_disabled_before_other_actions(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_toggle_active_overrides={},
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=False,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (1, 2, 3, 11, 12, 13, 21, 22, 23, 24, 25, 31, 32, 33)
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
            hand_key=request_tiles,
            round_token="east1-0",
        )
        display_context = PystyleDisplayContext(round_token="east1-0")

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                (),
                (),
            )

        start_action.assert_called_once()
        self.assertEqual(start_action.call_args.kwargs["current_mode"], HAND_AUTO_MODE_KIND_RECOMMENDATION)
        self.assertEqual(start_action.call_args.kwargs["attempt_key"][:2], ("auto_naki_disabled_on", 1183749))

    def test_pystyle_auto_does_not_reclick_naki_disabled_while_override_waits(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_toggle_active_overrides={BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID: True},
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(
                    TenhouUiBridgeControl(control_id=2359814, visible=True, text="", label=""),
                ),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=False,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (1, 2, 3, 11, 12, 13, 21, 22, 23, 24, 25, 31, 32, 33)
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
            hand_key=request_tiles,
            round_token="east1-0",
        )
        display_context = PystyleDisplayContext(round_token="east1-0")

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                (),
                (),
            )

        start_action.assert_called_once()
        self.assertEqual(start_action.call_args.kwargs["attempt_key"][:2], ("auto_riichi", 2359814))

    def test_pystyle_auto_clicks_riichi_before_discard_when_visible(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_toggle_active_overrides={},
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(
                    TenhouUiBridgeControl(control_id=2359814, visible=True, text="", label=""),
                ),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (1, 2, 3, 11, 12, 13, 21, 22, 23, 24, 25, 31, 32, 33)
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
            hand_key=request_tiles,
            round_token="east1-0",
        )
        display_context = PystyleDisplayContext(round_token="east1-0")

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                (),
                (),
            )

        start_action.assert_called_once()
        self.assertEqual(start_action.call_args.kwargs["current_mode"], HAND_AUTO_MODE_KIND_RECOMMENDATION)
        self.assertEqual(start_action.call_args.kwargs["attempt_key"][:2], ("auto_riichi", 2359814))
        self.assertEqual(start_action.call_args.kwargs["tile_text"], "リーチ")

    def test_pystyle_auto_clicks_riichi_even_before_recommendation_arrives(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_toggle_active_overrides={},
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(
                    TenhouUiBridgeControl(control_id=2359814, visible=True, text="", label=""),
                ),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=False,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=False,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (1, 2, 3, 11, 12, 13, 21, 22, 23, 24, 25, 31, 32, 33)
        panel = HandRecommendationPanelData(
            items=(),
            hand_key=request_tiles,
            round_token="east1-0",
            status_text="計算中...",
            is_loading=True,
        )
        display_context = PystyleDisplayContext(round_token="east1-0")

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                (),
                (),
            )

        start_action.assert_called_once()
        self.assertEqual(start_action.call_args.kwargs["attempt_key"][:2], ("auto_riichi", 2359814))
        self.assertEqual(start_action.call_args.kwargs["tile_text"], "リーチ")

    def test_pystyle_auto_caps_timeout_fallback_delay_to_point_one_seconds(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_toggle_active_overrides={},
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (1, 2, 3, 11, 12, 13, 21, 22, 23, 24, 25, 31, 32, 33)
        panel = HandRecommendationPanelData(
            items=(),
            hand_key=request_tiles,
            round_token="east1-0",
        )
        display_context = PystyleDisplayContext(round_token="east1-0")
        hand_danger_percentages = tuple(
            {1: {"percentage": float(index + 1) * 5.0}, 2: {"percentage": 0}, 3: {"percentage": 0}}
            for index, _tile in enumerate(request_tiles)
        )

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                hand_danger_percentages,
                (),
                recommendation_timeout_elapsed=True,
        )

        start_action.assert_called_once()
        self.assertEqual(start_action.call_args.kwargs["delay_s"], HAND_PYSTYLE_TIMEOUT_FALLBACK_DELAY_S)

    def test_pystyle_auto_adds_extra_delay_when_current_response_is_usable(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_toggle_active_overrides={},
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (31, 11, 21)
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
            hand_key=request_tiles,
            round_token="east1-0",
            request_context_key=(3, "frontend_fallback", None, 27, 27, (), (), (), "east1-0"),
        )
        display_context = PystyleDisplayContext(round_token="east1-0")

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                (
                    {1: {"percentage": 40}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                    {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                    {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
                ),
                (),
            )

        start_action.assert_called_once()
        self.assertEqual(
            start_action.call_args.kwargs["delay_s"],
            HAND_PYSTYLE_AUTO_THINK_DELAY_S + HAND_PYSTYLE_RESPONSE_EXTRA_THINK_DELAY_S,
        )

    def test_pystyle_auto_uses_honor_fallback_when_request_times_out(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_toggle_active_overrides={},
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (31, 11, 32, 21)
        panel = HandRecommendationPanelData(
            items=(),
            hand_key=request_tiles,
            round_token="east1-0",
        )
        display_context = PystyleDisplayContext(round_token="east1-0")
        hand_danger_percentages = (
            {1: {"percentage": 40}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            {1: {"percentage": 15}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
        )

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                hand_danger_percentages,
                (),
                recommendation_timeout_elapsed=True,
            )

        start_action.assert_called_once()
        self.assertEqual(
            start_action.call_args.kwargs["attempt_key"][0],
            "pystyle_shanten_honor_discard",
        )
        self.assertEqual(start_action.call_args.kwargs["tile_37"], 32)

    def test_pystyle_auto_uses_recommendation_candidate_when_panel_has_recommendation(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_toggle_active_overrides={},
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (31, 11, 21)
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
            hand_key=request_tiles,
            round_token="east1-0",
            request_context_key=_hand_recommendation_request_context_key(
                PystyleDisplayContext(
                    round_token="east1-0",
                    turn_index=3,
                    turn_source="remaining_wall_formula",
                    wall_tiles_remaining=27,
                    round_wind=27,
                    seat_wind=27,
                )
            ),
        )
        display_context = PystyleDisplayContext(
            round_token="east1-0",
            turn_index=3,
            turn_source="remaining_wall_formula",
            wall_tiles_remaining=27,
            round_wind=27,
            seat_wind=27,
        )
        hand_danger_percentages = (
            {1: {"percentage": 40}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
        )

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                hand_danger_percentages,
                (),
                recommendation_timeout_elapsed=False,
            )

        start_action.assert_called_once()
        self.assertEqual(
            start_action.call_args.kwargs["attempt_key"][0],
            "auto_discard",
        )
        self.assertEqual(start_action.call_args.kwargs["tile_37"], 11)

    def test_pystyle_auto_uses_betaori_candidate_when_error_fallback_has_no_honor(self) -> None:
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
            bridge_toggle_active_overrides={},
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(),
                toggle_controls=(
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_AUTO_AGARI_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                    TenhouUiBridgeToggleControl(
                        control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                        available=True,
                        active=True,
                        text="",
                        label="",
                    ),
                ),
            ),
            bridge_click_control_action=lambda control_id: {"ok": True, "control_id": control_id},
            hand_auto_discard_action=lambda tile_37: {"ok": True, "tile_37": tile_37},
            hand_bridge_discard_by_index_action=None,
        )
        request_tiles = (1, 11, 21)
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_37=1,
                    tile_text="2m",
                    expected_value=1234.0,
                    expected_value_text="1234pt",
                ),
            ),
            hand_key=request_tiles,
            round_token="east1-0",
        )
        display_context = PystyleDisplayContext(round_token="east1-0")
        hand_danger_percentages = (
            {1: {"percentage": 55}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            {1: {"percentage": 10}, 2: {"percentage": 0}, 3: {"percentage": 0}},
            {1: {"percentage": 25}, 2: {"percentage": 0}, 3: {"percentage": 0}},
        )

        with patch("ui.table_renderer._start_hand_auto_mode_action", return_value=True) as start_action:
            _maybe_start_hand_auto_discard(
                canvas,
                request_tiles,
                panel,
                display_context,
                hand_danger_percentages,
                (),
                recommendation_error_fallback_active=True,
            )

        start_action.assert_called_once()
        self.assertEqual(
            start_action.call_args.kwargs["attempt_key"][0],
            "pystyle_shanten_betaori",
        )
        self.assertEqual(start_action.call_args.kwargs["tile_37"], 11)

    def test_pystyle_late_riichi_guard_prefers_riichi_over_discard(self) -> None:
        discard_calls: list[int] = []
        control_calls: list[int] = []
        canvas = SimpleNamespace(
            bridge_status_provider=lambda: TenhouUiBridgeStatus(
                ws_url="ws://127.0.0.1:8765",
                visible_controls=(
                    TenhouUiBridgeControl(control_id=2359814, visible=True, text="", label=""),
                ),
            ),
            bridge_click_control_action=lambda control_id: control_calls.append(control_id) or {
                "ok": True,
                "control_id": control_id,
            },
        )

        action = _build_pystyle_auto_discard_action_with_riichi_guard(
            canvas,
            lambda tile_37: discard_calls.append(tile_37) or {"ok": True, "tile_37": tile_37},
            allow_riichi=True,
        )
        result = action(11)

        self.assertEqual(discard_calls, [])
        self.assertEqual(control_calls, [2359814])
        self.assertEqual(result, {"ok": True, "control_id": 2359814})

    def test_reset_hand_auto_mode_volatile_state_resets_recommendation_service(self) -> None:
        reset_calls: list[str] = []
        canvas = SimpleNamespace(
            hand_auto_mode_state=HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
                in_flight=True,
                last_attempt_key=("auto_discard", "old"),
                last_error="timeout",
            ),
            hand_response_requested_hand_key=("same-hand",),
            hand_response_last_request_started_monotonic_s=12.5,
            hand_response_turn_started_monotonic_s=10.0,
            hand_response_turn_display_key=("turn", "east1-0", (31, 11, 32, 21)),
            hand_response_timeout_fallback_applied_turn_key=("turn", "east1-0", (31, 11, 32, 21)),
            hand_recommendation_reset_action=lambda: reset_calls.append("reset"),
        )

        _reset_hand_auto_mode_volatile_state(canvas)

        self.assertEqual(reset_calls, ["reset"])
        self.assertEqual(
            canvas.hand_auto_mode_state,
            HandAutoModeState(
                enabled=True,
                mode=HAND_AUTO_MODE_KIND_RECOMMENDATION,
            ),
        )
        self.assertIsNone(canvas.hand_response_requested_hand_key)
        self.assertIsNone(canvas.hand_response_last_request_started_monotonic_s)
        self.assertIsNone(canvas.hand_response_turn_started_monotonic_s)
        self.assertIsNone(canvas.hand_response_turn_display_key)
        self.assertIsNone(canvas.hand_response_timeout_fallback_applied_turn_key)

    def test_timeout_restart_resets_and_reissues_pystyle_request(self) -> None:
        reset_calls: list[str] = []
        request_calls: list[tuple[tuple[int, ...], PystyleDisplayContext | None]] = []
        canvas = SimpleNamespace(
            hand_recommendation_reset_action=lambda: reset_calls.append("reset"),
            hand_recommendation_request_action=lambda hand_tiles, display_context=None: request_calls.append(
                (tuple(int(tile) for tile in hand_tiles), display_context)
            ),
            hand_response_requested_hand_key=("old",),
            hand_response_last_request_started_monotonic_s=5.0,
            hand_response_turn_started_monotonic_s=3.5,
            hand_response_turn_display_key=("request", "east1-0", (31, 11, 32, 21)),
            hand_response_timeout_fallback_applied_turn_key=None,
        )
        request_tiles = (31, 11, 32, 21)
        display_context = PystyleDisplayContext(round_token="east1-0")
        current_request_key = ("request", "east1-0", request_tiles)

        restarted = _restart_hand_recommendation_request_after_timeout(
            canvas,
            request_tiles,
            display_context,
            current_request_key,
            auto_mode_enabled=True,
            recommendation_timeout_elapsed=True,
        )

        self.assertTrue(restarted)
        self.assertEqual(reset_calls, ["reset"])
        self.assertEqual(request_calls, [(request_tiles, display_context)])
        self.assertEqual(canvas.hand_response_requested_hand_key, current_request_key)
        self.assertIsInstance(canvas.hand_response_last_request_started_monotonic_s, float)
        self.assertGreater(canvas.hand_response_last_request_started_monotonic_s, 5.0)
        self.assertEqual(canvas.hand_response_turn_started_monotonic_s, 3.5)
        self.assertEqual(canvas.hand_response_turn_display_key, current_request_key)
        self.assertEqual(canvas.hand_response_timeout_fallback_applied_turn_key, current_request_key)

    def test_timeout_restart_skips_when_timeout_not_elapsed(self) -> None:
        reset_calls: list[str] = []
        request_calls: list[tuple[tuple[int, ...], PystyleDisplayContext | None]] = []
        canvas = SimpleNamespace(
            hand_recommendation_reset_action=lambda: reset_calls.append("reset"),
            hand_recommendation_request_action=lambda hand_tiles, display_context=None: request_calls.append(
                (tuple(int(tile) for tile in hand_tiles), display_context)
            ),
            hand_response_requested_hand_key=("old",),
            hand_response_last_request_started_monotonic_s=5.0,
            hand_response_turn_started_monotonic_s=3.5,
            hand_response_turn_display_key=("request", "east1-0", (31, 11, 32, 21)),
            hand_response_timeout_fallback_applied_turn_key=None,
        )
        request_tiles = (31, 11, 32, 21)
        display_context = PystyleDisplayContext(round_token="east1-0")
        current_request_key = ("request", "east1-0", request_tiles)

        restarted = _restart_hand_recommendation_request_after_timeout(
            canvas,
            request_tiles,
            display_context,
            current_request_key,
            auto_mode_enabled=True,
            recommendation_timeout_elapsed=False,
        )

        self.assertFalse(restarted)
        self.assertEqual(reset_calls, [])
        self.assertEqual(request_calls, [])

    def test_error_restart_resets_and_reissues_pystyle_request(self) -> None:
        reset_calls: list[str] = []
        request_calls: list[tuple[tuple[int, ...], PystyleDisplayContext | None]] = []
        canvas = SimpleNamespace(
            hand_recommendation_reset_action=lambda: reset_calls.append("reset"),
            hand_recommendation_request_action=lambda hand_tiles, display_context=None: request_calls.append(
                (tuple(int(tile) for tile in hand_tiles), display_context)
            ),
            hand_response_requested_hand_key=("old",),
            hand_response_last_request_started_monotonic_s=5.0,
            hand_response_turn_started_monotonic_s=3.5,
            hand_response_turn_display_key=("request", "east1-0", (31, 11, 32, 21)),
            hand_response_timeout_fallback_applied_turn_key=None,
        )
        request_tiles = (31, 11, 32, 21)
        display_context = PystyleDisplayContext(round_token="east1-0")
        current_request_key = ("request", "east1-0", request_tiles)

        restarted = _restart_hand_recommendation_request_after_error(
            canvas,
            request_tiles,
            display_context,
            current_request_key,
            auto_mode_enabled=True,
            recommendation_error_fallback_active=True,
        )

        self.assertTrue(restarted)
        self.assertEqual(reset_calls, ["reset"])
        self.assertEqual(request_calls, [(request_tiles, display_context)])
        self.assertEqual(canvas.hand_response_requested_hand_key, current_request_key)
        self.assertIsInstance(canvas.hand_response_last_request_started_monotonic_s, float)
        self.assertEqual(canvas.hand_response_turn_started_monotonic_s, 3.5)
        self.assertEqual(canvas.hand_response_turn_display_key, current_request_key)
        self.assertIsNone(canvas.hand_response_timeout_fallback_applied_turn_key)

    def test_error_restart_skips_when_error_fallback_not_active(self) -> None:
        reset_calls: list[str] = []
        request_calls: list[tuple[tuple[int, ...], PystyleDisplayContext | None]] = []
        canvas = SimpleNamespace(
            hand_recommendation_reset_action=lambda: reset_calls.append("reset"),
            hand_recommendation_request_action=lambda hand_tiles, display_context=None: request_calls.append(
                (tuple(int(tile) for tile in hand_tiles), display_context)
            ),
            hand_response_requested_hand_key=("old",),
            hand_response_last_request_started_monotonic_s=5.0,
            hand_response_turn_started_monotonic_s=3.5,
            hand_response_turn_display_key=("request", "east1-0", (31, 11, 32, 21)),
            hand_response_timeout_fallback_applied_turn_key=None,
        )
        request_tiles = (31, 11, 32, 21)
        display_context = PystyleDisplayContext(round_token="east1-0")
        current_request_key = ("request", "east1-0", request_tiles)

        restarted = _restart_hand_recommendation_request_after_error(
            canvas,
            request_tiles,
            display_context,
            current_request_key,
            auto_mode_enabled=True,
            recommendation_error_fallback_active=False,
        )

        self.assertFalse(restarted)
        self.assertEqual(reset_calls, [])
        self.assertEqual(request_calls, [])


if __name__ == "__main__":
    unittest.main()
