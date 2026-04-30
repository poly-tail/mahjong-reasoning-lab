import unittest
from types import SimpleNamespace

from sutehai import Discard, DrawType, Player
from ui.table_renderer import (
    _adjust_table_situation_score,
    _aggregate_table_situation_scores,
    _build_table_situation_auto_scores_by_seat,
    _empty_table_situation_scores,
    _format_table_situation_total_text,
    _normalize_table_situation_scores_by_seat,
    _round_half_away_from_zero,
    _resolve_table_situation_scores_by_seat,
    _set_table_situation_score,
    _table_situation_total,
    _table_situation_zero_suited_division,
)


class _DummyCanvas:
    def __init__(self) -> None:
        self.table_situation_scores_by_seat = {
            int(Player.KAMICHA): _empty_table_situation_scores(),
            int(Player.TOIMEN): _empty_table_situation_scores(),
            int(Player.SHIMOCHA): _empty_table_situation_scores(),
        }


class TableSituationScoreTest(unittest.TestCase):
    def test_normalize_table_situation_scores_by_seat_clamps_and_fills(self) -> None:
        normalized = _normalize_table_situation_scores_by_seat(
            {
                int(Player.KAMICHA): (3, -3, 1),
                int(Player.TOIMEN): ("2", "-1", None, 99),
            }
        )

        self.assertEqual(normalized[int(Player.KAMICHA)][:4], (3, -3, 1, 0))
        self.assertEqual(normalized[int(Player.TOIMEN)][:5], (2, -1, 0, 4, 0))
        self.assertEqual(normalized[int(Player.SHIMOCHA)], _empty_table_situation_scores())

    def test_adjust_table_situation_score_clamps_between_minus_four_and_plus_four(self) -> None:
        self.assertEqual(_adjust_table_situation_score(0, +1), 1)
        self.assertEqual(_adjust_table_situation_score(3, +1), 4)
        self.assertEqual(_adjust_table_situation_score(4, +1), 4)
        self.assertEqual(_adjust_table_situation_score(0, -1), -1)
        self.assertEqual(_adjust_table_situation_score(-3, -1), -4)
        self.assertEqual(_adjust_table_situation_score(-4, -1), -4)

    def test_set_table_situation_score_updates_one_block_only(self) -> None:
        canvas = _DummyCanvas()

        changed = _set_table_situation_score(canvas, int(Player.KAMICHA), 4, 2)

        self.assertTrue(changed)
        self.assertEqual(canvas.table_situation_scores_by_seat[int(Player.KAMICHA)][4], 2)
        self.assertEqual(canvas.table_situation_scores_by_seat[int(Player.TOIMEN)], _empty_table_situation_scores())

    def test_aggregate_table_situation_scores_keeps_fractional_average(self) -> None:
        aggregated = _aggregate_table_situation_scores(
            {
                int(Player.KAMICHA): (2, -2, 0, 0, 0, 0, 0, 0, 0, 1),
                int(Player.TOIMEN): (0, 0, 0, 0, 0, 0, 0, 0, 0, 1),
                int(Player.SHIMOCHA): (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            }
        )

        self.assertAlmostEqual(aggregated[0], 2 / 3, places=3)
        self.assertAlmostEqual(aggregated[1], -2 / 3, places=3)
        self.assertAlmostEqual(aggregated[9], 2 / 3, places=3)

    def test_round_half_away_from_zero_matches_manual_shishagonyu(self) -> None:
        self.assertEqual(_round_half_away_from_zero(0.49), 0)
        self.assertEqual(_round_half_away_from_zero(0.5), 1)
        self.assertEqual(_round_half_away_from_zero(-0.49), 0)
        self.assertEqual(_round_half_away_from_zero(-0.5), -1)

    def test_table_situation_total_sums_all_ten_blocks(self) -> None:
        self.assertEqual(
            _table_situation_total((2, 1, 0, -1, -2, 0, 1, 1, -1, 2)),
            3,
        )

    def test_format_table_situation_total_text_can_force_one_decimal(self) -> None:
        self.assertEqual(_format_table_situation_total_text(2 / 3, force_decimal=True), "+0.7")
        self.assertEqual(_format_table_situation_total_text(-2 / 3, force_decimal=True), "-0.7")
        self.assertEqual(_format_table_situation_total_text(0.0, force_decimal=True), "0.0")

    def test_build_table_situation_auto_scores_by_seat_uses_base_weights_before_first_red_tint(self) -> None:
        auto_scores = _build_table_situation_auto_scores_by_seat(
            {
                Player.KAMICHA: (
                    SimpleNamespace(tile_34=2, draw_type=DrawType.TEDASHI, thinking_time_ms=2500.0),
                    SimpleNamespace(tile_34=9, draw_type=DrawType.TEDASHI),
                ),
                Player.TOIMEN: (),
                Player.SHIMOCHA: (),
            },
            {
                int(Player.KAMICHA): {1},
            },
        )

        kamicha_scores = auto_scores[int(Player.KAMICHA)]
        self.assertAlmostEqual(kamicha_scores[0], -0.5, places=3)
        self.assertAlmostEqual(kamicha_scores[1], -(1.5 + 1.0) / 3.0, places=3)

    def test_build_table_situation_auto_scores_by_seat_strengthens_first_four_fast_tedashi(self) -> None:
        auto_scores = _build_table_situation_auto_scores_by_seat(
            {
                Player.KAMICHA: (
                    SimpleNamespace(tile_34=3, draw_type=DrawType.TEDASHI, thinking_time_ms=1800.0),
                    SimpleNamespace(tile_34=9, draw_type=DrawType.TEDASHI),
                ),
                Player.TOIMEN: (),
                Player.SHIMOCHA: (),
            },
            {
                int(Player.KAMICHA): {1},
            },
        )

        kamicha_scores = auto_scores[int(Player.KAMICHA)]
        self.assertAlmostEqual(kamicha_scores[0], -2.0 / 3.0, places=3)
        self.assertAlmostEqual(kamicha_scores[1], -(2.0 + 1.5) / 3.0, places=3)

    def test_build_table_situation_auto_scores_by_seat_adds_positive_red_tint_neighbor_scores(self) -> None:
        auto_scores = _build_table_situation_auto_scores_by_seat(
            {
                Player.KAMICHA: (
                    SimpleNamespace(tile_34=2, draw_type=DrawType.TEDASHI),
                ),
                Player.TOIMEN: (),
                Player.SHIMOCHA: (),
            },
            {
                int(Player.KAMICHA): {0},
            },
        )

        kamicha_scores = auto_scores[int(Player.KAMICHA)]
        self.assertAlmostEqual(kamicha_scores[0], 2.5 / 3.0, places=3)
        self.assertAlmostEqual(kamicha_scores[1], 2.5 / 3.0, places=3)

    def test_resolve_table_situation_scores_by_seat_adds_manual_and_auto_scores(self) -> None:
        resolved = _resolve_table_situation_scores_by_seat(
            {
                int(Player.KAMICHA): (1, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                int(Player.TOIMEN): _empty_table_situation_scores(),
                int(Player.SHIMOCHA): _empty_table_situation_scores(),
            },
            {
                int(Player.KAMICHA): (-0.5, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
                int(Player.TOIMEN): tuple(0.0 for _ in range(10)),
                int(Player.SHIMOCHA): tuple(0.0 for _ in range(10)),
            },
        )

        self.assertAlmostEqual(resolved[int(Player.KAMICHA)][0], 0.5, places=3)
        self.assertAlmostEqual(resolved[int(Player.KAMICHA)][1], -1.0, places=3)

    def test_table_situation_zero_suited_division_uses_zero_suited_cell_count(self) -> None:
        self.assertAlmostEqual(
            _table_situation_zero_suited_division(
                (-1.3, -1.3, -1.3, -1.3, -1.3, -1.3, 0.0, 0.0, 0.0, 0.0)
            ),
            -7.8 / 3.0,
            places=3,
        )


if __name__ == "__main__":
    unittest.main()
