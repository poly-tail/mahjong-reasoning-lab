import unittest
import queue

from capture.state import LAG_FLAG_UNCONFIRMED
from sutehai import Discard, DrawType, Player
from ui.table_renderer import (
    _INFERRED_VISIBLE_WORKER_STOP,
    _selected_inferred_visible_popup_entry_key,
    _detail_visible_tile_border_color,
    DiscardTileSelectionClickSpec,
    _ensure_inferred_visible_background_worker,
    _filter_inferred_visible_entries_for_display,
    _handle_inferred_visible_candidate_button_click,
    _handle_inferred_visible_candidate_button_double_click,
    _handle_discard_tile_selection_click,
    _handle_inferred_visible_delete_button_click,
    _handle_lag_marker_reference_button_click,
    _handle_inferred_visible_manual_count_button_click,
    _handle_inferred_visible_tile_count_click,
    _handle_selected_inferred_visible_delete_button_click,
    _merge_visible_detail_samples,
    _select_inferred_visible_tile,
    InferredVisibleCandidateButtonSpec,
    InferredVisibleDeleteButtonSpec,
    InferredVisibleEntry,
    LagMarkerReferenceButtonSpec,
    InferredVisibleManualCountButtonSpec,
    InferredVisibleSelectedTileDeleteButtonSpec,
    InferredVisibleTileCountClickSpec,
    INFERRED_VISIBLE_PON_LAG_AMOUNT,
    LAG_MARKER_REFERENCE_KIND_BLUE,
    LAG_MARKER_REFERENCE_KIND_BLACK,
    LAG_MARKER_REFERENCE_KIND_GREEN,
    _build_visible_tile_inference_summary_for_canvas,
    _build_inferred_visible_entries,
    _build_inferred_visible_entries_from_state,
    _build_visible_tile_inference_summary_from_entries,
    _drain_inferred_visible_background_result_queue,
    _inferred_visible_entry_key,
    INFERRED_VISIBLE_REASON_RED_TINT_NEIGHBOR,
    INFERRED_VISIBLE_RED_TINT_ADJACENT_AMOUNT,
    INFERRED_VISIBLE_RED_TINT_TWO_AWAY_AMOUNT,
)
from visible_tiles import (
    VisibleTileInferenceSummary,
    VisibleTileSummary,
    build_visible_tile_inference_summary,
    tile37_to_tile34_index,
)


class _DummyCanvas:
    def __init__(self) -> None:
        self.lag_marker_reference_kind = LAG_MARKER_REFERENCE_KIND_GREEN
        self.lag_marker_reference_kinds_by_entry = {}
        self.inferred_visible_entry_excluded_seats = {}
        self.inferred_visible_deleted_entry_keys = set()
        self.inferred_visible_manual_counts_by_tile34 = {}
        self.inferred_visible_runtime_enabled = True
        self.selected_inferred_visible_disabled_seats_by_tile34 = {}
        self.inferred_visible_entries = []
        self.current_visible_tile_inference_summary = VisibleTileInferenceSummary()
        self.selected_inferred_visible_tile_34_index = None
        self.selected_inferred_visible_tile_37 = None
        self.inferred_visible_tile_count_click_specs = []
        self.inferred_visible_manual_count_button_specs = []
        self.inferred_visible_delete_button_specs = []
        self.selected_inferred_visible_delete_button_specs = []
        self.inferred_visible_candidate_button_specs = []
        self.discard_tile_selection_click_specs = []
        self.lag_marker_reference_button_specs = []
        self.inferred_visible_async_result_queue = queue.Queue()
        self.inferred_visible_async_in_flight = False
        self.inferred_visible_async_pending_key = None
        self.inferred_visible_async_requested_key = None
        self.inferred_visible_async_completed_cache_key = None
        self.inferred_visible_async_thread = None
        self.redraw_action = None

    def after(self, _delay_ms, _callback):
        return None


def _discard(
    tile_id: int,
    *,
    lagged: int = 0,
    event_index: int = -1,
    round_discard_index: int = -1,
) -> Discard:
    discard = Discard(
        tile_id=tile_id,
        draw_type=DrawType.TEDASHI,
        lagged=lagged,
    )
    discard.event_index = event_index
    discard.round_discard_index = round_discard_index
    return discard


class VisibleTileInferenceSummaryTests(unittest.TestCase):
    def test_tile37_to_tile34_index_returns_none_for_missing_value(self) -> None:
        self.assertIsNone(tile37_to_tile34_index(None))

    def test_build_visible_tile_inference_summary_rounds_half_up_from_player_adjustments(self) -> None:
        tile_34_index = tile37_to_tile34_index(5)
        self.assertIsNotNone(tile_34_index)
        base_counts = [0] * 34
        base_counts[tile_34_index] = 2
        player_adjustments = {
            int(Player.KAMICHA): [0.0] * 34,
            int(Player.SHIMOCHA): [0.0] * 34,
        }
        player_adjustments[int(Player.KAMICHA)][tile_34_index] = 0.4
        player_adjustments[int(Player.SHIMOCHA)][tile_34_index] = 0.5
        summary = build_visible_tile_inference_summary(
            VisibleTileSummary(
                three_visible_tiles=[],
                four_visible_tiles=[],
                visible_counts_34_index=tuple(base_counts),
            ),
            player_adjustments_34_index=player_adjustments,
        )

        self.assertAlmostEqual(summary.global_adjustments_34_index[tile_34_index], 0.9)
        self.assertAlmostEqual(summary.adjusted_visible_counts_34_index[tile_34_index], 2.9)
        self.assertEqual(summary.rounded_visible_counts_34_index[tile_34_index], 3)
        self.assertEqual(summary.inferred_three_visible_tiles, [5])
        self.assertEqual(summary.inferred_four_visible_tiles, [])

    def test_build_visible_tile_inference_summary_caps_adjusted_total_at_four(self) -> None:
        tile_34_index = tile37_to_tile34_index(5)
        self.assertIsNotNone(tile_34_index)
        base_counts = [0] * 34
        base_counts[tile_34_index] = 3
        global_adjustments = [0.0] * 34
        global_adjustments[tile_34_index] = 2.0
        summary = build_visible_tile_inference_summary(
            VisibleTileSummary(
                three_visible_tiles=[],
                four_visible_tiles=[],
                visible_counts_34_index=tuple(base_counts),
            ),
            global_adjustments_34_index=global_adjustments,
        )

        self.assertAlmostEqual(summary.global_adjustments_34_index[tile_34_index], 2.0)
        self.assertEqual(summary.adjusted_visible_counts_34_index[tile_34_index], 4.0)
        self.assertEqual(summary.rounded_visible_counts_34_index[tile_34_index], 4)
        self.assertEqual(summary.inferred_four_visible_tiles, [5])

    def test_merge_visible_detail_samples_marks_inference_only_tiles(self) -> None:
        merged_samples, inferred_only_samples = _merge_visible_detail_samples(
            [5, 15],
            [15, 25],
        )

        self.assertEqual(merged_samples, [5, 15, 25])
        self.assertEqual(inferred_only_samples, frozenset({25}))

    def test_detail_visible_tile_border_uses_blue_for_inferred_increment(self) -> None:
        self.assertEqual(
            _detail_visible_tile_border_color(
                25,
                "four",
                inferred_incremented=True,
            ),
            "#60a5fa",
        )


class InferredVisibleEntryTests(unittest.TestCase):
    def test_lag_marker_reference_circle_click_uses_circle_hitbox(self) -> None:
        canvas = _DummyCanvas()
        entry_key = ("lag_marker", "round-1", int(Player.JICHA), 3, 10, 3, 5)
        canvas.lag_marker_reference_button_specs = [
            LagMarkerReferenceButtonSpec(
                kind=LAG_MARKER_REFERENCE_KIND_BLUE,
                center=(50.0, 50.0),
                radius=10.0,
                entry_key=entry_key,
                base_kind=LAG_MARKER_REFERENCE_KIND_BLUE,
            )
        ]

        self.assertTrue(_handle_lag_marker_reference_button_click(canvas, 55.0, 50.0))
        self.assertEqual(canvas.lag_marker_reference_kind, LAG_MARKER_REFERENCE_KIND_GREEN)
        self.assertEqual(
            canvas.lag_marker_reference_kinds_by_entry[entry_key],
            LAG_MARKER_REFERENCE_KIND_GREEN,
        )
        self.assertFalse(_handle_lag_marker_reference_button_click(canvas, 61.0, 50.0))
        self.assertEqual(canvas.lag_marker_reference_kind, LAG_MARKER_REFERENCE_KIND_GREEN)

    def test_lag_marker_click_toggles_only_the_clicked_discard(self) -> None:
        canvas = _DummyCanvas()
        entry_key_a = ("lag_marker", "round-1", int(Player.JICHA), 3, 10, 3, 5)
        entry_key_b = ("lag_marker", "round-1", int(Player.TOIMEN), 4, 11, 4, 5)
        canvas.lag_marker_reference_button_specs = [
            LagMarkerReferenceButtonSpec(
                kind=LAG_MARKER_REFERENCE_KIND_BLUE,
                center=(30.0, 30.0),
                radius=10.0,
                entry_key=entry_key_a,
                base_kind=LAG_MARKER_REFERENCE_KIND_BLUE,
            ),
            LagMarkerReferenceButtonSpec(
                kind=LAG_MARKER_REFERENCE_KIND_GREEN,
                center=(70.0, 30.0),
                radius=10.0,
                entry_key=entry_key_b,
                base_kind=LAG_MARKER_REFERENCE_KIND_GREEN,
            ),
        ]

        self.assertTrue(_handle_lag_marker_reference_button_click(canvas, 30.0, 30.0))
        self.assertEqual(
            canvas.lag_marker_reference_kinds_by_entry,
            {entry_key_a: LAG_MARKER_REFERENCE_KIND_GREEN},
        )

    def test_inferred_visible_worker_is_long_lived_per_canvas(self) -> None:
        canvas = _DummyCanvas()

        _ensure_inferred_visible_background_worker(canvas)
        first_thread = canvas.inferred_visible_async_thread
        _ensure_inferred_visible_background_worker(canvas)
        second_thread = canvas.inferred_visible_async_thread

        self.assertIsNotNone(first_thread)
        self.assertIs(first_thread, second_thread)
        canvas.inferred_visible_async_request_queue.put(_INFERRED_VISIBLE_WORKER_STOP)

    def test_red_tint_neighbor_entries_add_per_player_adjustments(self) -> None:
        kamicha_discard = _discard(5, event_index=20, round_discard_index=6)
        discard_map = {
            Player.JICHA: [],
            Player.KAMICHA: [kamicha_discard],
            Player.TOIMEN: [],
            Player.SHIMOCHA: [],
        }

        entries, _, _ = _build_inferred_visible_entries_from_state(
            discard_map,
            "round-1",
            discard_red_tint_indices_by_seat={int(Player.KAMICHA): {0}},
        )

        self.assertEqual(len(entries), 4)
        self.assertTrue(
            all(entry.source_kind == INFERRED_VISIBLE_REASON_RED_TINT_NEIGHBOR for entry in entries)
        )
        observed = {
            (entry.tile_37, entry.total_adjustment, entry.active_candidate_seats)
            for entry in entries
        }
        self.assertEqual(
            observed,
            {
                (4, INFERRED_VISIBLE_RED_TINT_ADJACENT_AMOUNT, (int(Player.KAMICHA),)),
                (6, INFERRED_VISIBLE_RED_TINT_ADJACENT_AMOUNT, (int(Player.KAMICHA),)),
                (3, INFERRED_VISIBLE_RED_TINT_TWO_AWAY_AMOUNT, (int(Player.KAMICHA),)),
                (7, INFERRED_VISIBLE_RED_TINT_TWO_AWAY_AMOUNT, (int(Player.KAMICHA),)),
            },
        )

    def test_red_tint_neighbor_adjustments_round_into_visible_three(self) -> None:
        kamicha_discard = _discard(5, event_index=20, round_discard_index=6)
        discard_map = {
            Player.JICHA: [],
            Player.KAMICHA: [kamicha_discard],
            Player.TOIMEN: [],
            Player.SHIMOCHA: [],
        }
        base_counts = [0] * 34
        tile_34_index = tile37_to_tile34_index(4)
        self.assertIsNotNone(tile_34_index)
        base_counts[tile_34_index] = 2
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=tuple(base_counts),
        )

        entries, _, _ = _build_inferred_visible_entries_from_state(
            discard_map,
            "round-1",
            discard_red_tint_indices_by_seat={int(Player.KAMICHA): {0}},
        )
        summary = _build_visible_tile_inference_summary_from_entries(
            visible_summary,
            entries,
        )

        self.assertEqual(summary.rounded_visible_counts_34_index[tile_34_index], 3)
        self.assertIn(4, summary.inferred_three_visible_tiles)
        self.assertTrue(any(entry.tile_37 == 4 for entry in entries))

    def test_green_mode_splits_pon_lag_between_active_candidates_and_applies_reveal_reduction(self) -> None:
        canvas = _DummyCanvas()
        self_discard = _discard(
            5,
            lagged=LAG_FLAG_UNCONFIRMED,
            event_index=10,
            round_discard_index=3,
        )
        entry_key = _inferred_visible_entry_key("round-1", self_discard)
        lag_entry_key = ("lag_marker", "round-1", int(Player.JICHA), 3, 10, 3, 5)
        canvas.inferred_visible_entry_excluded_seats = {
            entry_key: {int(Player.KAMICHA)},
        }
        canvas.lag_marker_reference_kinds_by_entry = {
            lag_entry_key: LAG_MARKER_REFERENCE_KIND_GREEN,
        }
        discard_map = {
            Player.JICHA: [self_discard],
            Player.KAMICHA: [],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [_discard(5, event_index=12)],
        }

        entries = _build_inferred_visible_entries(canvas, discard_map, "round-1")

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        tile_34_index = tile37_to_tile34_index(5)
        self.assertEqual(entry.active_candidate_seats, (int(Player.SHIMOCHA), int(Player.TOIMEN)))
        self.assertEqual(entry.inactive_candidate_seats, (int(Player.KAMICHA),))
        self.assertEqual(entry.revealed_candidate_seats, (int(Player.TOIMEN),))
        self.assertAlmostEqual(
            entry.seat_adjustments_34_index[int(Player.SHIMOCHA)][tile_34_index],
            INFERRED_VISIBLE_PON_LAG_AMOUNT / 2,
        )
        self.assertAlmostEqual(
            entry.seat_adjustments_34_index[int(Player.TOIMEN)][tile_34_index],
            0.0,
        )
        self.assertAlmostEqual(entry.total_adjustment, 0.9)

    def test_black_mode_disables_lag_based_inferred_visible_entries(self) -> None:
        canvas = _DummyCanvas()
        self_discard = _discard(5, lagged=LAG_FLAG_UNCONFIRMED, event_index=10)
        canvas.lag_marker_reference_kinds_by_entry = {
            ("lag_marker", "round-1", int(Player.JICHA), 10, 10, -1, 5): LAG_MARKER_REFERENCE_KIND_BLACK,
        }
        discard_map = {
            Player.JICHA: [self_discard],
            Player.KAMICHA: [],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
        }

        entries = _build_inferred_visible_entries(canvas, discard_map, "round-1")

        self.assertEqual(entries, [])
        self.assertEqual(canvas.inferred_visible_entries, [])
        self.assertEqual(
            canvas.inferred_visible_entry_excluded_seats,
            {_inferred_visible_entry_key("round-1", self_discard): set()},
        )

    def test_deleted_inferred_visible_entry_is_excluded_from_built_entries(self) -> None:
        canvas = _DummyCanvas()
        self_discard = _discard(
            5,
            lagged=LAG_FLAG_UNCONFIRMED,
            event_index=10,
            round_discard_index=3,
        )
        canvas.inferred_visible_deleted_entry_keys = {
            _inferred_visible_entry_key("round-1", self_discard),
        }
        discard_map = {
            Player.JICHA: [self_discard],
            Player.KAMICHA: [],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
        }

        entries = _build_inferred_visible_entries(canvas, discard_map, "round-1")

        self.assertEqual(entries, [])

    def test_canvas_inference_summary_applies_manual_tile_count_override(self) -> None:
        canvas = _DummyCanvas()
        tile_34_index = tile37_to_tile34_index(5)
        self.assertIsNotNone(tile_34_index)
        visible_counts = [0] * 34
        visible_counts[tile_34_index] = 2
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=tuple(visible_counts),
        )
        canvas.inferred_visible_manual_counts_by_tile34 = {tile_34_index: 1}

        summary, entries = _build_visible_tile_inference_summary_for_canvas(
            canvas,
            {
                Player.JICHA: [],
                Player.KAMICHA: [],
                Player.SHIMOCHA: [],
                Player.TOIMEN: [],
            },
            visible_summary,
            "round-1",
        )

        self.assertEqual(entries, [])
        self.assertEqual(summary.adjusted_visible_counts_34_index[tile_34_index], 3.0)
        self.assertEqual(summary.rounded_visible_counts_34_index[tile_34_index], 3)

    def test_inferred_visible_tile_count_click_cycles_zero_through_four(self) -> None:
        canvas = _DummyCanvas()
        tile_34_index = tile37_to_tile34_index(5)
        canvas.inferred_visible_tile_count_click_specs = [
            InferredVisibleTileCountClickSpec(
                tile_34_index=tile_34_index,
                rect=(0.0, 0.0, 20.0, 20.0),
            )
        ]

        observed_counts: list[int] = []
        for _unused_index in range(5):
            self.assertTrue(_handle_inferred_visible_tile_count_click(canvas, 10.0, 10.0))
            observed_counts.append(canvas.inferred_visible_manual_counts_by_tile34.get(tile_34_index, 0))

        self.assertEqual(observed_counts, [1, 2, 3, 4, 0])

    def test_inferred_visible_manual_count_button_sets_exact_value(self) -> None:
        canvas = _DummyCanvas()
        tile_34_index = tile37_to_tile34_index(5)
        canvas.inferred_visible_manual_count_button_specs = [
            InferredVisibleManualCountButtonSpec(
                tile_34_index=tile_34_index,
                count=3,
                rect=(0.0, 0.0, 20.0, 20.0),
            ),
            InferredVisibleManualCountButtonSpec(
                tile_34_index=tile_34_index,
                count=0,
                rect=(24.0, 0.0, 44.0, 20.0),
            ),
        ]

        self.assertTrue(_handle_inferred_visible_manual_count_button_click(canvas, 10.0, 10.0))
        self.assertEqual(canvas.inferred_visible_manual_counts_by_tile34.get(tile_34_index), 3)
        self.assertTrue(_handle_inferred_visible_manual_count_button_click(canvas, 30.0, 10.0))
        self.assertNotIn(tile_34_index, canvas.inferred_visible_manual_counts_by_tile34)

    def test_inferred_visible_delete_button_marks_entry_deleted(self) -> None:
        canvas = _DummyCanvas()
        entry = InferredVisibleEntryTests._build_sample_entry()
        canvas.inferred_visible_delete_button_specs = [
            InferredVisibleDeleteButtonSpec(
                entry_key=entry.key,
                rect=(0.0, 0.0, 20.0, 20.0),
            )
        ]

        self.assertTrue(_handle_inferred_visible_delete_button_click(canvas, 10.0, 10.0))
        self.assertEqual(canvas.inferred_visible_deleted_entry_keys, {entry.key})

    def test_selected_inferred_visible_delete_button_clears_selected_tile(self) -> None:
        canvas = _DummyCanvas()
        canvas.selected_inferred_visible_tile_34_index = tile37_to_tile34_index(10)
        canvas.selected_inferred_visible_tile_37 = 10
        canvas.selected_inferred_visible_delete_button_specs = [
            InferredVisibleSelectedTileDeleteButtonSpec(rect=(0.0, 0.0, 20.0, 20.0))
        ]

        self.assertTrue(_handle_selected_inferred_visible_delete_button_click(canvas, 10.0, 10.0))
        self.assertIsNone(canvas.selected_inferred_visible_tile_34_index)
        self.assertIsNone(canvas.selected_inferred_visible_tile_37)

    def test_select_inferred_visible_tile_keeps_red_tile_display_id_but_counts_in_34_kind(self) -> None:
        canvas = _DummyCanvas()

        self.assertTrue(_select_inferred_visible_tile(canvas, 10))
        self.assertEqual(canvas.selected_inferred_visible_tile_37, 10)
        self.assertEqual(canvas.selected_inferred_visible_tile_34_index, tile37_to_tile34_index(10))

    def test_inferred_visible_candidate_button_double_click_keeps_only_clicked_seat_active(self) -> None:
        canvas = _DummyCanvas()
        entry = InferredVisibleEntryTests._build_sample_entry()
        canvas.inferred_visible_candidate_button_specs = [
            InferredVisibleCandidateButtonSpec(
                entry_key=entry.key,
                seat=int(Player.KAMICHA),
                all_candidate_seats=(int(Player.KAMICHA), int(Player.TOIMEN), int(Player.SHIMOCHA)),
                rect=(0.0, 0.0, 20.0, 20.0),
            )
        ]

        self.assertTrue(_handle_inferred_visible_candidate_button_double_click(canvas, 10.0, 10.0))
        self.assertEqual(
            canvas.inferred_visible_entry_excluded_seats[entry.key],
            {int(Player.TOIMEN), int(Player.SHIMOCHA)},
        )

    def test_selected_tile_candidate_button_click_toggles_all_related_entries(self) -> None:
        canvas = _DummyCanvas()
        entry_key_a = ("round-1", 10)
        entry_key_b = ("round-1", 12)
        canvas.inferred_visible_candidate_button_specs = [
            InferredVisibleCandidateButtonSpec(
                entry_key=entry_key_a,
                seat=int(Player.TOIMEN),
                all_candidate_seats=(int(Player.KAMICHA), int(Player.TOIMEN), int(Player.SHIMOCHA)),
                rect=(0.0, 0.0, 20.0, 20.0),
                entry_keys=(entry_key_a, entry_key_b),
            )
        ]

        self.assertTrue(_handle_inferred_visible_candidate_button_click(canvas, 10.0, 10.0))
        self.assertEqual(
            canvas.inferred_visible_entry_excluded_seats,
            {
                entry_key_a: {int(Player.TOIMEN)},
                entry_key_b: {int(Player.TOIMEN)},
            },
        )
        self.assertTrue(_handle_inferred_visible_candidate_button_click(canvas, 10.0, 10.0))
        self.assertEqual(
            canvas.inferred_visible_entry_excluded_seats,
            {
                entry_key_a: set(),
                entry_key_b: set(),
            },
        )

    def test_selected_tile_candidate_button_double_click_keeps_only_clicked_seat_for_all_entries(self) -> None:
        canvas = _DummyCanvas()
        entry_key_a = ("round-1", 10)
        entry_key_b = ("round-1", 12)
        canvas.inferred_visible_candidate_button_specs = [
            InferredVisibleCandidateButtonSpec(
                entry_key=entry_key_a,
                seat=int(Player.TOIMEN),
                all_candidate_seats=(int(Player.KAMICHA), int(Player.TOIMEN), int(Player.SHIMOCHA)),
                rect=(0.0, 0.0, 20.0, 20.0),
                entry_keys=(entry_key_a, entry_key_b),
            )
        ]

        self.assertTrue(_handle_inferred_visible_candidate_button_double_click(canvas, 10.0, 10.0))
        self.assertEqual(
            canvas.inferred_visible_entry_excluded_seats,
            {
                entry_key_a: {int(Player.KAMICHA), int(Player.SHIMOCHA)},
                entry_key_b: {int(Player.KAMICHA), int(Player.SHIMOCHA)},
            },
        )

    def test_selected_popup_candidate_button_click_toggles_one_seat(self) -> None:
        canvas = _DummyCanvas()
        popup_entry_key = _selected_inferred_visible_popup_entry_key(canvas, 4)
        canvas.inferred_visible_candidate_button_specs = [
            InferredVisibleCandidateButtonSpec(
                entry_key=popup_entry_key,
                seat=int(Player.TOIMEN),
                all_candidate_seats=(int(Player.KAMICHA), int(Player.TOIMEN), int(Player.SHIMOCHA)),
                rect=(0.0, 0.0, 20.0, 20.0),
                entry_keys=(popup_entry_key,),
            )
        ]

        self.assertTrue(_handle_inferred_visible_candidate_button_click(canvas, 10.0, 10.0))
        self.assertEqual(
            canvas.selected_inferred_visible_disabled_seats_by_tile34,
            {4: {int(Player.TOIMEN)}},
        )
        self.assertTrue(_handle_inferred_visible_candidate_button_click(canvas, 10.0, 10.0))
        self.assertEqual(canvas.selected_inferred_visible_disabled_seats_by_tile34, {})

    def test_selected_popup_candidate_button_double_click_keeps_only_clicked_seat(self) -> None:
        canvas = _DummyCanvas()
        popup_entry_key = _selected_inferred_visible_popup_entry_key(canvas, 4)
        canvas.inferred_visible_candidate_button_specs = [
            InferredVisibleCandidateButtonSpec(
                entry_key=popup_entry_key,
                seat=int(Player.TOIMEN),
                all_candidate_seats=(int(Player.KAMICHA), int(Player.TOIMEN), int(Player.SHIMOCHA)),
                rect=(0.0, 0.0, 20.0, 20.0),
                entry_keys=(popup_entry_key,),
            )
        ]

        self.assertTrue(_handle_inferred_visible_candidate_button_double_click(canvas, 10.0, 10.0))
        self.assertEqual(
            canvas.selected_inferred_visible_disabled_seats_by_tile34,
            {4: {int(Player.KAMICHA), int(Player.SHIMOCHA)}},
        )

    def test_discard_tile_selection_filters_display_entries(self) -> None:
        canvas = _DummyCanvas()
        entry = InferredVisibleEntryTests._build_sample_entry()
        other_tile_34_index = tile37_to_tile34_index(6)
        other_entry = InferredVisibleEntry(
            key=("round-1", 11),
            tile_37=6,
            tile_34_index=other_tile_34_index,
            source_kind="pon_lag",
            source_event_index=11,
            source_discard_index=4,
            candidate_seats=(int(Player.KAMICHA), int(Player.TOIMEN)),
            active_candidate_seats=(int(Player.KAMICHA), int(Player.TOIMEN)),
            inactive_candidate_seats=(),
            revealed_candidate_seats=(),
            seat_adjustments_34_index={},
            total_adjustment=0.9,
        )
        canvas.discard_tile_selection_click_specs = [
            DiscardTileSelectionClickSpec(
                tile_34_index=entry.tile_34_index,
                rect=(0.0, 0.0, 20.0, 20.0),
                tile_37=10,
            )
        ]

        self.assertTrue(_handle_discard_tile_selection_click(canvas, 10.0, 10.0))
        self.assertEqual(canvas.selected_inferred_visible_tile_37, 10)
        self.assertEqual(
            _filter_inferred_visible_entries_for_display(canvas, [entry, other_entry]),
            [entry],
        )

    def test_canvas_inference_summary_returns_base_counts_while_async_worker_runs(self) -> None:
        canvas = _DummyCanvas()
        tile_34_index = tile37_to_tile34_index(5)
        self.assertIsNotNone(tile_34_index)
        visible_counts = [0] * 34
        visible_counts[tile_34_index] = 2
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=tuple(visible_counts),
        )
        discard_map = {
            Player.JICHA: [_discard(5, lagged=LAG_FLAG_UNCONFIRMED, event_index=10)],
            Player.KAMICHA: [],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
        }

        summary, entries = _build_visible_tile_inference_summary_for_canvas(
            canvas,
            discard_map,
            visible_summary,
            "round-1",
        )

        self.assertEqual(entries, [])
        self.assertEqual(summary.adjusted_visible_counts_34_index[tile_34_index], 2.0)
        self.assertEqual(canvas.current_visible_tile_inference_summary, summary)
        self.assertIsNotNone(canvas.inferred_visible_async_requested_key)

    def test_canvas_inference_summary_keeps_existing_entries_while_async_worker_runs(self) -> None:
        canvas = _DummyCanvas()
        entry = InferredVisibleEntryTests._build_sample_entry()
        canvas.inferred_visible_entries = [entry]
        tile_34_index = entry.tile_34_index
        visible_counts = [0] * 34
        visible_counts[tile_34_index] = 2
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=tuple(visible_counts),
        )

        summary, entries = _build_visible_tile_inference_summary_for_canvas(
            canvas,
            {
                Player.JICHA: [_discard(5, lagged=LAG_FLAG_UNCONFIRMED, event_index=10)],
                Player.KAMICHA: [],
                Player.SHIMOCHA: [],
                Player.TOIMEN: [],
            },
            visible_summary,
            "round-1",
        )

        self.assertEqual(entries, [entry])
        self.assertEqual(canvas.inferred_visible_entries, [entry])
        self.assertGreater(summary.adjusted_visible_counts_34_index[tile_34_index], 2.0)

    def test_drain_inferred_visible_background_result_queue_applies_matching_result(self) -> None:
        canvas = _DummyCanvas()
        summary = build_visible_tile_inference_summary(
            VisibleTileSummary(
                three_visible_tiles=[],
                four_visible_tiles=[],
                visible_counts_34_index=(0,) * 34,
            )
        )
        entry = InferredVisibleEntryTests._build_sample_entry()
        cache_key = ("inferred_visible", "round-1")
        canvas.inferred_visible_async_requested_key = cache_key
        canvas.inferred_visible_async_pending_key = cache_key
        canvas.inferred_visible_async_in_flight = True
        canvas.inferred_visible_async_result_queue.put(
            {
                "cache_key": cache_key,
                "ok": True,
                "summary": summary,
                "entries": (entry,),
                "exclusions": {entry.key: {int(Player.KAMICHA)}},
            }
        )

        changed = _drain_inferred_visible_background_result_queue(canvas)

        self.assertTrue(changed)
        self.assertFalse(canvas.inferred_visible_async_in_flight)
        self.assertEqual(canvas.inferred_visible_async_completed_cache_key, cache_key)
        self.assertEqual(canvas.current_visible_tile_inference_summary, summary)
        self.assertEqual(canvas.inferred_visible_entries, [entry])
        self.assertEqual(
            canvas.inferred_visible_entry_excluded_seats,
            {entry.key: {int(Player.KAMICHA)}},
        )

    @staticmethod
    def _build_sample_entry():
        tile_34_index = tile37_to_tile34_index(5)
        return InferredVisibleEntry(
            key=("round-1", 10),
            tile_37=5,
            tile_34_index=tile_34_index,
            source_kind="pon_lag",
            source_event_index=10,
            source_discard_index=3,
            candidate_seats=(int(Player.KAMICHA), int(Player.TOIMEN)),
            active_candidate_seats=(int(Player.KAMICHA),),
            inactive_candidate_seats=(int(Player.TOIMEN),),
            revealed_candidate_seats=(),
            seat_adjustments_34_index={
                int(Player.KAMICHA): tuple(1.8 if idx == tile_34_index else 0.0 for idx in range(34)),
            },
            total_adjustment=1.8,
        )


if __name__ == "__main__":
    unittest.main()
