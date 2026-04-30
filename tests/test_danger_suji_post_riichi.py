import unittest

from capture.state import Discard, RoundState
from logic.danger_suji import (
    _latest_tedashi_non_genbutsu_suji_tile34_set,
    estimate_tile_suji_danger_percent,
)


class PostRiichiSujiUpdateTest(unittest.TestCase):
    def test_latest_tedashi_special_suji_targets_ignore_post_riichi_discards(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=12, tile_34=3, tsumogiri=False, round_discard_index=0),
                Discard(
                    tile_136=36,
                    tile_34=9,
                    tsumogiri=False,
                    riichi_marker_before=True,
                    round_discard_index=1,
                ),
                # Snapshot drift can occasionally leave a post-riichi discard marked as tedashi.
                # The latest-tedashi special-suji heuristic must still stay anchored pre-riichi.
                Discard(tile_136=20, tile_34=5, tsumogiri=False, round_discard_index=2),
            ]
        )

        self.assertEqual(
            _latest_tedashi_non_genbutsu_suji_tile34_set(round_state, 1),
            frozenset({0, 6}),
        )

    def test_post_riichi_discard_suji_is_not_boosted_as_latest_tedashi_special(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(
                    tile_136=36,
                    tile_34=9,
                    tsumogiri=False,
                    riichi_marker_before=True,
                    round_discard_index=0,
                ),
                Discard(tile_136=20, tile_34=5, tsumogiri=False, round_discard_index=1),
            ]
        )

        self.assertLess(
            estimate_tile_suji_danger_percent(round_state, 1, 2),
            8.0,
        )


if __name__ == "__main__":
    unittest.main()
