import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app.main as app_main
from capture.state import CaptureState, Discard, Meld, RoundState
from logic.danger_suji import (
    DEFAULT_TENPAI_PROBABILITY_PERCENT,
    build_hand_tile_suji_danger_metrics,
    build_opponent_tenpai_probability_percentages,
)


def _discard(
    tile_34: int,
    discard_index: int,
    *,
    tsumogiri: bool = False,
    thinking_time_source: str | None = None,
) -> Discard:
    return Discard(
        tile_136=tile_34 * 4,
        tile_34=tile_34,
        tsumogiri=tsumogiri,
        thinking_time_source=thinking_time_source,
        round_discard_index=discard_index,
    )


class OpponentTenpaiProbabilityTest(unittest.TestCase):
    def test_riichi_is_always_treated_as_100_percent_tenpai(self) -> None:
        round_state = RoundState()
        round_state.reach_state[1] = "accepted"

        probabilities = build_opponent_tenpai_probability_percentages(round_state)

        self.assertEqual(probabilities[1], 100.0)

    def test_two_open_melds_gain_tedashi_and_push_tenpai_probability(self) -> None:
        round_state = RoundState()
        round_state.melds[1].extend(
            [
                Meld(who=1, raw_m=0, meld_type="chi", is_open=True, event_index=0),
                Meld(who=1, raw_m=1, meld_type="pon", is_open=True, event_index=1),
            ]
        )
        round_state.discards[1].extend(
            [
                Discard(
                    tile_136=0,
                    tile_34=0,
                    tsumogiri=False,
                    thinking_time_source="call",
                    round_discard_index=0,
                ),
                Discard(
                    tile_136=4,
                    tile_34=1,
                    tsumogiri=False,
                    thinking_time_source="draw",
                    round_discard_index=1,
                ),
            ]
        )

        def fake_push_alerts(prefix_state: RoundState, **_kwargs: object) -> dict[int, object]:
            return {
                1: SimpleNamespace(
                    percentage=(9.0 if len(prefix_state.discards[1]) == 1 else 0.0)
                )
            }

        with patch(
            "logic.danger_suji.build_latest_discard_push_alert_percentages",
            side_effect=fake_push_alerts,
        ):
            probabilities = build_opponent_tenpai_probability_percentages(round_state)

        self.assertEqual(probabilities[1], 85.0)

    def test_menzen_push_starts_at_70_and_gains_15_each_time(self) -> None:
        round_state = RoundState()
        round_state.discards[2].extend(
            [
                Discard(
                    tile_136=0,
                    tile_34=0,
                    tsumogiri=False,
                    thinking_time_source="draw",
                    round_discard_index=0,
                ),
                Discard(
                    tile_136=4,
                    tile_34=1,
                    tsumogiri=False,
                    thinking_time_source="draw",
                    round_discard_index=1,
                ),
            ]
        )

        with patch(
            "logic.danger_suji.build_latest_discard_push_alert_percentages",
            return_value={2: SimpleNamespace(percentage=9.0)},
        ):
            probabilities = build_opponent_tenpai_probability_percentages(round_state)

        self.assertEqual(probabilities[2], 85.0)

    def test_no_signal_seat_defaults_to_20_percent_tenpai(self) -> None:
        round_state = RoundState()

        probabilities = build_opponent_tenpai_probability_percentages(round_state)

        self.assertEqual(probabilities[1], DEFAULT_TENPAI_PROBABILITY_PERCENT)
        self.assertEqual(probabilities[2], DEFAULT_TENPAI_PROBABILITY_PERCENT)
        self.assertEqual(probabilities[3], DEFAULT_TENPAI_PROBABILITY_PERCENT)

    def test_first_visible_red_tint_sets_35_percent_floor(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                _discard(0, 0),
                _discard(27, 1, thinking_time_source="call"),
            ]
        )

        probabilities = build_opponent_tenpai_probability_percentages(round_state)

        self.assertEqual(probabilities[1], 35.0)

    def test_each_additional_red_tint_tedashi_adds_5_percent_floor(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                _discard(0, 0),
                _discard(27, 1, thinking_time_source="call"),
                _discard(4, 2, tsumogiri=True),
                _discard(28, 3),
            ]
        )

        probabilities = build_opponent_tenpai_probability_percentages(round_state)

        self.assertEqual(probabilities[1], 40.0)

    def test_red_tint_floor_does_not_override_higher_open_hand_probability(self) -> None:
        round_state = RoundState()
        round_state.melds[1].append(Meld(who=1, raw_m=0, meld_type="chi", is_open=True, event_index=0))
        round_state.discards[1].append(_discard(27, 0, thinking_time_source="call"))

        probabilities = build_opponent_tenpai_probability_percentages(round_state)

        self.assertEqual(probabilities[1], 40.0)

    def test_hand_tile_danger_metrics_use_effective_tenpai_weighted_percentages(self) -> None:
        state = CaptureState()
        state.current_round = RoundState()

        with patch(
            "logic.danger_suji.build_opponent_tenpai_probability_percentages",
            return_value={1: 100.0, 2: 100.0, 3: 100.0},
        ):
            baseline_metrics = build_hand_tile_suji_danger_metrics(state, [0])[0]

        with patch(
            "logic.danger_suji.build_opponent_tenpai_probability_percentages",
            return_value={1: 50.0, 2: 100.0, 3: 0.0},
        ):
            weighted_metrics = build_hand_tile_suji_danger_metrics(state, [0])[0]

        self.assertGreater(baseline_metrics[1].percentage, 0)
        self.assertEqual(
            weighted_metrics[1].percentage,
            int(round(baseline_metrics[1].percentage * 0.5)),
        )
        self.assertAlmostEqual(
            weighted_metrics[1].numerator_count,
            baseline_metrics[1].numerator_count * 0.5,
        )
        self.assertEqual(weighted_metrics[2].percentage, baseline_metrics[2].percentage)
        self.assertEqual(weighted_metrics[3].percentage, 0)
        self.assertEqual(weighted_metrics[3].numerator_count, 0.0)

    def test_loading_panel_placeholder_uses_same_default_tenpai_probability(self) -> None:
        summaries = app_main._build_loading_opponent_suji_panel_summaries(None)

        self.assertEqual(
            summaries[1]["tenpai_probability"],
            DEFAULT_TENPAI_PROBABILITY_PERCENT,
        )
        self.assertEqual(
            summaries[2]["tenpai_probability"],
            DEFAULT_TENPAI_PROBABILITY_PERCENT,
        )
        self.assertEqual(
            summaries[3]["tenpai_probability"],
            DEFAULT_TENPAI_PROBABILITY_PERCENT,
        )


if __name__ == "__main__":
    unittest.main()
