import unittest

from capture.state import Discard, Meld, RoundState
from logic.danger_suji import (
    HAND_PATTERN_ALERT_RED_LEVEL,
    HAND_PATTERN_ALERT_YELLOW_LEVEL,
    build_inner_to_outer_hand_pattern_alert_level,
    build_opponent_suji_panel_summary,
    build_ryanmen_chi_central_tedashi_alert,
    build_suit_bias_alert,
)
from ui.table_renderer import (
    _build_player_panel_alert_indicators_by_seat,
    _player_panel_alert_sound_priority,
)


class PlayerPatternAlertTest(unittest.TestCase):
    def test_hand_pattern_alert_turns_yellow_after_28_to_19_and_two_more_tedashi(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=4, tile_34=1, tsumogiri=False, round_discard_index=0),
                Discard(tile_136=0, tile_34=0, tsumogiri=False, round_discard_index=1),
                Discard(tile_136=12, tile_34=3, tsumogiri=False, round_discard_index=2),
                Discard(tile_136=24, tile_34=6, tsumogiri=False, round_discard_index=3),
            ]
        )

        self.assertEqual(
            build_inner_to_outer_hand_pattern_alert_level(round_state, 1),
            HAND_PATTERN_ALERT_YELLOW_LEVEL,
        )
        self.assertEqual(
            build_opponent_suji_panel_summary(round_state, 1).hand_pattern_alert_level,
            HAND_PATTERN_ALERT_YELLOW_LEVEL,
        )

    def test_hand_pattern_alert_turns_red_after_37_to_outer_and_two_more_tedashi(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=16, tile_34=4, tsumogiri=False, round_discard_index=0),
                Discard(tile_136=0, tile_34=0, tsumogiri=False, round_discard_index=1),
                Discard(tile_136=12, tile_34=3, tsumogiri=False, round_discard_index=2),
                Discard(tile_136=24, tile_34=6, tsumogiri=False, round_discard_index=3),
            ]
        )

        self.assertEqual(
            build_inner_to_outer_hand_pattern_alert_level(round_state, 1),
            HAND_PATTERN_ALERT_RED_LEVEL,
        )
        self.assertEqual(
            build_opponent_suji_panel_summary(round_state, 1).hand_pattern_alert_level,
            HAND_PATTERN_ALERT_RED_LEVEL,
        )

    def test_player_panel_hand_pattern_alert_uses_red_and_yellow_keys(self) -> None:
        yellow_indicators = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 12.0,
                    "hand_pattern_alert_level": HAND_PATTERN_ALERT_YELLOW_LEVEL,
                }
            },
            {},
        )
        red_indicators = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 12.0,
                    "hand_pattern_alert_level": HAND_PATTERN_ALERT_RED_LEVEL,
                }
            },
            {},
        )

        self.assertEqual(
            tuple(indicator.key for indicator in yellow_indicators[1]),
            ("hand_pattern_yellow",),
        )
        self.assertEqual(
            tuple(indicator.key for indicator in red_indicators[1]),
            ("hand_pattern_red",),
        )

    def test_suit_bias_alert_triggers_when_removed_line_gap_reaches_threshold(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=0, tile_34=0, tsumogiri=False, round_discard_index=0),
                Discard(tile_136=4, tile_34=1, tsumogiri=False, round_discard_index=1),
                Discard(tile_136=8, tile_34=2, tsumogiri=False, round_discard_index=2),
                Discard(tile_136=12, tile_34=3, tsumogiri=False, round_discard_index=3),
            ]
        )

        self.assertTrue(build_suit_bias_alert(round_state, 1))
        self.assertTrue(build_opponent_suji_panel_summary(round_state, 1).suit_bias_alert)

    def test_suit_bias_alert_stays_off_when_removed_lines_are_balanced(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=0, tile_34=0, tsumogiri=False, round_discard_index=0),
                Discard(tile_136=40, tile_34=10, tsumogiri=False, round_discard_index=1),
                Discard(tile_136=80, tile_34=20, tsumogiri=False, round_discard_index=2),
            ]
        )

        self.assertFalse(build_suit_bias_alert(round_state, 1))
        self.assertFalse(build_opponent_suji_panel_summary(round_state, 1).suit_bias_alert)

    def test_player_panel_suit_bias_alert_uses_yellow_key_and_sound_priority(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 12.0,
                    "suit_bias_alert": True,
                }
            },
            {},
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("suit_bias",),
        )
        self.assertEqual(
            tuple(indicator.label for indicator in indicators_by_seat[1]),
            ("染/対々 UP",),
        )
        self.assertEqual(_player_panel_alert_sound_priority("hand_pattern_red"), 2)
        self.assertEqual(_player_panel_alert_sound_priority("hand_pattern_yellow"), 1)
        self.assertEqual(_player_panel_alert_sound_priority("suit_bias"), 1)

    def test_ryanmen_chi_central_tedashi_alert_triggers_after_call_tedashi(self) -> None:
        round_state = RoundState()
        round_state.melds[1].append(
            Meld(
                who=1,
                raw_m=0,
                meld_type="chi",
                from_who=3,
                is_open=True,
                tiles_136=[12, 16, 20],
                called_tile_id=12,
                called_index=0,
                event_index=10,
            )
        )
        round_state.discards[1].append(
            Discard(
                tile_136=24,
                tile_34=6,
                tsumogiri=False,
                thinking_time_source="call",
                round_discard_index=0,
                event_index=11,
            )
        )

        self.assertTrue(build_ryanmen_chi_central_tedashi_alert(round_state, 1))
        self.assertTrue(
            build_opponent_suji_panel_summary(round_state, 1).ryanmen_chi_central_tedashi_alert
        )

    def test_ryanmen_chi_central_tedashi_alert_requires_3_to_7_tedashi(self) -> None:
        round_state = RoundState()
        round_state.melds[1].append(
            Meld(
                who=1,
                raw_m=0,
                meld_type="chi",
                from_who=3,
                is_open=True,
                tiles_136=[12, 16, 20],
                called_tile_id=12,
                called_index=0,
                event_index=10,
            )
        )
        round_state.discards[1].append(
            Discard(
                tile_136=0,
                tile_34=0,
                tsumogiri=False,
                thinking_time_source="call",
                round_discard_index=0,
                event_index=11,
            )
        )

        self.assertFalse(build_ryanmen_chi_central_tedashi_alert(round_state, 1))

    def test_player_panel_ryanmen_chi_alert_uses_yellow_key_and_sound_priority(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 12.0,
                    "ryanmen_chi_central_tedashi_alert": True,
                }
            },
            {},
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("ryanmen_chi_37",),
        )
        self.assertEqual(_player_panel_alert_sound_priority("ryanmen_chi_37"), 1)


if __name__ == "__main__":
    unittest.main()
