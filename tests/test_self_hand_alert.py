import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ui.table_renderer import (
    HAND_SELF_ALERT_KIND_HIGH,
    HAND_SELF_ALERT_KIND_LOW,
    HAND_SELF_ALERT_KIND_NONE,
    HAND_SELF_ALERT_KIND_WARNING,
    HandRecommendationPanelData,
    SelfHandValueAlertState,
    _build_self_hand_value_alert_state,
    _dora_tile34_index_from_indicator_tile37,
    _format_visible_dora_tile_count_label,
    _play_self_hand_value_alert_sound_if_needed,
    _self_hand_visible_dora_alert_colors,
    _self_hand_visible_dora_alert_dot_color,
    _should_evaluate_alert_audio_for_refresh_token,
    _should_play_low_ev_self_hand_alert_sound_for_round,
    _should_play_self_hand_value_alert_sound,
    _visible_dora_tile_count,
)
from sutehai import Discard, DrawType, Player
from visible_tiles import VisibleTileSummary, collect_visible_tile_summary


class SelfHandAlertStateTest(unittest.TestCase):
    def test_dora_indicator_maps_to_wrapped_dora_tile_index(self) -> None:
        self.assertEqual(_dora_tile34_index_from_indicator_tile37(4), 4)
        self.assertEqual(_dora_tile34_index_from_indicator_tile37(10), 5)
        self.assertEqual(_dora_tile34_index_from_indicator_tile37(9), 0)
        self.assertEqual(_dora_tile34_index_from_indicator_tile37(34), 27)
        self.assertEqual(_dora_tile34_index_from_indicator_tile37(35), 32)
        self.assertEqual(_dora_tile34_index_from_indicator_tile37(36), 33)
        self.assertEqual(_dora_tile34_index_from_indicator_tile37(37), 31)

    def test_visible_dora_tile_count_uses_distinct_dora_kinds(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=tuple(
                3 if tile_34 == 4 else 2 if tile_34 == 27 else 0
                for tile_34 in range(34)
            ),
        )

        self.assertEqual(_visible_dora_tile_count([4, 9, 34, 34], visible_summary), 5)
        self.assertEqual(_format_visible_dora_tile_count_label(5), "ドラ５")
        self.assertEqual(_format_visible_dora_tile_count_label(12), "ドラ１２")

    def test_visible_dora_count_alert_colors_follow_thresholds(self) -> None:
        self.assertEqual(
            _self_hand_visible_dora_alert_colors(0),
            ("#2a1618", "#8b1e27", "#fecaca"),
        )
        self.assertEqual(
            _self_hand_visible_dora_alert_colors(1),
            ("#2a2416", "#b58f1b", "#fde68a"),
        )
        self.assertEqual(
            _self_hand_visible_dora_alert_colors(2),
            ("#171f2b", "#3b4c63", "#8ea0b6"),
        )
        self.assertEqual(
            _self_hand_visible_dora_alert_colors(3),
            ("#16281e", "#23814a", "#bbf7d0"),
        )

    def test_visible_dora_count_alert_dot_follows_alert_color_states(self) -> None:
        self.assertEqual(_self_hand_visible_dora_alert_dot_color(0), "#dc2626")
        self.assertEqual(_self_hand_visible_dora_alert_dot_color(1), "#facc15")
        self.assertIsNone(_self_hand_visible_dora_alert_dot_color(2))
        self.assertEqual(_self_hand_visible_dora_alert_dot_color(3), "#22c55e")

    def test_visible_dora_tile_count_adds_visible_red_dora_count(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=tuple(
                3 if tile_34 == 4 else 2 if tile_34 == 27 else 0
                for tile_34 in range(34)
            ),
            visible_red_dora_count=2,
        )

        self.assertEqual(_visible_dora_tile_count([4, 9, 34, 34], visible_summary), 7)

    def test_visible_dora_tile_count_treats_three_visible_honor_dora_as_four(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=tuple(
                3 if tile_34 == 27 else 0
                for tile_34 in range(34)
            ),
        )

        self.assertEqual(_visible_dora_tile_count([34], visible_summary), 4)

    def test_visible_tile_summary_tracks_red_dora_count(self) -> None:
        discard_map = {player: [] for player in Player}
        discard_map[Player.JICHA].append(
            Discard(
                tile_id=10,
                draw_type=DrawType.TEDASHI,
            )
        )

        visible_summary = collect_visible_tile_summary(
            discard_map=discard_map,
            hand_tiles=[20],
            meld_tiles=[30],
            dora_indicator_tiles=[10],
        )

        self.assertEqual(visible_summary.visible_red_dora_count, 4)

    def test_open_hand_red_alert_uses_adjusted_value_only_for_threshold(self) -> None:
        panel = HandRecommendationPanelData(
            top_expected_value=700.0,
            hand_key=(11, 12, 13),
            round_token="east-1",
        )

        state = _build_self_hand_value_alert_state(
            panel,
            [11, 12, 13],
            "east-1",
            [SimpleNamespace(is_open=True)],
        )

        self.assertTrue(state.active)
        self.assertEqual(state.kind, HAND_SELF_ALERT_KIND_LOW)
        self.assertEqual(state.round_token, "east-1")
        self.assertEqual(state.label, "LOW EV")
        self.assertEqual(state.raw_top_expected_value, 700.0)
        self.assertEqual(state.adjusted_top_expected_value, 560.0)

    def test_self_alert_accepts_reordered_equivalent_hand_key(self) -> None:
        panel = HandRecommendationPanelData(
            top_expected_value=700.0,
            hand_key=(13, 11, 12),
            round_token="east-1",
        )

        state = _build_self_hand_value_alert_state(
            panel,
            [11, 12, 13],
            "east-1",
            [SimpleNamespace(is_open=True)],
        )

        self.assertTrue(state.active)
        self.assertEqual(state.kind, HAND_SELF_ALERT_KIND_LOW)

    def test_open_hand_yellow_alert_uses_raw_pystyle_threshold_800(self) -> None:
        panel = HandRecommendationPanelData(
            top_expected_value=750.0,
            hand_key=(21, 22, 23),
            round_token="east-2",
        )

        state = _build_self_hand_value_alert_state(
            panel,
            [21, 22, 23],
            "east-2",
            [SimpleNamespace(is_open=True)],
        )

        self.assertTrue(state.active)
        self.assertEqual(state.kind, HAND_SELF_ALERT_KIND_WARNING)
        self.assertEqual(state.label, "EV<800")
        self.assertEqual(state.raw_top_expected_value, 750.0)
        self.assertEqual(state.adjusted_top_expected_value, 600.0)

    def test_high_ev_alert_uses_raw_pystyle_threshold_3000(self) -> None:
        panel = HandRecommendationPanelData(
            top_expected_value=3000.0,
            hand_key=(24, 25, 26),
            round_token="east-2",
        )

        state = _build_self_hand_value_alert_state(
            panel,
            [24, 25, 26],
            "east-2",
            [],
        )

        self.assertTrue(state.active)
        self.assertEqual(state.kind, HAND_SELF_ALERT_KIND_HIGH)
        self.assertEqual(state.label, "HIGH EV")
        self.assertEqual(state.raw_top_expected_value, 3000.0)
        self.assertEqual(state.adjusted_top_expected_value, 3000.0)

    def test_alert_stays_inactive_when_snapshot_is_not_current(self) -> None:
        panel = HandRecommendationPanelData(
            top_expected_value=500.0,
            hand_key=(31, 32, 33),
            round_token="east-3",
        )

        state = _build_self_hand_value_alert_state(
            panel,
            [31, 32, 33],
            "east-4",
            [SimpleNamespace(is_open=True)],
        )

        self.assertFalse(state.active)
        self.assertEqual(state.kind, HAND_SELF_ALERT_KIND_NONE)
        self.assertIsNone(state.raw_top_expected_value)
        self.assertIsNone(state.adjusted_top_expected_value)

    def test_alert_accepts_live_round_identity_with_bootstrap_wrapper(self) -> None:
        panel = HandRecommendationPanelData(
            top_expected_value=3000.0,
            hand_key=(24, 25, 26),
            round_token="east-2",
        )

        state = _build_self_hand_value_alert_state(
            panel,
            [24, 25, 26],
            ("east-2", 7),
            [],
        )

        self.assertTrue(state.active)
        self.assertEqual(state.kind, HAND_SELF_ALERT_KIND_HIGH)
        self.assertEqual(state.label, "HIGH EV")

    def test_sound_only_fires_when_alert_kind_changes_into_active(self) -> None:
        self.assertTrue(
            _should_play_self_hand_value_alert_sound(
                HAND_SELF_ALERT_KIND_NONE,
                HAND_SELF_ALERT_KIND_WARNING,
            )
        )
        self.assertFalse(
            _should_play_self_hand_value_alert_sound(
                HAND_SELF_ALERT_KIND_LOW,
                HAND_SELF_ALERT_KIND_HIGH,
            )
        )
        self.assertFalse(
            _should_play_self_hand_value_alert_sound(
                HAND_SELF_ALERT_KIND_NONE,
                HAND_SELF_ALERT_KIND_HIGH,
            )
        )
        self.assertFalse(
            _should_play_self_hand_value_alert_sound(
                HAND_SELF_ALERT_KIND_WARNING,
                HAND_SELF_ALERT_KIND_WARNING,
            )
        )
        self.assertFalse(
            _should_play_self_hand_value_alert_sound(
                HAND_SELF_ALERT_KIND_HIGH,
                HAND_SELF_ALERT_KIND_NONE,
            )
        )

    def test_low_ev_sound_is_limited_to_once_per_round(self) -> None:
        self.assertTrue(
            _should_play_low_ev_self_hand_alert_sound_for_round(
                HAND_SELF_ALERT_KIND_LOW,
                "east-1",
                "",
            )
        )
        self.assertFalse(
            _should_play_low_ev_self_hand_alert_sound_for_round(
                HAND_SELF_ALERT_KIND_LOW,
                "east-1",
                "east-1",
            )
        )
        self.assertTrue(
            _should_play_low_ev_self_hand_alert_sound_for_round(
                HAND_SELF_ALERT_KIND_LOW,
                "east-2",
                "east-1",
            )
        )
        self.assertTrue(
            _should_play_low_ev_self_hand_alert_sound_for_round(
                HAND_SELF_ALERT_KIND_WARNING,
                "east-1",
                "east-1",
            )
        )

    def test_alert_audio_evaluates_only_once_per_refresh_token(self) -> None:
        canvas = SimpleNamespace()

        self.assertTrue(
            _should_evaluate_alert_audio_for_refresh_token(canvas, ("capture", 1))
        )
        self.assertFalse(
            _should_evaluate_alert_audio_for_refresh_token(canvas, ("capture", 1))
        )
        self.assertTrue(
            _should_evaluate_alert_audio_for_refresh_token(canvas, ("capture", 2))
        )

    def test_self_alert_sound_rate_limits_rapid_retriggers(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_self_hand_value_alert_kind = HAND_SELF_ALERT_KIND_NONE
                self.last_self_low_ev_sound_round_token = ""
                self.last_self_hand_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()

        with patch("ui.table_renderer.winsound", None), patch(
            "ui.table_renderer.time.monotonic",
            side_effect=[100.0, 100.3],
        ):
            _play_self_hand_value_alert_sound_if_needed(
                canvas,
                SelfHandValueAlertState(kind=HAND_SELF_ALERT_KIND_WARNING),
            )
            _play_self_hand_value_alert_sound_if_needed(
                canvas,
                SelfHandValueAlertState(kind=HAND_SELF_ALERT_KIND_NONE),
            )
            _play_self_hand_value_alert_sound_if_needed(
                canvas,
                SelfHandValueAlertState(kind=HAND_SELF_ALERT_KIND_WARNING),
            )

        self.assertEqual(canvas.bell_calls, 1)

    def test_self_alert_sound_can_fire_again_after_cooldown(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_self_hand_value_alert_kind = HAND_SELF_ALERT_KIND_NONE
                self.last_self_low_ev_sound_round_token = ""
                self.last_self_hand_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()

        with patch("ui.table_renderer.winsound", None), patch(
            "ui.table_renderer.time.monotonic",
            side_effect=[100.0, 101.2],
        ):
            _play_self_hand_value_alert_sound_if_needed(
                canvas,
                SelfHandValueAlertState(kind=HAND_SELF_ALERT_KIND_WARNING),
            )
            _play_self_hand_value_alert_sound_if_needed(
                canvas,
                SelfHandValueAlertState(kind=HAND_SELF_ALERT_KIND_NONE),
            )
            _play_self_hand_value_alert_sound_if_needed(
                canvas,
                SelfHandValueAlertState(kind=HAND_SELF_ALERT_KIND_WARNING),
            )

        self.assertEqual(canvas.bell_calls, 2)


if __name__ == "__main__":
    unittest.main()
