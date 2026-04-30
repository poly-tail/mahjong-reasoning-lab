import unittest
from unittest.mock import patch

from capture.state import Discard, RoundState
import logic.danger_suji as danger_suji
from logic.danger_suji import build_discard_red_tint_indices_by_seat
from ui.table_renderer import _normalize_discard_red_tint_indices_by_seat


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
        round_discard_index=discard_index,
        thinking_time_source=thinking_time_source,
    )


class DiscardRedTintHighlightTest(unittest.TestCase):
    def test_red_tint_tolerates_missing_discard_order_indices(self) -> None:
        round_state = RoundState()
        broken_discard = _discard(0, 0)
        broken_discard.round_discard_index = None
        broken_discard.event_index = None
        round_state.discards[1].append(broken_discard)

        highlighted = build_discard_red_tint_indices_by_seat(round_state)

        self.assertIn(1, highlighted)
        self.assertEqual(highlighted[1], ())

    def test_low_no_temp_remain_marks_all_later_tedashi_after_threshold(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                _discard(0, 0),
                _discard(9, 1),
                _discard(18, 2),
                _discard(8, 3),
                _discard(17, 4),
                _discard(26, 5),
                _discard(27, 6),
                _discard(4, 7, tsumogiri=True),
                _discard(28, 8),
            ]
        )

        highlighted = build_discard_red_tint_indices_by_seat(round_state)

        self.assertEqual(highlighted[1], (4, 5, 6, 8))
        self.assertEqual(highlighted[2], ())
        self.assertEqual(highlighted[3], ())

    def test_inner_to_outer_marks_all_later_tedashi_including_honors(self) -> None:
        round_state = RoundState()
        round_state.discards[2].extend(
            [
                _discard(4, 0),
                _discard(0, 1),
                _discard(27, 2),
                _discard(15, 3),
                _discard(19, 4),
                _discard(20, 5, tsumogiri=True),
            ]
        )

        highlighted = build_discard_red_tint_indices_by_seat(round_state)

        self.assertEqual(highlighted[2], (1, 2, 3, 4))

    def test_post_call_tedashi_marks_call_tedashi_and_later_tedashi(self) -> None:
        round_state = RoundState()
        round_state.discards[3].extend(
            [
                _discard(0, 0),
                _discard(27, 1, thinking_time_source="call"),
                _discard(4, 2, tsumogiri=True),
                _discard(28, 3),
            ]
        )

        highlighted = build_discard_red_tint_indices_by_seat(round_state)

        self.assertEqual(highlighted[3], (1, 3))

    def test_taatsu_drop_like_nearby_same_suit_tedashi_latches_red_tint(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                _discard(0, 0),
                _discard(2, 1),
                _discard(27, 2),
                _discard(3, 3, tsumogiri=True),
            ]
        )

        highlighted = build_discard_red_tint_indices_by_seat(round_state)

        self.assertEqual(highlighted[1], (1, 2))

    def test_red_tint_latch_stops_additional_no_temp_prefix_rebuilds(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                _discard(0, 0),
                _discard(9, 1),
                _discard(18, 2),
                _discard(8, 3),
                _discard(17, 4),
                _discard(26, 5),
                _discard(27, 6),
                _discard(4, 7, tsumogiri=True),
                _discard(28, 8),
            ]
        )

        with patch(
            "logic.danger_suji._round_state_prefix_until_discard_index",
            wraps=danger_suji._round_state_prefix_until_discard_index,
        ) as prefix_builder:
            first = build_discard_red_tint_indices_by_seat(round_state)
            first_call_count = prefix_builder.call_count
            second = build_discard_red_tint_indices_by_seat(round_state)

            round_state.discards[1].append(_discard(8, 9))
            third = build_discard_red_tint_indices_by_seat(round_state)

        self.assertGreater(first_call_count, 0)
        self.assertEqual(second, first)
        self.assertEqual(prefix_builder.call_count, first_call_count)
        self.assertEqual(third[1], (4, 5, 6, 8, 9))

    def test_renderer_normalization_filters_invalid_indices(self) -> None:
        normalized = _normalize_discard_red_tint_indices_by_seat(
            {
                0: [0, "2", -1, None],
                1: {1, 1, "bad"},
                "x": [5],
                9: [3],
            }
        )

        self.assertEqual(normalized[0], frozenset({0, 2}))
        self.assertEqual(normalized[1], frozenset({1}))
        self.assertEqual(normalized[2], frozenset())
        self.assertEqual(normalized[3], frozenset())


if __name__ == "__main__":
    unittest.main()
