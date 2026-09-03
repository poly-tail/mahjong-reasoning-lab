import math
import pickle
import unittest
from dataclasses import asdict, astuple, fields, replace
from inspect import signature
from types import SimpleNamespace
from unittest.mock import patch

from capture.state import Discard, RoundState
import logic.danger_suji as danger_suji


EXPECTED_SUJI_LINE_KEYS = tuple(
    (suit_index, left_number, right_number)
    for suit_index in range(3)
    for left_number, right_number in (
        (1, 4),
        (4, 7),
        (2, 5),
        (5, 8),
        (3, 6),
        (6, 9),
    )
)


class SujiLineTableTest(unittest.TestCase):
    def test_empty_round_has_stable_eighteen_row_schema_and_legacy_order(self) -> None:
        round_state = RoundState()

        table = danger_suji._build_suji_line_table(round_state, 1)

        self.assertEqual(danger_suji.SUJI_LINE_KEYS, EXPECTED_SUJI_LINE_KEYS)
        self.assertEqual(
            danger_suji.SUJI_LINE_INDEX_BY_KEY,
            {line_key: line_id for line_id, line_key in enumerate(EXPECTED_SUJI_LINE_KEYS)},
        )
        self.assertEqual(len(table.rows), 18)
        self.assertEqual(table.raw_denominator_count, 18)
        self.assertEqual(
            table.raw_tile_numerator_counts_34,
            (1, 1, 1, 2, 2, 2, 1, 1, 1) * 3 + (0,) * 7,
        )
        self.assertEqual(
            tuple(
                (
                    row.line_id,
                    row.suit_index,
                    row.left_number,
                    row.right_number,
                    row.left_tile_34,
                    row.right_tile_34,
                    row.raw_count,
                    row.matagi_assignment_count,
                    row.matagi_visible_factor,
                    row.chi_factor,
                    row.inside_to_outside_factor,
                    row.urasuji_factor,
                    row.low_remain_long_think_factor,
                    row.lag_factor,
                    row.base_weight,
                    row.concentration_factor,
                    row.concentrated_weight,
                )
                for row in table.rows
            ),
            tuple(
                (
                    line_id,
                    suit_index,
                    left_number,
                    right_number,
                    suit_index * 9 + left_number - 1,
                    suit_index * 9 + right_number - 1,
                    1,
                    None,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    0.9,
                    0.9,
                )
                for line_id, (suit_index, left_number, right_number) in enumerate(
                    EXPECTED_SUJI_LINE_KEYS
                )
            ),
        )

        legacy_map = table.to_legacy_map()
        self.assertEqual(tuple(legacy_map), EXPECTED_SUJI_LINE_KEYS)
        self.assertEqual(tuple(legacy_map.values()), (1.0,) * 18)

        profile = danger_suji.build_opponent_suji_danger_profile(round_state, 1)
        self.assertEqual(
            profile.line_weights,
            tuple((*line_key, 1.0) for line_key in sorted(EXPECTED_SUJI_LINE_KEYS)),
        )

    def test_named_factor_columns_preserve_the_exact_weight_product(self) -> None:
        target_line = (0, 3, 6)
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=16,
                tile_34=4,
                tsumogiri=False,
                round_discard_index=0,
            )
        )
        matagi_assignment_count = 0.5
        matagi_visible_factor = 0.8
        chi_factor = 0.6
        inside_to_outside_factor = 0.7
        urasuji_factor = 0.75
        low_remain_long_think_factor = 0.65
        lag_factor = 1.4
        concentration_factor = 1.3

        danger_suji._build_concentrated_suji_projection.cache_clear()
        self.addCleanup(danger_suji._build_concentrated_suji_projection.cache_clear)
        with (
            patch.object(
                danger_suji,
                "_matagi_assignment_and_visible_factor",
                return_value=(matagi_assignment_count, matagi_visible_factor),
            ),
            patch.object(
                danger_suji,
                "_chi_line_factors",
                return_value={target_line: chi_factor},
            ),
            patch.object(
                danger_suji,
                "_inside_to_outside_line_factors",
                return_value={target_line: inside_to_outside_factor},
            ),
            patch.object(
                danger_suji,
                "_latest_tedashi_urasuji_ryanmen_line_factors",
                return_value={target_line: urasuji_factor},
            ),
            patch.object(
                danger_suji,
                "_low_remain_long_thinking_tsumogiri_line_factors",
                return_value={target_line: low_remain_long_think_factor},
            ),
            patch.object(
                danger_suji,
                "_lag_neighbor_line_factors",
                return_value={target_line: lag_factor},
            ),
            patch.object(
                danger_suji,
                "_musuji_concentration_factor_for_line",
                return_value=concentration_factor,
            ),
        ):
            table = danger_suji._build_suji_line_table(round_state, 1)

        row = next(row for row in table.rows if row.line_key == target_line)
        self.assertEqual(row.line_id, 4)
        self.assertEqual(row.raw_count, 1)
        self.assertEqual(row.matagi_assignment_count, matagi_assignment_count)
        self.assertEqual(row.matagi_visible_factor, matagi_visible_factor)
        self.assertEqual(row.chi_factor, chi_factor)
        self.assertEqual(row.inside_to_outside_factor, inside_to_outside_factor)
        self.assertEqual(row.urasuji_factor, urasuji_factor)
        self.assertEqual(row.low_remain_long_think_factor, low_remain_long_think_factor)
        self.assertEqual(row.lag_factor, lag_factor)
        expected_base_weight = math.prod(
            (
                row.raw_count,
                matagi_assignment_count,
                matagi_visible_factor,
                chi_factor,
                inside_to_outside_factor,
                urasuji_factor,
                low_remain_long_think_factor,
                lag_factor,
            )
        )
        self.assertAlmostEqual(row.base_weight, expected_base_weight)
        self.assertEqual(row.concentration_factor, concentration_factor)
        self.assertAlmostEqual(
            row.concentrated_weight,
            expected_base_weight * concentration_factor,
        )

    def test_concentration_is_computed_once_per_line_and_preaggregated_per_tile(self) -> None:
        round_state = RoundState()
        visible_counts_34 = tuple(tile_34 % 4 for tile_34 in range(34))
        original_helper = danger_suji._musuji_concentration_factor_for_line
        danger_suji._build_concentrated_suji_projection.cache_clear()
        self.addCleanup(danger_suji._build_concentrated_suji_projection.cache_clear)

        with patch.object(
            danger_suji,
            "_musuji_concentration_factor_for_line",
            wraps=original_helper,
        ) as concentration_helper:
            table = danger_suji._build_suji_line_table(
                round_state,
                1,
                visible_counts_34=visible_counts_34,
            )
            profile = danger_suji.build_opponent_suji_danger_profile(
                round_state,
                1,
                visible_counts_34=visible_counts_34,
            )
            self.assertEqual(concentration_helper.call_count, 18)

            self.assertAlmostEqual(
                table.base_denominator_count,
                sum(row.base_weight for row in table.rows),
            )
            self.assertAlmostEqual(
                table.concentrated_denominator_count,
                sum(row.concentrated_weight for row in table.rows),
            )
            self.assertEqual(len(table.base_tile_numerator_counts_34), 34)
            self.assertEqual(len(table.concentrated_tile_numerator_counts_34), 34)
            self.assertEqual(table.raw_denominator_count, sum(row.raw_count for row in table.rows))
            for tile_34 in range(34):
                expected_raw_numerator = sum(
                    row.raw_count
                    for row in table.rows
                    if tile_34 in (row.left_tile_34, row.right_tile_34)
                )
                expected_base_numerator = sum(
                    row.base_weight
                    for row in table.rows
                    if tile_34 in (row.left_tile_34, row.right_tile_34)
                )
                expected_concentrated_numerator = sum(
                    row.concentrated_weight
                    for row in table.rows
                    if tile_34 in (row.left_tile_34, row.right_tile_34)
                )
                self.assertAlmostEqual(
                    table.base_tile_numerator_counts_34[tile_34],
                    expected_base_numerator,
                )
                self.assertEqual(
                    table.raw_tile_numerator_counts_34[tile_34],
                    expected_raw_numerator,
                )
                self.assertAlmostEqual(
                    table.concentrated_tile_numerator_counts_34[tile_34],
                    expected_concentrated_numerator,
                )

                concentration_applies = (
                    expected_base_numerator / table.base_denominator_count * 100.0
                    > danger_suji.MUSUJI_CONCENTRATION_TRIGGER_PERCENT
                )
                self.assertAlmostEqual(
                    danger_suji._tile_numerator_count(profile, tile_34),
                    (
                        expected_concentrated_numerator
                        if concentration_applies
                        else expected_base_numerator
                    ),
                )
                self.assertAlmostEqual(
                    danger_suji._tile_denominator_count(profile, tile_34),
                    (
                        table.concentrated_denominator_count
                        if concentration_applies
                        else table.base_denominator_count
                    ),
                )

            self.assertEqual(concentration_helper.call_count, 18)

    def test_public_profile_shape_and_legacy_constructor_keep_the_same_tile_results(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            (
                Discard(tile_136=16, tile_34=4, round_discard_index=0),
                Discard(tile_136=8, tile_34=2, round_discard_index=1),
            )
        )
        visible_counts_34 = tuple(tile_34 % 5 for tile_34 in range(34))
        profile = danger_suji.build_opponent_suji_danger_profile(
            round_state,
            1,
            visible_counts_34=visible_counts_34,
        )
        legacy_profile = danger_suji.OpponentSujiDangerProfile(
            profile.seat,
            profile.tile_weights_34,
            profile.corrected_musuji_count,
            profile.safe_tile34,
            profile.line_weights,
            profile.visible_counts_34,
            profile.ugly_wait_add_percent_34,
        )

        expected_field_names = (
            "seat",
            "tile_weights_34",
            "corrected_musuji_count",
            "safe_tile34",
            "line_weights",
            "visible_counts_34",
            "ugly_wait_add_percent_34",
        )
        self.assertEqual(
            tuple(field.name for field in fields(danger_suji.OpponentSujiDangerProfile)),
            expected_field_names,
        )
        self.assertEqual(tuple(asdict(legacy_profile)), expected_field_names)
        self.assertEqual(len(astuple(legacy_profile)), len(expected_field_names))
        self.assertEqual(tuple(vars(legacy_profile)), expected_field_names)
        self.assertNotIn("_line_table", vars(legacy_profile))
        self.assertEqual(pickle.loads(pickle.dumps(legacy_profile)), legacy_profile)
        self.assertEqual(
            tuple(signature(danger_suji.build_latest_discard_push_alert_percentages).parameters),
            (
                "round_state",
                "visible_counts_34",
                "threshold_percent",
                "riichi_target_threshold_percent",
                "max_target_remain_count",
            ),
        )
        self.assertEqual(
            danger_suji._build_concentrated_suji_projection.cache_parameters()["maxsize"],
            512,
        )
        for tile_34 in range(34):
            self.assertEqual(
                danger_suji._tile_numerator_count(profile, tile_34),
                danger_suji._tile_numerator_count(legacy_profile, tile_34),
            )
            self.assertEqual(
                danger_suji._tile_denominator_count(profile, tile_34),
                danger_suji._tile_denominator_count(legacy_profile, tile_34),
            )
            self.assertEqual(
                danger_suji._tile_total_percent(profile, tile_34),
                danger_suji._tile_total_percent(legacy_profile, tile_34),
            )

    def test_exact_ten_percent_uses_base_projection_and_safe_tile_short_circuits(self) -> None:
        positive_line_keys = tuple(sorted(EXPECTED_SUJI_LINE_KEYS))[:10]
        line_weights = tuple(
            (*line_key, 1.0 if line_key in positive_line_keys else 0.0)
            for line_key in sorted(EXPECTED_SUJI_LINE_KEYS)
        )
        tile_weights_34 = (1.0,) + (0.0,) * 33
        profile = danger_suji.OpponentSujiDangerProfile(
            seat=1,
            tile_weights_34=tile_weights_34,
            corrected_musuji_count=10.0,
            safe_tile34=frozenset(),
            line_weights=line_weights,
            visible_counts_34=(0,) * 34,
            ugly_wait_add_percent_34=(0.0,) * 34,
        )

        self.assertEqual(danger_suji._tile_base_weight_percent_value(profile, 0), 10.0)
        self.assertEqual(danger_suji._tile_numerator_count(profile, 0), 1.0)
        self.assertEqual(danger_suji._tile_denominator_count(profile, 0), 10.0)
        self.assertEqual(
            danger_suji._tile_adjusted_line_weight_items(profile, 0),
            danger_suji._profile_line_weight_items(profile),
        )

        safe_profile = replace(profile, safe_tile34=frozenset({0}))
        self.assertEqual(danger_suji._tile_numerator_count(safe_profile, 0), 0.0)
        self.assertEqual(danger_suji._tile_denominator_count(safe_profile, 0), 10.0)
        self.assertEqual(danger_suji._tile_total_percent(safe_profile, 0), 0.0)

    def test_historical_push_builds_only_actor_profiles_and_reuses_cached_result(self) -> None:
        round_state = RoundState()
        for discard_index, actor_seat in enumerate((1, 2, 1, 3)):
            tile_34 = discard_index + 1
            round_state.discards[actor_seat].append(
                Discard(
                    tile_136=tile_34 * 4,
                    tile_34=tile_34,
                    tsumogiri=True,
                    round_discard_index=discard_index,
                )
            )

        with (
            patch.object(
                danger_suji,
                "build_opponent_suji_danger_profile",
                return_value=SimpleNamespace(corrected_musuji_count=12.0),
            ) as profile_builder,
            patch.object(danger_suji, "_tile_total_percent", return_value=9.0),
        ):
            first_counts = danger_suji._historical_push_count_by_seat(round_state)
            self.assertEqual(profile_builder.call_count, 12)

            second_counts = danger_suji._historical_push_count_by_seat(round_state)

        self.assertEqual(first_counts, {3: 1, 2: 1, 1: 2})
        self.assertEqual(second_counts, first_counts)
        self.assertEqual(profile_builder.call_count, 12)


if __name__ == "__main__":
    unittest.main()
