import unittest

from app.main import build_live_round_identity, build_live_table_snapshot
from capture.fragment_parser import _sync_live_state, parse_fragment
from capture.state import CaptureState, Discard, Meld, RoundState
from sutehai import Player
from ui.table_renderer import _round_discard_cache_identity


class LiveReinitBootstrapTest(unittest.TestCase):
    def test_reinit_bootstraps_live_snapshot_without_go(self) -> None:
        state = CaptureState()

        event = parse_fragment(
            state,
            1.0,
            (
                '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
                '"hai":"2,17,27,29,39,44,48,51,64,68,109,134,135",'
                '"kawa0":"117","kawa1":"119","kawa2":"38","kawa3":"32,36"}'
            ),
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "reinit")
        self.assertIsNotNone(state.current_round)
        self.assertTrue(state.current_round.started_from_init_like)
        self.assertEqual(state.current_round.snapshot_bootstrap_sequence, 1)
        self.assertGreater(len(state.live_hand_tiles_136), 0)
        self.assertEqual(state.live_dora_indicator_tiles_136, [3])
        self.assertIsNotNone(build_live_round_identity(state))

    def test_live_reset_keeps_go_room_class_metadata_without_erasing_discards(self) -> None:
        state = CaptureState()
        state.parser_mode = "player_live"
        state.current_round = RoundState(started_from_init_like=True)
        state.current_round.discards[0].append(Discard(tile_136=0))
        for seat, name in enumerate(("old0", "old1", "old2", "old3")):
            state.players_rel[seat].name = name
        state.refresh_player_views()
        state.seat_mapping_resolved = True

        parse_fragment(state, 1.0, '{"tag":"GO","type":"169"}')
        event = parse_fragment(
            state,
            2.0,
            '{"tag":"UN","n0":"new0","n1":"new1","n2":"new2","n3":"new3"}',
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "un")
        self.assertEqual(state.go_type, 169)
        self.assertEqual(state.room_class_label, "鳳凰卓")
        self.assertIsNotNone(state.current_round)
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[0]], [0])

    def test_reinit_keeps_live_round_identity_for_same_logical_round(self) -> None:
        state = CaptureState()
        first_fragment = (
            '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
            '"hai":"2,17,27,29,39,44,48,51,64,68,109,134,135",'
            '"kawa0":"117","kawa1":"119","kawa2":"38","kawa3":"32,36"}'
        )
        second_fragment = (
            '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
            '"hai":"2,17,27,29,39,44,48,51,64,68,109,134,135",'
            '"kawa0":"117,120","kawa1":"119","kawa2":"38","kawa3":"32,36"}'
        )

        parse_fragment(state, 1.0, first_fragment)
        first_identity = build_live_round_identity(state)

        parse_fragment(state, 2.0, second_fragment)
        second_identity = build_live_round_identity(state)

        self.assertIsNotNone(first_identity)
        self.assertIsNotNone(second_identity)
        self.assertEqual(first_identity, second_identity)
        self.assertEqual(first_identity[0], "river_epoch")
        self.assertEqual(first_identity[1], 1)

    def test_live_tracker_discard_keeps_round_and_event_indices(self) -> None:
        state = CaptureState()
        parse_fragment(
            state,
            1.0,
            (
                '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
                '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
                '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
            ),
        )

        discard_event = parse_fragment(state, 2.0, "D0")

        self.assertIsNotNone(discard_event)
        self.assertEqual(discard_event.event_type, "discard")
        tracker_discard = state.tracker.discards[Player.JICHA][0]
        self.assertEqual(getattr(tracker_discard, "round_discard_index", None), 0)
        self.assertEqual(getattr(tracker_discard, "event_index", None), len(state.events) - 1)

    def test_opponent_discard_updates_live_tracker_and_sequence(self) -> None:
        state = CaptureState()
        parse_fragment(
            state,
            1.0,
            (
                '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
                '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
                '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
            ),
        )
        before_sequence = state.live_update_sequence

        event = parse_fragment(state, 2.0, "E52")

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "discard")
        self.assertEqual(event.seat, 1)
        self.assertGreater(state.live_update_sequence, before_sequence)
        self.assertEqual(len(state.current_round.discards[1]), 1)
        self.assertEqual(len(state.tracker.discards[Player.SHIMOCHA]), 1)
        self.assertEqual(state.tracker.discards[Player.SHIMOCHA][0].tile_id, 20)

    def test_discard_without_init_builds_drawable_provisional_round(self) -> None:
        state = CaptureState()

        event = parse_fragment(state, 1.0, "E52")

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "discard")
        self.assertIsNotNone(state.current_round)
        self.assertFalse(state.current_round.started_from_init_like)
        self.assertEqual(state.current_round.provisional_round_sequence, 1)
        self.assertEqual(build_live_round_identity(state), ("river_epoch", 1, ("provisional", 1)))
        self.assertEqual([discard.tag for discard in state.tracker.discards[Player.SHIMOCHA]], ["E52"])
        snapshot = build_live_table_snapshot(state)
        self.assertEqual(
            [discard.tag for discard in snapshot.discard_map[Player.SHIMOCHA]],
            ["E52"],
        )

    def test_discard_after_result_without_init_starts_new_provisional_round(self) -> None:
        state = CaptureState()
        parse_fragment(state, 1.0, "E52")
        first_identity = build_live_round_identity(state)
        parse_fragment(state, 2.0, '{"tag":"RYUUKYOKU"}')

        event = parse_fragment(state, 3.0, "E56")

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "discard")
        self.assertEqual(len(state.rounds), 2)
        self.assertIsNotNone(state.rounds[0].result)
        self.assertEqual([discard.tile_136 for discard in state.rounds[0].discards[1]], [52])
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[1]], [56])
        self.assertEqual(
            [discard.tag for discard in state.tracker.discards[Player.SHIMOCHA]],
            ["E52", "E56"],
        )
        self.assertNotEqual(first_identity, build_live_round_identity(state))
        self.assertEqual(state.current_round.provisional_round_sequence, 2)

    def test_init_after_packet_first_round_clears_previous_discards(self) -> None:
        state = CaptureState()
        parse_fragment(state, 1.0, "E52")
        parse_fragment(state, 1.1, "F56")
        previous_round = state.current_round

        event = parse_fragment(
            state,
            2.0,
            (
                '{"tag":"INIT","seed":"1,0,0,2,0,3","ten":"250,250,250,250","oya":"0",'
                '"hai":"0,4,8,12,16,20,24,28,32,36,40,44,48"}'
            ),
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "init")
        self.assertIsNot(state.current_round, previous_round)
        self.assertTrue(state.current_round.started_from_init_like)
        self.assertEqual(state.current_round.discards, {0: [], 1: [], 2: [], 3: []})
        self.assertEqual(
            {player: list(state.tracker.discards[player]) for player in Player},
            {player: [] for player in Player},
        )
        snapshot = build_live_table_snapshot(state)
        self.assertEqual(
            {player: list(snapshot.discard_map[player]) for player in Player},
            {player: [] for player in Player},
        )

    def test_repeated_init_for_same_seed_drops_previous_ui_cache_identity(self) -> None:
        state = CaptureState()
        init_fragment = (
            '{"tag":"INIT","seed":"1,0,0,2,0,3","ten":"250,250,250,250","oya":"0",'
            '"hai":"0,4,8,12,16,20,24,28,32,36,40,44,48"}'
        )
        parse_fragment(state, 1.0, init_fragment)
        first_identity = build_live_round_identity(state)
        parse_fragment(state, 1.1, "E52")
        self.assertEqual([discard.tag for discard in state.tracker.discards[Player.SHIMOCHA]], ["E52"])

        parse_fragment(state, 2.0, init_fragment)
        second_identity = build_live_round_identity(state)

        self.assertNotEqual(first_identity, second_identity)
        self.assertNotEqual(
            _round_discard_cache_identity(first_identity),
            _round_discard_cache_identity(second_identity),
        )
        self.assertEqual(
            {player: list(state.tracker.discards[player]) for player in Player},
            {player: [] for player in Player},
        )
        snapshot = build_live_table_snapshot(state)
        self.assertEqual(
            {player: list(snapshot.discard_map[player]) for player in Player},
            {player: [] for player in Player},
        )

    def test_bare_init_changes_live_identity_to_drop_previous_ui_cache(self) -> None:
        state = CaptureState()
        parse_fragment(state, 1.0, '{"tag":"INIT"}')
        first_identity = build_live_round_identity(state)

        parse_fragment(state, 2.0, '{"tag":"INIT"}')
        second_identity = build_live_round_identity(state)

        self.assertNotEqual(first_identity[1], second_identity[1])

    def test_reinit_shorter_kawa_does_not_shrink_packet_captured_discards(self) -> None:
        state = CaptureState()
        bootstrap_fragment = (
            '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
            '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
            '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
        )
        parse_fragment(state, 1.0, bootstrap_fragment)
        parse_fragment(state, 2.0, "D0")
        parse_fragment(state, 2.1, "E52")

        event = parse_fragment(state, 3.0, bootstrap_fragment)

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "reinit")
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[0]], [0])
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[1]], [52])
        self.assertEqual([discard.tag for discard in state.tracker.discards[Player.JICHA]], ["D0"])
        self.assertEqual([discard.tag for discard in state.tracker.discards[Player.SHIMOCHA]], ["E52"])

    def test_reinit_projection_appends_visible_tail_after_single_omitted_discard(self) -> None:
        state = CaptureState()
        bootstrap_fragment = (
            '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
            '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
            '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
        )
        projection_fragment = (
            '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
            '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
            '"kawa0":"4","kawa1":"","kawa2":"","kawa3":""}'
        )
        parse_fragment(state, 1.0, bootstrap_fragment)
        parse_fragment(state, 2.0, "D0")

        event = parse_fragment(state, 3.0, projection_fragment)

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "reinit")
        merged_discards = state.current_round.discards[0]
        self.assertEqual([discard.tile_136 for discard in merged_discards], [0])
        self.assertFalse(merged_discards[0].called)
        self.assertEqual(merged_discards[0].lagged, 0)
        self.assertEqual([discard.tile_id for discard in state.tracker.discards[Player.JICHA]], [1])
        self.assertFalse(state.tracker.discards[Player.JICHA][0].called)
        self.assertEqual(state.live_river_store.counts_by_seat()[0], 1)

    def test_reinit_without_kawa_does_not_clear_packet_captured_discards(self) -> None:
        state = CaptureState()
        bootstrap_fragment = (
            '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
            '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
            '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
        )
        no_kawa_fragment = (
            '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
            '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135"}'
        )
        parse_fragment(state, 1.0, bootstrap_fragment)
        parse_fragment(state, 2.0, "D0")
        parse_fragment(state, 2.1, "E52")

        event = parse_fragment(state, 3.0, no_kawa_fragment)

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "reinit")
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[0]], [0])
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[1]], [52])
        self.assertEqual([discard.tag for discard in state.tracker.discards[Player.JICHA]], ["D0"])
        self.assertEqual([discard.tag for discard in state.tracker.discards[Player.SHIMOCHA]], ["E52"])

    def test_reinit_missing_one_seat_kawa_does_not_clear_that_seat(self) -> None:
        state = CaptureState()
        bootstrap_fragment = (
            '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
            '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
            '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
        )
        missing_seat_fragment = (
            '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
            '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
            '"kawa0":"0","kawa2":"","kawa3":""}'
        )
        parse_fragment(state, 1.0, bootstrap_fragment)
        parse_fragment(state, 2.0, "D0")
        parse_fragment(state, 2.1, "E52")

        event = parse_fragment(state, 3.0, missing_seat_fragment)

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "reinit")
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[0]], [0])
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[1]], [52])
        self.assertEqual([discard.tag for discard in state.tracker.discards[Player.SHIMOCHA]], ["E52"])

    def test_client_discard_request_without_init_draws_provisionally(self) -> None:
        state = CaptureState()
        before_sequence = state.live_update_sequence

        event = parse_fragment(state, 1.0, '{"tag":"D","p":"52"}')

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "discard")
        self.assertTrue(event.attrs["client_discard_request"])
        self.assertTrue(event.attrs["optimistic_discard_applied"])
        self.assertGreater(state.live_update_sequence, before_sequence)
        self.assertIsNotNone(state.current_round)
        self.assertFalse(state.current_round.started_from_init_like)
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[0]], [52])
        self.assertEqual(len(state.tracker.discards[Player.JICHA]), 1)
        self.assertTrue(state.tracker.discards[Player.JICHA][0].tag.startswith("CLIENT_DISCARD_REQUEST:"))

        confirmed = parse_fragment(state, 1.1, "D52")

        self.assertIsNotNone(confirmed)
        self.assertEqual(confirmed.event_type, "discard")
        self.assertTrue(confirmed.attrs["confirmed_client_discard_request"])
        self.assertEqual([discard.tile_136 for discard in state.current_round.discards[0]], [52])
        self.assertEqual([discard.tag for discard in state.tracker.discards[Player.JICHA]], ["D52"])

    def test_self_client_discard_request_optimistically_updates_live_hand(self) -> None:
        state = CaptureState()
        parse_fragment(
            state,
            1.0,
            (
                '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
                '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
                '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
            ),
        )
        parse_fragment(state, 2.0, "T52")

        event = parse_fragment(state, 3.0, '{"tag":"D","p":"52"}')

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "discard")
        self.assertTrue(event.attrs["client_discard_request"])
        self.assertTrue(event.attrs["optimistic_discard_applied"])
        self.assertNotIn(52, state.current_round.current_hands_136[0])
        self.assertIsNone(state.current_round.last_draw_tiles_136[0])
        self.assertIsNone(state.live_last_draw_tile_136)
        self.assertEqual(len(state.current_round.discards[0]), 1)
        self.assertEqual(len(state.tracker.discards[Player.JICHA]), 1)
        self.assertTrue(state.current_round.discards[0][0].raw_tag.startswith("CLIENT_DISCARD_REQUEST:"))

    def test_self_client_discard_request_does_not_apply_during_opponent_turn(self) -> None:
        state = CaptureState()
        parse_fragment(
            state,
            1.0,
            (
                '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
                '"hai":"0,17,27,29,39,44,48,51,52,64,68,109,134",'
                '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
            ),
        )
        parse_fragment(state, 2.0, "U")
        before_sequence = state.live_update_sequence

        event = parse_fragment(state, 3.0, '{"tag":"D","p":"52"}')

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "client_discard_request")
        self.assertFalse(event.attrs["optimistic_discard_applied"])
        self.assertEqual(event.attrs["optimistic_discard_reject_reason"], "not_self_discard_turn")
        self.assertIn(52, state.current_round.current_hands_136[0])
        self.assertEqual(state.current_round.discards[0], [])
        self.assertEqual(state.live_update_sequence, before_sequence)

    def test_self_client_discard_request_can_apply_after_self_call_turn(self) -> None:
        state = CaptureState()
        parse_fragment(
            state,
            1.0,
            (
                '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
                '"hai":"0,17,27,29,39,44,48,51,52,64,68",'
                '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
            ),
        )
        state.current_round.discard_thinking_starts[0] = (2.0, "call")

        event = parse_fragment(state, 3.0, '{"tag":"D","p":"52"}')

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "discard")
        self.assertTrue(event.attrs["optimistic_discard_applied"])
        self.assertNotIn(52, state.current_round.current_hands_136[0])
        self.assertEqual(len(state.current_round.discards[0]), 1)

    def test_live_sync_removes_called_self_discard_from_current_hand(self) -> None:
        state = CaptureState()
        round_state = RoundState()
        round_state.current_hands_136[0] = [0, 4, 8, 52]
        round_state.last_draw_tiles_136[0] = 52
        round_state.discards[0].append(Discard(tile_136=52, called=True))
        state.current_round = round_state

        _sync_live_state(state)

        self.assertNotIn(52, round_state.current_hands_136[0])
        self.assertNotIn(52, state.live_hand_tiles_136)
        self.assertIsNone(round_state.last_draw_tiles_136[0])
        self.assertIsNone(state.live_last_draw_tile_136)

    def test_live_sync_removes_self_meld_tiles_from_current_hand(self) -> None:
        state = CaptureState()
        round_state = RoundState()
        round_state.current_hands_136[0] = [0, 4, 8, 12, 16]
        round_state.last_draw_tiles_136[0] = 16
        round_state.melds[0].append(
            Meld(
                who=0,
                raw_m=0,
                from_who=1,
                meld_type="chi",
                tiles_136=[8, 12, 16],
                consumed_tile_ids=[8, 12, 16],
                called_tile_id=16,
                called_index=2,
                is_open=True,
            )
        )
        state.current_round = round_state

        _sync_live_state(state)

        self.assertEqual(round_state.current_hands_136[0], [0, 4])
        self.assertEqual(state.live_hand_tiles_136, [0, 4])
        self.assertIsNone(round_state.last_draw_tiles_136[0])

    def test_server_discard_confirmation_merges_optimistic_self_discard(self) -> None:
        state = CaptureState()
        parse_fragment(
            state,
            1.0,
            (
                '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
                '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
                '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
            ),
        )
        parse_fragment(state, 2.0, "T52")
        parse_fragment(state, 3.0, '{"tag":"D","p":"52"}')

        event = parse_fragment(state, 3.1, "D52")

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "discard")
        self.assertTrue(event.attrs["confirmed_client_discard_request"])
        self.assertEqual(len(state.current_round.discards[0]), 1)
        self.assertEqual(len(state.tracker.discards[Player.JICHA]), 1)
        discard = state.current_round.discards[0][0]
        tracker_discard = state.tracker.discards[Player.JICHA][0]
        self.assertEqual(discard.raw_tag, "D52")
        self.assertEqual(tracker_discard.tag, "D52")
        self.assertEqual(discard.event_index, len(state.events) - 1)
        self.assertEqual(getattr(tracker_discard, "event_index", None), len(state.events) - 1)

    def test_unapplied_client_discard_request_does_not_advance_live_update_token(self) -> None:
        state = CaptureState()
        parse_fragment(
            state,
            1.0,
            (
                '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
                '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
                '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
            ),
        )
        before_sequence = state.live_update_sequence

        event = parse_fragment(state, 2.0, '{"tag":"D","p":"52"}')

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "client_discard_request")
        self.assertFalse(event.attrs["optimistic_discard_applied"])
        self.assertEqual(state.live_update_sequence, before_sequence)
        self.assertEqual(state.current_round.discards[0], [])

    def test_open_call_marks_called_discard_without_shrinking_live_river(self) -> None:
        state = CaptureState()
        parse_fragment(
            state,
            1.0,
            (
                '{"tag":"REINIT","seed":"0,0,0,2,0,3","ten":"250,250,250,250","oya":"3",'
                '"hai":"0,17,27,29,39,44,48,51,64,68,109,134,135",'
                '"kawa0":"","kawa1":"","kawa2":"","kawa3":""}'
            ),
        )
        parse_fragment(state, 2.0, "G133")
        before_identity = build_live_round_identity(state)

        event = parse_fragment(state, 3.0, '<N who="0" m="51275"/>')
        snapshot = build_live_table_snapshot(state)

        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "call")
        self.assertEqual(build_live_round_identity(state), before_identity)
        self.assertEqual(len(state.current_round.discards[int(Player.KAMICHA)]), 1)
        self.assertTrue(state.current_round.discards[int(Player.KAMICHA)][0].called)
        self.assertEqual(len(state.tracker.discards[Player.KAMICHA]), 1)
        self.assertTrue(state.tracker.discards[Player.KAMICHA][0].called)
        self.assertEqual(len(snapshot.discard_map[Player.KAMICHA]), 1)
        self.assertTrue(snapshot.discard_map[Player.KAMICHA][0].called)


if __name__ == "__main__":
    unittest.main()
