import copy
import unittest

import app.main as app_main
from capture.state import CaptureState
from sutehai import Player


def _sample_table_snapshot() -> dict[str, object]:
    return {
        "ok": True,
        "playerNames": ["self", "shimo", "toimen", "kami"],
        "scores": [25000, 24000, 26000, 25000],
        "kyokuIndex": 4,
        "honba": 1,
        "kyotaku": 2,
        "oya": 1,
        "doraIndicators136": [3],
        "handTiles136": [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52],
        "riverEntriesBySeat": [
            [
                {"tile34Index": 0, "tsumogiri": False, "riichiMarkerBefore": False},
                {"tile34Index": 1, "tsumogiri": True, "riichiMarkerBefore": False},
            ],
            [
                {"tile34Index": 27, "tsumogiri": False, "riichiMarkerBefore": True},
            ],
            [
                {"tile34Index": 4, "tsumogiri": False, "riichiMarkerBefore": False},
            ],
            [],
        ],
    }


class BridgeTableSnapshotImportTests(unittest.TestCase):
    def test_import_bootstraps_partial_live_round_from_browser_snapshot(self) -> None:
        state = CaptureState()
        state.game_id = "game-123"

        summary = app_main._import_tenhou_ui_bridge_table_snapshot(
            state,
            _sample_table_snapshot(),
        )

        self.assertEqual(summary["mappedHandTileCount"], 14)
        self.assertEqual(summary["mappedDiscardCountTotal"], 4)
        self.assertEqual(summary["mappedRiichiSeatCount"], 1)
        self.assertIsNotNone(state.current_round)
        self.assertTrue(state.current_round.started_from_init_like)
        self.assertTrue(state.current_round.snapshot_is_partial)
        self.assertEqual(state.current_round.snapshot_bootstrap_sequence, 1)
        self.assertEqual(state.current_round.round_id, "game-123:4:1:2:1")
        self.assertEqual(state.live_dora_indicator_tiles_136, [3])
        self.assertEqual(state.live_last_draw_tile_136, 52)
        self.assertEqual(len(state.tracker.discards[Player.JICHA]), 2)
        self.assertEqual(len(state.tracker.discards[Player.SHIMOCHA]), 1)
        self.assertTrue(state.current_round.discards[0][1].tsumogiri)
        self.assertEqual(state.current_round.reach_state[1], "accepted")
        discard_tile_ids = [
            discard.tile_136
            for seat in range(4)
            for discard in state.current_round.discards[seat]
        ]
        self.assertEqual(len(discard_tile_ids), len(set(discard_tile_ids)))
        self.assertIsNotNone(app_main.build_live_round_identity(state))

    def test_repeat_import_changes_live_round_identity(self) -> None:
        state = CaptureState()
        first_snapshot = _sample_table_snapshot()
        second_snapshot = copy.deepcopy(first_snapshot)
        second_snapshot["riverEntriesBySeat"][0].append(
            {"tile34Index": 2, "tsumogiri": False, "riichiMarkerBefore": False}
        )

        app_main._import_tenhou_ui_bridge_table_snapshot(state, first_snapshot)
        first_identity = app_main.build_live_round_identity(state)

        app_main._import_tenhou_ui_bridge_table_snapshot(state, second_snapshot)
        second_identity = app_main.build_live_round_identity(state)

        self.assertIsNotNone(first_identity)
        self.assertIsNotNone(second_identity)
        self.assertNotEqual(first_identity, second_identity)
        self.assertEqual(first_identity[1], 1)
        self.assertEqual(second_identity[1], 2)


if __name__ == "__main__":
    unittest.main()
