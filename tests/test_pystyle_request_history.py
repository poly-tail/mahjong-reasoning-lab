import threading
import unittest

from app.hand_recommendation_service import (
    HandRecommendationEntry,
    HandRecommendationSnapshot,
)
from app.main import _remember_visible_pystyle_history, build_live_pystyle_display_context
from app.main import _build_hand_recommendation_panel_data
from app.pystyle_simulator_protocol import PystyleDisplayContext
from capture.storage import remember_pystyle_self_history
from capture.state import CaptureState, Discard, RoundState, tile136_to_tile37
from ui.table_renderer import (
    HandRecommendationItem,
    HandRecommendationPanelData,
    _build_hand_tiles_for_recommendation,
    _can_reuse_existing_hand_recommendation,
    _hand_recommendation_request_display_key,
    _normalize_hand_recommendation_key,
)


class PystyleRequestHistoryTest(unittest.TestCase):
    def test_build_hand_recommendation_panel_data_keeps_win_probability(self) -> None:
        class _FakeRecommendationService:
            def snapshot(self) -> HandRecommendationSnapshot:
                return HandRecommendationSnapshot(
                    items=(
                        HandRecommendationEntry(
                            rank=1,
                            tile_37=15,
                            tile_text="5p",
                            expected_value=1500.0,
                            expected_value_text="1500pt",
                            win_probability=0.087,
                        ),
                    ),
                    hand_key=(11, 12, 13, 15),
                    round_token="round-1",
                )

        panel = _build_hand_recommendation_panel_data(_FakeRecommendationService())

        self.assertEqual(panel.items[0].expected_value_text, "1500pt")
        self.assertAlmostEqual(panel.items[0].win_probability or 0.0, 0.087)

    def test_recommendation_hand_key_is_order_insensitive(self) -> None:
        self.assertEqual(
            _normalize_hand_recommendation_key([14, 11, 13, 12]),
            (11, 12, 13, 14),
        )

    def test_request_tiles_append_last_self_discard_only_when_no_draw_exists(self) -> None:
        self.assertEqual(
            _build_hand_tiles_for_recommendation(
                [11, 12, 13],
                None,
                fallback_tile_37=19,
            ),
            [11, 12, 13, 19],
        )

    def test_live_context_uses_last_self_discard_as_request_fallback(self) -> None:
        capture_state = CaptureState()
        round_state = RoundState(round_id="round-1")
        latest_discard_136 = 20
        round_state.discards[0].append(Discard(tile_136=latest_discard_136))
        capture_state.current_round = round_state
        capture_state.round_id = "round-1"
        capture_state.live_hand_tiles_136 = list(range(13))
        capture_state.live_last_draw_tile_136 = None

        display_context = build_live_pystyle_display_context(capture_state)

        self.assertEqual(
            display_context.request_fallback_tile_37,
            tile136_to_tile37(latest_discard_136),
        )
        self.assertFalse(display_context.allow_history_persist)

    def test_existing_pre_discard_snapshot_is_reused_in_post_discard_fallback_state(self) -> None:
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_text="5p",
                    expected_value_text="1500pt",
                ),
            ),
            hand_key=(11, 14, 12, 13),
            round_token="round-1",
        )

        self.assertTrue(
            _can_reuse_existing_hand_recommendation(
                [11, 12, 13, 14],
                panel,
                PystyleDisplayContext(
                    round_token="round-1",
                    request_fallback_tile_37=14,
                    allow_history_persist=False,
                ),
            )
        )
        self.assertFalse(
            _can_reuse_existing_hand_recommendation(
                [11, 12, 13, 14],
                panel,
                PystyleDisplayContext(
                    round_token="round-1",
                    allow_history_persist=True,
                ),
            )
        )

    def test_request_display_key_changes_again_after_next_draw(self) -> None:
        post_discard_key = _hand_recommendation_request_display_key(
            [11, 12, 13, 14],
            PystyleDisplayContext(
                round_token="round-1",
                request_fallback_tile_37=14,
                allow_history_persist=False,
            ),
        )
        next_draw_key = _hand_recommendation_request_display_key(
            [14, 11, 12, 13],
            PystyleDisplayContext(
                round_token="round-1",
                turn_index=4,
                allow_history_persist=True,
            ),
        )

        self.assertNotEqual(post_discard_key, next_draw_key)

    def test_history_cache_is_not_saved_for_reconstructed_post_only_hand(self) -> None:
        capture_state = CaptureState()
        round_state = RoundState(round_id="round-1")
        capture_state.current_round = round_state
        capture_state.round_id = "round-1"
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_text="1m",
                    expected_value_text="1200pt",
                ),
            )
        )

        _remember_visible_pystyle_history(
            capture_state,
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15],
            panel,
            PystyleDisplayContext(allow_history_persist=False),
        )

        self.assertEqual(capture_state.pystyle_self_history_by_round_hand, {})

    def test_history_cache_is_saved_only_for_live_discardable_hand(self) -> None:
        capture_state = CaptureState()
        round_state = RoundState(round_id="round-1")
        capture_state.current_round = round_state
        capture_state.round_id = "round-1"
        panel = HandRecommendationPanelData(
            items=(
                HandRecommendationItem(
                    rank=1,
                    tile_text="1m",
                    expected_value_text="1200pt",
                ),
            )
        )

        _remember_visible_pystyle_history(
            capture_state,
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15],
            panel,
            PystyleDisplayContext(allow_history_persist=True),
        )

        self.assertEqual(len(capture_state.pystyle_self_history_by_round_hand), 1)

    def test_history_cache_nonblocking_skips_when_capture_state_lock_is_busy(self) -> None:
        capture_state = CaptureState()
        round_state = RoundState(round_id="round-1")
        capture_state.current_round = round_state
        capture_state.round_id = "round-1"
        lock_acquired = threading.Event()
        release_lock = threading.Event()

        def hold_state_lock() -> None:
            with capture_state.state_lock:
                lock_acquired.set()
                release_lock.wait(timeout=2.0)

        worker = threading.Thread(target=hold_state_lock)
        worker.start()
        self.assertTrue(lock_acquired.wait(timeout=1.0))
        try:
            saved = remember_pystyle_self_history(
                capture_state,
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15],
                (("1m", "1200pt"),),
                blocking=False,
            )
        finally:
            release_lock.set()
            worker.join(timeout=1.0)

        self.assertFalse(saved)
        self.assertEqual(capture_state.pystyle_self_history_by_round_hand, {})


if __name__ == "__main__":
    unittest.main()
