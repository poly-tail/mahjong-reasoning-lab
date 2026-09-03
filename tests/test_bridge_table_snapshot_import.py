import copy
import unittest

import app.main as app_main
from capture.fragment_parser import parse_fragment
from capture.state import CaptureState, Discard as CaptureDiscard, build_round_id
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

    def test_repeat_import_updates_metadata_without_replacing_existing_round(self) -> None:
        state = CaptureState()
        first_snapshot = _sample_table_snapshot()
        second_snapshot = copy.deepcopy(first_snapshot)
        second_snapshot["riverEntriesBySeat"][0].append(
            {"tile34Index": 2, "tsumogiri": False, "riichiMarkerBefore": False}
        )

        app_main._import_tenhou_ui_bridge_table_snapshot(state, first_snapshot)
        first_identity = app_main.build_live_round_identity(state)

        summary = app_main._import_tenhou_ui_bridge_table_snapshot(state, second_snapshot)
        second_identity = app_main.build_live_round_identity(state)

        self.assertIsNotNone(first_identity)
        self.assertIsNotNone(second_identity)
        self.assertEqual(summary["importMode"], "metadata_only")
        self.assertEqual(first_identity, second_identity)
        self.assertEqual(first_identity[1], 1)
        self.assertEqual(second_identity[1], 1)
        self.assertEqual(summary["browserProjectionDiscardCountBySeat"][0], 3)

    def test_same_round_shorter_snapshot_keeps_packet_captured_river(self) -> None:
        state = CaptureState()
        state.game_id = "game-123"
        first_snapshot = _sample_table_snapshot()
        shorter_snapshot = copy.deepcopy(first_snapshot)
        shorter_snapshot["riverEntriesBySeat"][0] = shorter_snapshot["riverEntriesBySeat"][0][:1]
        shorter_snapshot["riverEntriesBySeat"][1] = []

        app_main._import_tenhou_ui_bridge_table_snapshot(state, first_snapshot)
        first_identity = app_main.build_live_round_identity(state)
        first_self_discards = list(state.current_round.discards[0])
        first_shimo_discards = list(state.current_round.discards[1])

        summary = app_main._import_tenhou_ui_bridge_table_snapshot(state, shorter_snapshot)

        self.assertEqual(summary["mappedDiscardCountBySeat"][0], 2)
        self.assertEqual(summary["mappedDiscardCountBySeat"][1], 1)
        self.assertEqual(app_main.build_live_round_identity(state)[0], first_identity[0])
        self.assertEqual(
            [discard.tile_136 for discard in state.current_round.discards[0]],
            [discard.tile_136 for discard in first_self_discards],
        )
        self.assertEqual(
            [discard.tile_136 for discard in state.current_round.discards[1]],
            [discard.tile_136 for discard in first_shimo_discards],
        )
        self.assertEqual(len(state.tracker.discards[Player.JICHA]), 2)
        self.assertEqual(len(state.tracker.discards[Player.SHIMOCHA]), 1)

    def test_shorter_bridge_snapshot_ignores_called_discards_when_matching_prefix(self) -> None:
        state = CaptureState()
        previous_round = state.begin_round(started_from_init_like=False)
        state.game_id = "game-123"
        previous_round.kyoku_index = 4
        previous_round.honba = 1
        previous_round.kyotaku = 2
        previous_round.oya = 1
        previous_round.round_id = build_round_id("game-123", 4, 1, 2, 1)
        previous_round.discards[0].append(CaptureDiscard(tile_136=0, called=True))
        previous_round.discards[0].append(CaptureDiscard(tile_136=4))
        state.tracker.add_discard(Player.JICHA, 1, called=True)
        state.tracker.add_discard(Player.JICHA, 2)
        snapshot = copy.deepcopy(_sample_table_snapshot())
        snapshot["riverEntriesBySeat"] = [
            [{"tile34Index": 1, "tsumogiri": False, "riichiMarkerBefore": False}],
            [],
            [],
            [],
        ]

        summary = app_main._import_tenhou_ui_bridge_table_snapshot(state, snapshot)

        self.assertEqual(summary["mappedDiscardCountBySeat"][0], 2)
        self.assertEqual(
            [discard.tile_136 for discard in state.current_round.discards[0]],
            [0, 4],
        )
        self.assertTrue(state.current_round.discards[0][0].called)
        self.assertEqual(len(state.tracker.discards[Player.JICHA]), 2)

    def test_bridge_snapshot_import_keeps_existing_discards_and_stores_projection(self) -> None:
        state = CaptureState()
        state.game_id = "game-123"
        previous_round = state.begin_round(started_from_init_like=False)
        previous_round.kyoku_index = 4
        previous_round.honba = 1
        previous_round.kyotaku = 2
        previous_round.oya = 1
        previous_round.round_id = build_round_id("game-123", 4, 1, 2, 1)
        called_head = CaptureDiscard(tile_136=0, called=True)
        previous_visible = CaptureDiscard(tile_136=4)
        previous_round.discards[0].extend([called_head, previous_visible])
        snapshot = copy.deepcopy(_sample_table_snapshot())
        snapshot["riverEntriesBySeat"] = [
            [
                {"tile34Index": 1, "tsumogiri": False, "riichiMarkerBefore": False},
                {"tile34Index": 2, "tsumogiri": False, "riichiMarkerBefore": False},
            ],
            [],
            [],
            [],
        ]

        summary = app_main._import_tenhou_ui_bridge_table_snapshot(state, snapshot)

        self.assertEqual(summary["importMode"], "metadata_only")
        self.assertEqual(summary["mappedDiscardCountBySeat"][0], 2)
        self.assertEqual(summary["browserProjectionDiscardCountBySeat"][0], 2)
        merged_discards = state.current_round.discards[0]
        self.assertEqual([discard.tile_136 // 4 for discard in merged_discards], [0, 1])
        self.assertIs(merged_discards[0], called_head)
        self.assertTrue(merged_discards[0].called)
        self.assertIs(merged_discards[1], previous_visible)
        self.assertEqual(
            len(state.current_round.browser_visible_river_projection[0]),
            2,
        )
        self.assertEqual(len(state.tracker.discards[Player.JICHA]), 0)

    def test_bridge_snapshot_import_does_not_infer_called_gap_on_existing_round(self) -> None:
        state = CaptureState()
        state.game_id = "game-123"
        previous_round = state.begin_round(started_from_init_like=False)
        previous_round.kyoku_index = 4
        previous_round.honba = 1
        previous_round.kyotaku = 2
        previous_round.oya = 1
        previous_round.round_id = build_round_id("game-123", 4, 1, 2, 1)
        omitted_head = CaptureDiscard(tile_136=0)
        previous_visible = CaptureDiscard(tile_136=4)
        previous_round.discards[0].extend([omitted_head, previous_visible])
        snapshot = copy.deepcopy(_sample_table_snapshot())
        snapshot["riverEntriesBySeat"] = [
            [
                {"tile34Index": 1, "tsumogiri": False, "riichiMarkerBefore": False},
                {"tile34Index": 2, "tsumogiri": False, "riichiMarkerBefore": False},
            ],
            [],
            [],
            [],
        ]

        summary = app_main._import_tenhou_ui_bridge_table_snapshot(state, snapshot)

        self.assertEqual(summary["importMode"], "metadata_only")
        self.assertEqual(summary["mappedDiscardCountBySeat"][0], 2)
        merged_discards = state.current_round.discards[0]
        self.assertEqual([discard.tile_136 // 4 for discard in merged_discards], [0, 1])
        self.assertIs(merged_discards[0], omitted_head)
        self.assertFalse(merged_discards[0].called)
        self.assertIs(merged_discards[1], previous_visible)
        self.assertEqual(len(state.current_round.browser_visible_river_projection[0]), 2)

    def test_bridge_snapshot_import_does_not_append_visible_tail_to_existing_round(self) -> None:
        state = CaptureState()
        state.game_id = "game-123"
        previous_round = state.begin_round(started_from_init_like=False)
        previous_round.kyoku_index = 4
        previous_round.honba = 1
        previous_round.kyotaku = 2
        previous_round.oya = 1
        previous_round.round_id = build_round_id("game-123", 4, 1, 2, 1)
        omitted_head = CaptureDiscard(tile_136=0)
        previous_round.discards[0].append(omitted_head)
        snapshot = copy.deepcopy(_sample_table_snapshot())
        snapshot["riverEntriesBySeat"] = [
            [{"tile34Index": 1, "tsumogiri": False, "riichiMarkerBefore": False}],
            [],
            [],
            [],
        ]

        summary = app_main._import_tenhou_ui_bridge_table_snapshot(state, snapshot)

        self.assertEqual(summary["importMode"], "metadata_only")
        self.assertEqual(summary["mappedDiscardCountBySeat"][0], 1)
        merged_discards = state.current_round.discards[0]
        self.assertEqual([discard.tile_136 // 4 for discard in merged_discards], [0])
        self.assertIs(merged_discards[0], omitted_head)
        self.assertFalse(merged_discards[0].called)
        self.assertEqual(len(state.current_round.browser_visible_river_projection[0]), 1)
        self.assertEqual(len(state.tracker.discards[Player.JICHA]), 0)

    def test_bridge_snapshot_import_does_not_bootstrap_existing_discards_even_if_snapshot_differs(
        self,
    ) -> None:
        state = CaptureState()
        state.game_id = "game-123"
        previous_round = state.begin_round(started_from_init_like=False)
        previous_round.kyoku_index = 3
        previous_round.honba = 0
        previous_round.kyotaku = 0
        previous_round.oya = 0
        previous_round.round_id = build_round_id("game-123", 3, 0, 0, 0)
        previous_round.discards[0].append(CaptureDiscard(tile_136=0))
        snapshot = copy.deepcopy(_sample_table_snapshot())
        snapshot["kyokuIndex"] = 4

        summary = app_main._import_tenhou_ui_bridge_table_snapshot(state, snapshot)

        self.assertEqual(summary["importMode"], "metadata_only")
        self.assertIs(state.current_round, previous_round)
        self.assertEqual(state.current_round.kyoku_index, 4)
        self.assertEqual([discard.tile_136 for discard in previous_round.discards[0]], [0])
        self.assertEqual(summary["mappedDiscardCountTotal"], 1)
        self.assertEqual(summary["browserProjectionDiscardCountBySeat"], [2, 1, 1, 0])

    def test_live_packet_after_bridge_snapshot_extends_imported_round(self) -> None:
        state = CaptureState()
        state.game_id = "game-123"

        app_main._import_tenhou_ui_bridge_table_snapshot(state, _sample_table_snapshot())
        imported_snapshot = app_main.build_live_table_snapshot(state)

        parse_fragment(state, 10.0, "D56")
        updated_snapshot = app_main.build_live_table_snapshot(state)

        self.assertEqual(
            len(updated_snapshot.discard_map[Player.JICHA]),
            len(imported_snapshot.discard_map[Player.JICHA]) + 1,
        )
        self.assertEqual(updated_snapshot.discard_map[Player.JICHA][-1].tag, "D56")
        self.assertEqual(updated_snapshot.discard_map[Player.JICHA][-1].tile_id, 16)


if __name__ == "__main__":
    unittest.main()
