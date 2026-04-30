import unittest

from capture.fragment_parser import ParsedTag, parse_n
from capture.meld_decoder import decode_meld
from capture.state import GameState


class PonDecodeTest(unittest.TestCase):
    def test_decode_pon_keeps_triplet_copies_in_canonical_order(self) -> None:
        cases = (
            {
                "label": "kamicha-7z-r1",
                "meld_code": 51275,
                "from_player": "kamicha",
                "tiles_136": [132, 133, 135],
                "called_tile_id": 133,
                "consumed_tile_ids": [132, 135],
            },
            {
                "label": "kamicha-7z-r0",
                "meld_code": 50731,
                "from_player": "kamicha",
                "tiles_136": [132, 134, 135],
                "called_tile_id": 132,
                "consumed_tile_ids": [134, 135],
            },
            {
                "label": "kamicha-2z-r0",
                "meld_code": 43083,
                "from_player": "kamicha",
                "tiles_136": [112, 113, 115],
                "called_tile_id": 112,
                "consumed_tile_ids": [113, 115],
            },
            {
                "label": "shimocha-6z",
                "meld_code": 45161,
                "from_player": "shimocha",
                "tiles_136": [116, 117, 118],
                "called_tile_id": 117,
                "consumed_tile_ids": [116, 118],
            },
            {
                "label": "toimen-7z",
                "meld_code": 51210,
                "from_player": "toimen",
                "tiles_136": [133, 134, 135],
                "called_tile_id": 134,
                "consumed_tile_ids": [133, 135],
            },
        )

        for case in cases:
            with self.subTest(case["label"]):
                meld = decode_meld(0, case["meld_code"])
                self.assertEqual(meld.meld_type, "pon")
                self.assertEqual(meld.from_player, case["from_player"])
                self.assertEqual(meld.tiles_136, case["tiles_136"])
                self.assertEqual(meld.called_tile_id, case["called_tile_id"])
                self.assertEqual(meld.consumed_tile_ids, case["consumed_tile_ids"])

    def test_parse_n_removes_both_self_tiles_for_kamicha_pon(self) -> None:
        state = GameState()
        round_state = state.begin_round()
        round_state.current_hands_136[0] = [61, 91, 23, 132, 54, 71, 135, 116, 117, 118, 51, 38, 113]
        round_state.last_draw_tiles_136[0] = 135

        event = parse_n(
            state,
            123.0,
            ParsedTag(
                tag_name="N",
                raw_tag='<N who="0" m="51275"/>',
                attrs={"who": "0", "m": "51275"},
                source_format="live",
            ),
        )

        self.assertEqual(event.event_type, "call")
        self.assertEqual(event.tile_136, 133)
        self.assertEqual(
            round_state.current_hands_136[0],
            [61, 91, 23, 54, 71, 116, 117, 118, 51, 38, 113],
        )
        self.assertIsNone(round_state.last_draw_tiles_136[0])
        self.assertEqual(state.live_hand_tiles_136, sorted(round_state.current_hands_136[0]))


if __name__ == "__main__":
    unittest.main()
