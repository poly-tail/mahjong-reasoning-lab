import unittest

from capture.state import Discard, RoundState
from logic.danger_suji import (
    _build_weighted_suji_line_map,
    build_opponent_suji_panel_summary,
    estimate_tile_suji_danger_percent,
)


class CalledRiichiSafeTileTest(unittest.TestCase):
    def _build_round_state(self, *, called: bool) -> RoundState:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=108,
                tsumogiri=False,
                riichi_marker_before=True,
                round_discard_index=0,
            )
        )
        round_state.discards[0].append(
            Discard(
                tile_136=24,
                tsumogiri=False,
                called=called,
                round_discard_index=1,
            )
        )
        return round_state

    def test_called_post_riichi_genbutsu_stays_exact_safe(self) -> None:
        round_state = self._build_round_state(called=True)

        self.assertEqual(
            estimate_tile_suji_danger_percent(round_state, 1, 6),
            0.0,
        )

    def test_called_post_riichi_genbutsu_still_reduces_suji_lines(self) -> None:
        visible_round_state = self._build_round_state(called=False)
        called_round_state = self._build_round_state(called=True)

        visible_line_weights = _build_weighted_suji_line_map(visible_round_state, 1)
        called_line_weights = _build_weighted_suji_line_map(called_round_state, 1)

        self.assertEqual(
            visible_line_weights.get((0, 4, 7)),
            0.0,
        )
        self.assertEqual(
            called_line_weights.get((0, 4, 7)),
            0.0,
        )

        visible_summary = build_opponent_suji_panel_summary(visible_round_state, 1)
        called_summary = build_opponent_suji_panel_summary(called_round_state, 1)

        self.assertEqual(
            called_summary.denominator_count,
            visible_summary.denominator_count,
        )


if __name__ == "__main__":
    unittest.main()
