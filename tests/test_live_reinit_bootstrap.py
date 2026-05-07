import unittest

from app.main import build_live_round_identity
from capture.fragment_parser import parse_fragment
from capture.state import CaptureState
from sutehai import Player


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

    def test_reinit_changes_live_round_identity_even_for_same_logical_round(self) -> None:
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
        self.assertNotEqual(first_identity, second_identity)
        self.assertEqual(first_identity[0], second_identity[0])
        self.assertEqual(first_identity[1], 1)
        self.assertEqual(second_identity[1], 2)

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


if __name__ == "__main__":
    unittest.main()
