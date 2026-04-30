import unittest

from capture.state import Discard, RoundState
from logic.danger_suji import (
    _build_weighted_suji_line_map,
    _latest_tedashi_non_genbutsu_suji_tile34_set,
    _latest_tedashi_suji_ugly_wait_add_percent,
    _representative_taatsu_drop_second_index,
    build_opponent_suji_danger_profile,
)


class DangerSujiHeuristicTest(unittest.TestCase):
    @staticmethod
    def _tedashi_discard(tile_136: int, round_discard_index: int) -> Discard:
        return Discard(
            tile_136=tile_136,
            tsumogiri=False,
            round_discard_index=round_discard_index,
        )

    def test_red_five_tedashi_weakens_both_matagi_lines_to_quarter(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=16,
                tsumogiri=False,
                round_discard_index=0,
            )
        )

        line_weights = _build_weighted_suji_line_map(round_state, 1)

        self.assertAlmostEqual(line_weights[(0, 3, 6)], 0.25)
        self.assertAlmostEqual(line_weights[(0, 4, 7)], 0.25)

    def test_non_red_five_keeps_full_matagi_count(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=17,
                tsumogiri=False,
                round_discard_index=0,
            )
        )

        line_weights = _build_weighted_suji_line_map(round_state, 1)

        self.assertAlmostEqual(line_weights[(0, 3, 6)], 1.0)
        self.assertAlmostEqual(line_weights[(0, 4, 7)], 1.0)

    def test_three_visible_discard_softens_matagi_to_eighty_percent(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=17,
                tsumogiri=False,
                round_discard_index=0,
            )
        )

        line_weights = _build_weighted_suji_line_map(
            round_state,
            1,
            visible_counts_34=tuple([0, 0, 0, 0, 3] + [0] * 29),
        )

        self.assertAlmostEqual(line_weights[(0, 3, 6)], 0.8)
        self.assertAlmostEqual(line_weights[(0, 4, 7)], 0.8)

    def test_four_visible_discard_zeroes_matagi_lines(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=17,
                tsumogiri=False,
                round_discard_index=0,
            )
        )

        line_weights = _build_weighted_suji_line_map(
            round_state,
            1,
            visible_counts_34=tuple([0, 0, 0, 0, 4] + [0] * 29),
        )

        self.assertAlmostEqual(line_weights[(0, 3, 6)], 0.0)
        self.assertAlmostEqual(line_weights[(0, 4, 7)], 0.0)

    def test_low_remain_long_thinking_tsumogiri_softens_two_away_suji(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=53,
                tile_34=13,
                tsumogiri=False,
                round_discard_index=0,
            )
        )
        round_state.discards[1].append(
            Discard(
                tile_136=0,
                tile_34=0,
                tsumogiri=True,
                thinking_time_ms=2500.0,
                round_discard_index=1,
            )
        )

        line_weights = _build_weighted_suji_line_map(round_state, 1)

        self.assertAlmostEqual(line_weights[(0, 3, 6)], 0.7)

    def test_long_thinking_tsumogiri_requires_remain_16_or_less(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=0,
                tile_34=0,
                tsumogiri=True,
                thinking_time_ms=4000.0,
                round_discard_index=0,
            )
        )

        line_weights = _build_weighted_suji_line_map(round_state, 1)

        self.assertAlmostEqual(line_weights[(0, 3, 6)], 1.0)

    def test_long_thinking_tsumogiri_requires_2500ms_or_more(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=53,
                tile_34=13,
                tsumogiri=False,
                round_discard_index=0,
            )
        )
        round_state.discards[1].append(
            Discard(
                tile_136=0,
                tile_34=0,
                tsumogiri=True,
                thinking_time_ms=2499.0,
                round_discard_index=1,
            )
        )

        line_weights = _build_weighted_suji_line_map(round_state, 1)

        self.assertAlmostEqual(line_weights[(0, 3, 6)], 1.0)

    def test_latest_tedashi_suji_no_longer_revives_suppressed_line_weight(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=0,
                tile_34=0,
                tsumogiri=False,
                round_discard_index=0,
            )
        )

        line_weights = _build_weighted_suji_line_map(round_state, 1)
        self.assertAlmostEqual(line_weights[(0, 1, 4)], 0.0)

    def test_latest_tedashi_non_genbutsu_suji_targets_follow_discard_side(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=8,
                tile_34=2,
                tsumogiri=False,
                round_discard_index=0,
            )
        )

        self.assertEqual(
            _latest_tedashi_non_genbutsu_suji_tile34_set(round_state, 1),
            frozenset({5}),
        )

    def test_latest_tedashi_suji_ugly_wait_add_has_two_percent_floor(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=8,
                tile_34=2,
                tsumogiri=False,
                round_discard_index=0,
            )
        )

        profile = build_opponent_suji_danger_profile(round_state, 1)

        self.assertAlmostEqual(
            _latest_tedashi_suji_ugly_wait_add_percent(profile.corrected_musuji_count),
            2.0,
        )

    def test_latest_tedashi_five_targets_both_non_genbutsu_suji_tiles_and_scales_with_remain(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=0, tile_34=0, tsumogiri=False, round_discard_index=0),
                Discard(tile_136=12, tile_34=3, tsumogiri=False, round_discard_index=1),
                Discard(tile_136=24, tile_34=6, tsumogiri=False, round_discard_index=2),
                Discard(tile_136=72, tile_34=18, tsumogiri=False, round_discard_index=3),
                Discard(tile_136=84, tile_34=21, tsumogiri=False, round_discard_index=4),
                Discard(tile_136=96, tile_34=24, tsumogiri=False, round_discard_index=5),
                Discard(tile_136=36, tile_34=9, tsumogiri=False, round_discard_index=6),
                Discard(tile_136=48, tile_34=12, tsumogiri=False, round_discard_index=7),
                Discard(tile_136=60, tile_34=15, tsumogiri=False, round_discard_index=8),
                Discard(tile_136=52, tile_34=13, tsumogiri=False, round_discard_index=9),
            ]
        )

        profile = build_opponent_suji_danger_profile(round_state, 1)
        self.assertEqual(
            _latest_tedashi_non_genbutsu_suji_tile34_set(round_state, 1),
            frozenset({10, 16}),
        )
        self.assertAlmostEqual(
            _latest_tedashi_suji_ugly_wait_add_percent(profile.corrected_musuji_count),
            max(2.0, 8.0 + (10.0 - profile.corrected_musuji_count) * 2.0),
        )

    def test_latest_tedashi_special_suji_targets_are_replaced_by_next_tedashi(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=8, tile_34=2, tsumogiri=False, round_discard_index=0),
                Discard(tile_136=16, tile_34=4, tsumogiri=False, round_discard_index=1),
            ]
        )

        self.assertEqual(
            _latest_tedashi_non_genbutsu_suji_tile34_set(round_state, 1),
            frozenset({1, 7}),
        )

    def test_latest_tedashi_special_suji_targets_clear_when_next_tedashi_is_honor(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=8, tile_34=2, tsumogiri=False, round_discard_index=0),
                Discard(tile_136=108, tile_34=27, tsumogiri=False, round_discard_index=1),
            ]
        )

        self.assertEqual(
            _latest_tedashi_non_genbutsu_suji_tile34_set(round_state, 1),
            frozenset(),
        )

    def test_taatsu_drop_with_two_away_consecutive_tedashi_softens_older_matagi_to_seventy_percent(self) -> None:
        self.assertEqual(
            _representative_taatsu_drop_second_index(
                [
                    self._tedashi_discard(17, 0),
                    self._tedashi_discard(8, 1),
                ]
            ),
            1,
        )

        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=17,
                tsumogiri=False,
                round_discard_index=0,
            )
        )
        round_state.discards[1].append(
            Discard(
                tile_136=8,
                tsumogiri=False,
                round_discard_index=1,
            )
        )

        line_weights = _build_weighted_suji_line_map(round_state, 1)

        self.assertGreater(line_weights[(0, 4, 7)], 0.5)

    def test_taatsu_drop_softening_does_not_apply_when_honor_tedashi_interrupts_pair(self) -> None:
        self.assertIsNone(
            _representative_taatsu_drop_second_index(
                [
                    self._tedashi_discard(17, 0),
                    self._tedashi_discard(108, 1),
                    self._tedashi_discard(8, 2),
                ]
            )
        )

        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=17,
                tsumogiri=False,
                round_discard_index=0,
            )
        )
        round_state.discards[1].append(
            Discard(
                tile_136=108,
                tsumogiri=False,
                round_discard_index=1,
            )
        )
        round_state.discards[1].append(
            Discard(
                tile_136=8,
                tsumogiri=False,
                round_discard_index=2,
            )
        )

        line_weights = _build_weighted_suji_line_map(round_state, 1)

        self.assertLess(line_weights[(0, 4, 7)], 0.3)

    def test_taatsu_drop_softening_does_not_apply_when_discards_are_three_or_more_apart(self) -> None:
        self.assertIsNone(
            _representative_taatsu_drop_second_index(
                [
                    self._tedashi_discard(17, 0),
                    self._tedashi_discard(8, 3),
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
