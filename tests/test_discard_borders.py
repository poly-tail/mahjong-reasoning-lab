import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.tenhou_ui_bridge_protocol import TenhouUiBridgeControl, TenhouUiBridgeStatus, TenhouUiBridgeToggleControl
from capture.state import Discard as LiveDiscard, LAG_FLAG_UNCONFIRMED
from capture.state import Event, Meld
from sutehai import Discard, DrawType, Player
from ui.table_renderer import (
    BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
    DISCARD_TINT_BRIGHTEN_BLEND,
    DISCARD_TINT_BRIGHTEN_COLOR,
    DISCARD_RED_TINT_BLEND,
    DISCARD_RED_TINT_COLOR,
    LayoutTuningSettings,
    LAG_DISCARD_MARKER,
    MULTI_PLAYER_LAG_DISCARD_MARKER,
    PEAK_THINKING_TIME_DISCARD_MARKER,
    PON_LAG_LIKELY_DISCARD_MARKER,
    THINKING_TIME_BLUE_COLOR,
    THINKING_TIME_GREEN_COLOR,
    THINKING_TIME_OVERLAY_MAX_BLEND,
    THINKING_TIME_PURPLE_COLOR,
    THINKING_TIME_RED_COLOR,
    THINKING_TIME_YELLOW_COLOR,
    THREE_VISIBLE_DISCARD_MARKER,
    FOUR_VISIBLE_DISCARD_MARKER,
    _discard_tint_brighten_overlay_band,
    _discard_item_canvas_tag,
    _discard_tile_image,
    _discard_tint_base_overlay_bands,
    _discard_tile_tint_kind,
    _discard_border_kind,
    _collect_multi_player_lag_tiles_34,
    _detail_visible_tile_border_color,
    _draw_discards,
    _lag_marker_color,
    _lag_marker_label,
    _lag_marker_reference_copy,
    _peak_thinking_time_marker_geometry,
    _peak_thinking_time_discard_local_index,
    _push_discard_marker_geometry,
    _push_discard_marker_indices_by_seat,
    _push_marker_alerts_for_render,
    _persist_player_push_alerts,
    _should_draw_push_discard_marker,
    _should_draw_discard_visible_count_marker,
    _same_jun_candidate_discard_indices_by_seat,
    _same_jun_match_discard_indices_by_seat,
    _self_hand_honor_visible_count,
    _self_hand_honor_visible_count_geometry,
    _thinking_time_overlay_style,
    _thinking_time_tint_step,
    _visible_count_marker_kind,
    _visible_count_marker_style,
    SAME_JUN_MATCH_DISCARD_MARKER,
)
from visible_tiles import VisibleTileSummary


class DiscardBorderKindTest(unittest.TestCase):
    def test_called_discard_keeps_red_border_priority(self) -> None:
        discard = Discard(
            tile_id=5,
            draw_type=DrawType.TEDASHI,
            called=True,
            thinking_time_source="call",
        )

        self.assertEqual(_discard_border_kind(discard), "called")

    def test_post_call_tedashi_gets_yellow_border(self) -> None:
        discard = Discard(
            tile_id=5,
            draw_type=DrawType.TEDASHI,
            thinking_time_source="call",
        )

        self.assertEqual(_discard_border_kind(discard), "post_call_tedashi")

    def test_regular_tedashi_has_no_extra_border(self) -> None:
        discard = Discard(
            tile_id=5,
            draw_type=DrawType.TEDASHI,
            thinking_time_source="draw",
        )

        self.assertEqual(_discard_border_kind(discard), "none")

    def test_post_call_tsumogiri_has_no_extra_border(self) -> None:
        discard = Discard(
            tile_id=5,
            draw_type=DrawType.TSUMOGIRI,
            thinking_time_source="call",
        )

        self.assertEqual(_discard_border_kind(discard), "none")

    def test_thinking_time_overlay_style_uses_six_fixed_levels(self) -> None:
        self.assertEqual(_thinking_time_overlay_style(_thinking_time_tint_step(0.0)), (None, 0.0))
        self.assertEqual(
            _thinking_time_overlay_style(_thinking_time_tint_step(1.0)),
            (THINKING_TIME_GREEN_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND),
        )
        self.assertEqual(
            _thinking_time_overlay_style(_thinking_time_tint_step(2500.0)),
            (THINKING_TIME_BLUE_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND),
        )
        self.assertEqual(
            _thinking_time_overlay_style(_thinking_time_tint_step(4000.0)),
            (THINKING_TIME_YELLOW_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND),
        )
        self.assertEqual(
            _thinking_time_overlay_style(_thinking_time_tint_step(5600.0)),
            (THINKING_TIME_RED_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND),
        )
        self.assertEqual(
            _thinking_time_overlay_style(_thinking_time_tint_step(7000.0)),
            (THINKING_TIME_PURPLE_COLOR, THINKING_TIME_OVERLAY_MAX_BLEND),
        )

    def test_discard_tile_image_uses_base_table_when_unmodified_scale_matches(self) -> None:
        discard = Discard(
            tile_id=5,
            draw_type=DrawType.TEDASHI,
        )
        canvas = SimpleNamespace(
            current_ui_scale=1.0,
            layout_tuning_settings=None,
            discard_base_tile_image_cache={},
        )
        img_table = {
            Player.JICHA: {
                DrawType.TEDASHI: {5: "base-image"},
                DrawType.TSUMOGIRI: {5: "base-tsumogiri-image"},
            }
        }

        with patch(
            "ui.table_renderer.build_tile_photoimage",
            side_effect=AssertionError("matching scale should use the base image table"),
        ):
            image = _discard_tile_image(
                canvas,
                img_table,
                Player.JICHA,
                discard,
                tint_kind="none",
            )

        self.assertEqual(image, "base-image")

    def test_discard_tile_image_caches_scaled_base_without_tint(self) -> None:
        discard = Discard(
            tile_id=5,
            draw_type=DrawType.TEDASHI,
        )
        canvas = SimpleNamespace(
            current_ui_scale=1.0,
            layout_tuning_settings=LayoutTuningSettings(discard_tile_scale=0.8),
            discard_base_tile_image_cache={},
        )
        img_table = {
            Player.JICHA: {
                DrawType.TEDASHI: {5: "base-image"},
                DrawType.TSUMOGIRI: {5: "base-tsumogiri-image"},
            }
        }

        with patch(
            "ui.table_renderer.build_tile_photoimage",
            return_value="scaled-base-image",
        ) as build_base:
            first = _discard_tile_image(
                canvas,
                img_table,
                Player.JICHA,
                discard,
                tint_kind="none",
            )
            second = _discard_tile_image(
                canvas,
                img_table,
                Player.JICHA,
                discard,
                tint_kind="none",
            )

        self.assertEqual(first, "scaled-base-image")
        self.assertEqual(second, "scaled-base-image")
        build_base.assert_called_once_with(
            canvas,
            5,
            Player.JICHA,
            DrawType.TEDASHI,
            tile_scale=0.8,
        )

    def test_discard_tile_image_caches_composited_tint_image(self) -> None:
        discard = Discard(
            tile_id=5,
            draw_type=DrawType.TEDASHI,
        )
        canvas = SimpleNamespace(
            current_ui_scale=1.0,
            layout_tuning_settings=None,
            discard_tinted_tile_image_cache={},
        )
        img_table = {
            Player.JICHA: {
                DrawType.TEDASHI: {5: "base-image"},
                DrawType.TSUMOGIRI: {5: "base-tsumogiri-image"},
            }
        }

        with patch(
            "ui.table_renderer.build_tile_photoimage_from_base_overlay",
            return_value="red-tinted-image",
        ) as build_tinted:
            first = _discard_tile_image(
                canvas,
                img_table,
                Player.JICHA,
                discard,
                tint_kind="red",
            )
            second = _discard_tile_image(
                canvas,
                img_table,
                Player.JICHA,
                discard,
                tint_kind="red",
            )

        self.assertEqual(first, "red-tinted-image")
        self.assertEqual(second, "red-tinted-image")
        build_tinted.assert_called_once_with(
            canvas,
            5,
            Player.JICHA,
            DrawType.TEDASHI,
            base_overlay_bands=_discard_tint_base_overlay_bands("red"),
            overlay_bands=(),
            tile_scale=1.0,
        )

    def test_draw_discards_reuses_unchanged_tile_and_tags_new_items_at_creation(self) -> None:
        class ImageStub:
            def width(self) -> int:
                return 20

            def height(self) -> int:
                return 30

        class CanvasStub:
            def __init__(self) -> None:
                self.current_ui_scale = 1.0
                self.layout_tuning_settings = LayoutTuningSettings()
                self.bridge_toggle_active_overrides = {}
                self.current_round_identity = ("east1", 0)
                self.discard_tile_selection_click_specs = []
                self.lag_marker_reference_button_specs = []
                self.discard_render_cache_by_key = {}
                self.deleted_tags: list[str] = []
                self.created_items: list[tuple[str, dict[str, object]]] = []
                self.items_by_id: dict[int, tuple[str, dict[str, object]]] = {}
                self._next_item_id = 0

            def _create(self, kind: str, **kwargs: object) -> int:
                self._next_item_id += 1
                self.created_items.append((kind, kwargs))
                self.items_by_id[self._next_item_id] = (kind, kwargs)
                return self._next_item_id

            def create_image(self, *_args: object, **kwargs: object) -> int:
                return self._create("image", **kwargs)

            def create_rectangle(self, *_args: object, **kwargs: object) -> int:
                return self._create("rectangle", **kwargs)

            def create_oval(self, *_args: object, **kwargs: object) -> int:
                return self._create("oval", **kwargs)

            def create_polygon(self, *_args: object, **kwargs: object) -> int:
                return self._create("polygon", **kwargs)

            def create_text(self, *_args: object, **kwargs: object) -> int:
                return self._create("text", **kwargs)

            def delete(self, tag: str) -> None:
                self.deleted_tags.append(tag)
                normalized_tag = str(tag)
                self.items_by_id = {
                    item_id: (kind, kwargs)
                    for item_id, (kind, kwargs) in self.items_by_id.items()
                    if normalized_tag not in kwargs.get("tags", ())
                }

            def find_withtag(self, tag: str) -> tuple[int, ...]:
                normalized_tag = str(tag)
                return tuple(
                    item_id
                    for item_id, (_kind, kwargs) in self.items_by_id.items()
                    if normalized_tag in kwargs.get("tags", ())
                )

            def type(self, item_id: int) -> str:
                return self.items_by_id[int(item_id)][0]

            def bbox(self, _item_id: int) -> tuple[int, int, int, int] | None:
                return None

            def tag_lower(self, *_args: object) -> None:
                return None

            def move(self, *_args: object) -> None:
                return None

        canvas = CanvasStub()
        discard = Discard(tile_id=5, draw_type=DrawType.TEDASHI)
        img_table = {
            player: {
                DrawType.TEDASHI: {1: ImageStub(), 5: ImageStub()},
                DrawType.TSUMOGIRI: {1: ImageStub(), 5: ImageStub()},
            }
            for player in Player
        }
        layout = {
            "discard_rects": {
                player: (0.0, 0.0, 160.0, 120.0)
                for player in Player
            }
        }
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=(0,) * 34,
        )

        _draw_discards(
            canvas,
            img_table,
            {Player.JICHA: [discard]},
            {},
            layout,
            visible_summary,
            {},
            {},
            (),
        )
        first_item_count = len(canvas.created_items)
        item_tag = _discard_item_canvas_tag(Player.JICHA, 0)
        image_tags = [
            kwargs.get("tags")
            for kind, kwargs in canvas.created_items
            if kind == "image"
        ]
        self.assertEqual(first_item_count, 1)
        self.assertIn(("live_async_discards", item_tag), image_tags)

        _draw_discards(
            canvas,
            img_table,
            {Player.JICHA: [discard]},
            {},
            layout,
            visible_summary,
            {},
            {},
            (),
        )
        self.assertEqual(len(canvas.created_items), first_item_count)
        self.assertEqual(canvas.deleted_tags, [])
        self.assertEqual(canvas.last_discard_render_stats["skipped"], 1)
        self.assertEqual(len(canvas.discard_tile_selection_click_specs), 1)

        canvas.discard_tile_image_refs = {}
        _draw_discards(
            canvas,
            img_table,
            {Player.JICHA: [discard]},
            {},
            layout,
            visible_summary,
            {},
            {},
            (),
        )
        self.assertGreater(len(canvas.created_items), first_item_count)
        self.assertEqual(canvas.last_discard_render_stats["skipped"], 0)
        self.assertEqual(canvas.last_discard_render_stats["changed"], 1)
        self.assertEqual(canvas.last_discard_render_stats["missing_image_refs"], 1)

        first_item_count = len(canvas.created_items)
        canvas.deleted_tags = []
        canvas.delete(item_tag)
        _draw_discards(
            canvas,
            img_table,
            {Player.JICHA: [discard]},
            {},
            layout,
            visible_summary,
            {},
            {},
            (),
        )
        self.assertGreater(len(canvas.created_items), first_item_count)
        self.assertEqual(canvas.last_discard_render_stats["skipped"], 0)
        self.assertEqual(canvas.last_discard_render_stats["changed"], 1)
        self.assertEqual(canvas.last_discard_render_stats["missing_image_items"], 1)

        first_item_count = len(canvas.created_items)
        canvas.deleted_tags = []
        canvas.items_by_id = {
            999: (
                "rectangle",
                {"tags": ("live_async_discards", item_tag)},
            )
        }
        _draw_discards(
            canvas,
            img_table,
            {Player.JICHA: [discard]},
            {},
            layout,
            visible_summary,
            {},
            {},
            (),
        )
        self.assertGreater(len(canvas.created_items), first_item_count)
        self.assertEqual(canvas.last_discard_render_stats["skipped"], 0)
        self.assertEqual(canvas.last_discard_render_stats["changed"], 1)
        self.assertEqual(canvas.last_discard_render_stats["missing_image_items"], 1)

        first_item_count = len(canvas.created_items)
        canvas.deleted_tags = []
        with patch(
            "ui.table_renderer.build_tile_photoimage_from_base_overlay",
            return_value=ImageStub(),
        ) as build_tinted:
            _draw_discards(
                canvas,
                img_table,
                {Player.JICHA: [discard]},
                {int(Player.JICHA): frozenset({0})},
                layout,
                visible_summary,
                {},
                {},
                (),
            )
        self.assertEqual(canvas.deleted_tags, [item_tag])
        self.assertGreater(len(canvas.created_items), first_item_count)
        self.assertEqual(canvas.last_discard_render_stats["changed"], 1)
        build_tinted.assert_called_once()
        new_items = canvas.created_items[first_item_count:]
        self.assertFalse(any(kind == "rectangle" for kind, _kwargs in new_items))

    def test_visible_count_marker_kind_prefers_four_over_three(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[5, 15],
            four_visible_tiles=[15, 25],
        )

        self.assertEqual(_visible_count_marker_kind(15, visible_summary), "four")
        self.assertEqual(_visible_count_marker_kind(5, visible_summary), "three")
        self.assertEqual(_visible_count_marker_kind(25, visible_summary), "four")
        self.assertEqual(_visible_count_marker_kind(35, visible_summary), "none")

    def test_visible_count_marker_style_uses_circle_colors(self) -> None:
        self.assertEqual(
            _visible_count_marker_style("three"),
            ("circle", THREE_VISIBLE_DISCARD_MARKER),
        )
        self.assertIsNone(_visible_count_marker_style("four"))
        self.assertIsNone(_visible_count_marker_style("none"))

    def test_visible_count_marker_on_discards_is_limited_to_tedashi(self) -> None:
        self.assertTrue(
            _should_draw_discard_visible_count_marker(
                Discard(tile_id=5, draw_type=DrawType.TEDASHI)
            )
        )
        self.assertFalse(
            _should_draw_discard_visible_count_marker(
                Discard(tile_id=5, draw_type=DrawType.TSUMOGIRI)
            )
        )

    def test_detail_visible_tile_border_color_only_marks_suited_three_to_seven(self) -> None:
        self.assertEqual(
            _detail_visible_tile_border_color(3, "three"),
            THREE_VISIBLE_DISCARD_MARKER,
        )
        self.assertEqual(
            _detail_visible_tile_border_color(17, "four"),
            FOUR_VISIBLE_DISCARD_MARKER,
        )
        self.assertIsNone(_detail_visible_tile_border_color(1, "three"))
        self.assertIsNone(_detail_visible_tile_border_color(29, "four"))
        self.assertIsNone(_detail_visible_tile_border_color(31, "three"))

    def test_multi_player_lag_marker_switches_to_green(self) -> None:
        self.assertEqual(LAG_DISCARD_MARKER, "#2563eb")
        self.assertEqual(PON_LAG_LIKELY_DISCARD_MARKER, "#22c55e")
        self.assertEqual(MULTI_PLAYER_LAG_DISCARD_MARKER, PON_LAG_LIKELY_DISCARD_MARKER)
        self.assertEqual(PEAK_THINKING_TIME_DISCARD_MARKER, "#dc2626")
        self.assertEqual(THREE_VISIBLE_DISCARD_MARKER, "#ec4899")
        self.assertEqual(FOUR_VISIBLE_DISCARD_MARKER, "#a855f7")
        self.assertEqual(SAME_JUN_MATCH_DISCARD_MARKER, "#facc15")

    def test_lag_marker_turns_green_when_self_snapshot_cannot_call(self) -> None:
        discard = Discard(
            tile_id=1,
            draw_type=DrawType.TEDASHI,
            lagged=LAG_FLAG_UNCONFIRMED,
            self_hand_tiles_before_discard_136=[12, 16, 36, 40],
        )

        self.assertEqual(
            _lag_marker_color(
                Player.KAMICHA,
                discard,
                set(),
                bridge_status=TenhouUiBridgeStatus(
                    ws_url="ws://127.0.0.1:8765",
                    visible_controls=(),
                    toggle_controls=(
                        TenhouUiBridgeToggleControl(
                            control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                            available=True,
                            active=False,
                            text="",
                            label="",
                        ),
                    ),
                ),
            ),
            PON_LAG_LIKELY_DISCARD_MARKER,
        )

    def test_kamicha_lag_turns_green_when_naki_disabled_is_on(self) -> None:
        discard = Discard(
            tile_id=3,
            draw_type=DrawType.TEDASHI,
            lagged=LAG_FLAG_UNCONFIRMED,
            self_hand_tiles_before_discard_136=[0, 4, 36, 40],
        )

        self.assertEqual(
            _lag_marker_color(
                Player.KAMICHA,
                discard,
                set(),
                bridge_status=TenhouUiBridgeStatus(
                    ws_url="ws://127.0.0.1:8765",
                    visible_controls=(),
                    toggle_controls=(
                        TenhouUiBridgeToggleControl(
                            control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                            available=True,
                            active=True,
                            text="",
                            label="",
                        ),
                    ),
                ),
            ),
            PON_LAG_LIKELY_DISCARD_MARKER,
        )

    def test_kamicha_lag_stays_blue_when_self_snapshot_can_chi(self) -> None:
        discard = Discard(
            tile_id=3,
            draw_type=DrawType.TEDASHI,
            lagged=LAG_FLAG_UNCONFIRMED,
            self_hand_tiles_before_discard_136=[0, 4, 36, 40],
        )

        self.assertEqual(
            _lag_marker_color(
                Player.KAMICHA,
                discard,
                set(),
                bridge_status=TenhouUiBridgeStatus(
                    ws_url="ws://127.0.0.1:8765",
                    visible_controls=(),
                    toggle_controls=(
                        TenhouUiBridgeToggleControl(
                            control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                            available=True,
                            active=False,
                            text="",
                            label="",
                        ),
                    ),
                ),
            ),
            LAG_DISCARD_MARKER,
        )

    def test_kamicha_lag_stays_blue_when_call_button_is_visible(self) -> None:
        discard = Discard(
            tile_id=1,
            draw_type=DrawType.TEDASHI,
            lagged=LAG_FLAG_UNCONFIRMED,
            self_hand_tiles_before_discard_136=[4, 8, 36, 40],
        )

        self.assertEqual(
            _lag_marker_color(
                Player.KAMICHA,
                discard,
                set(),
                bridge_status=TenhouUiBridgeStatus(
                    ws_url="ws://127.0.0.1:8765",
                    visible_controls=(
                        TenhouUiBridgeControl(control_id=3671045, visible=True, text="鳴き", label="鳴き"),
                    ),
                    toggle_controls=(
                        TenhouUiBridgeToggleControl(
                            control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                            available=True,
                            active=False,
                            text="",
                            label="",
                        ),
                    ),
                ),
            ),
            LAG_DISCARD_MARKER,
        )

    def test_non_kamicha_lag_stays_blue_without_multi_player_match(self) -> None:
        discard = Discard(
            tile_id=1,
            draw_type=DrawType.TEDASHI,
            lagged=LAG_FLAG_UNCONFIRMED,
            self_hand_tiles_before_discard_136=[4, 8, 36, 40],
        )

        self.assertEqual(
            _lag_marker_color(
                Player.TOIMEN,
                discard,
                set(),
                bridge_status=TenhouUiBridgeStatus(
                    ws_url="ws://127.0.0.1:8765",
                    visible_controls=(),
                    toggle_controls=(
                        TenhouUiBridgeToggleControl(
                            control_id=BRIDGE_NAKI_DISABLED_TOGGLE_CONTROL_ID,
                            available=True,
                            active=False,
                            text="",
                            label="",
                        ),
                    ),
                ),
            ),
            LAG_DISCARD_MARKER,
        )

    def test_honor_lag_uses_green_pl_marker_without_other_context(self) -> None:
        discard = Discard(
            tile_id=31,
            draw_type=DrawType.TEDASHI,
            lagged=LAG_FLAG_UNCONFIRMED,
        )

        self.assertEqual(
            _lag_marker_color(Player.JICHA, discard, set()),
            PON_LAG_LIKELY_DISCARD_MARKER,
        )
        self.assertEqual(
            _lag_marker_color(Player.TOIMEN, discard, set()),
            PON_LAG_LIKELY_DISCARD_MARKER,
        )

    def test_multi_player_same_tile_lag_still_uses_green_marker_without_snapshot(self) -> None:
        discard = Discard(
            tile_id=1,
            draw_type=DrawType.TEDASHI,
            lagged=LAG_FLAG_UNCONFIRMED,
        )

        self.assertEqual(
            _lag_marker_color(Player.TOIMEN, discard, {0}),
            PON_LAG_LIKELY_DISCARD_MARKER,
        )

    def test_lag_marker_label_uses_l_for_blue_and_pl_for_green(self) -> None:
        self.assertEqual(_lag_marker_label(LAG_DISCARD_MARKER), "L")
        self.assertEqual(_lag_marker_label(PON_LAG_LIKELY_DISCARD_MARKER), "Pl")

    def test_push_discard_marker_indices_by_seat_only_tracks_push_payloads(self) -> None:
        self.assertEqual(
            _push_discard_marker_indices_by_seat(
                {
                    int(Player.KAMICHA): {"seat": int(Player.KAMICHA), "kind": "push", "discard_index": 7},
                    int(Player.TOIMEN): {"seat": int(Player.TOIMEN), "kind": "release", "discard_index": 8},
                    int(Player.SHIMOCHA): {
                        "seat": int(Player.SHIMOCHA),
                        "percentage": 6.2,
                        "threshold_percent": 6.0,
                        "discard_index": 9,
                    },
                }
            ),
            {
                int(Player.KAMICHA): frozenset({7}),
                int(Player.SHIMOCHA): frozenset({9}),
            },
        )

    def test_push_discard_marker_draws_on_any_river_row(self) -> None:
        first_row_discard = Discard(tile_id=5, draw_type=DrawType.TEDASHI)
        second_row_discard = Discard(tile_id=5, draw_type=DrawType.TEDASHI)

        self.assertTrue(
            _should_draw_push_discard_marker(first_row_discard, 5, frozenset({5}))
        )
        self.assertTrue(
            _should_draw_push_discard_marker(second_row_discard, 6, frozenset({6}))
        )

    def test_push_discard_marker_uses_global_index_without_local_row_gate(self) -> None:
        discard = SimpleNamespace(
            tile_id=5,
            draw_type=DrawType.TEDASHI,
            round_discard_index=42,
        )

        self.assertTrue(_should_draw_push_discard_marker(discard, 5, frozenset({42})))
        self.assertTrue(_should_draw_push_discard_marker(discard, 6, frozenset({42})))

    def test_push_marker_ignores_old_panel_latch_when_raw_push_is_gone(self) -> None:
        raw_marker_alerts = _push_marker_alerts_for_render(
            {}
        )
        persisted_alerts = _persist_player_push_alerts(
            raw_marker_alerts,
            {
                int(Player.SHIMOCHA): {
                    "seat": int(Player.SHIMOCHA),
                    "percentage": 12.5,
                    "discard_index": 2,
                    "is_current": False,
                    "tile_label": "8m",
                    "kind": "push",
                }
            },
            7,
        )

        self.assertEqual(_push_discard_marker_indices_by_seat(raw_marker_alerts), {})
        self.assertEqual(
            _push_discard_marker_indices_by_seat(persisted_alerts),
            {int(Player.SHIMOCHA): frozenset({2})},
        )

    def test_lag_marker_reference_copy_mentions_l_pl_n_meanings(self) -> None:
        blue_title, blue_body = _lag_marker_reference_copy("blue")
        green_title, green_body = _lag_marker_reference_copy("green")
        black_title, black_body = _lag_marker_reference_copy("black")

        self.assertEqual(blue_title, "Lag marker: L")
        self.assertIn("lagged = 1 / 3", blue_body)
        self.assertIn("L -> Pl -> N", blue_body)
        self.assertEqual(green_title, "Lag marker: Pl")
        self.assertIn("鳴き無しON", green_body)
        self.assertEqual(black_title, "Lag marker: N")
        self.assertIn("無効扱い", black_body)

    def test_awaseuchi_marks_discard_when_tile_visibility_increased_by_other_discard(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI, tag="D1"),
                Discard(tile_id=25, draw_type=DrawType.TEDASHI, tag="D25"),
            ],
            Player.TOIMEN: [
                Discard(tile_id=25, draw_type=DrawType.TEDASHI, tag="V25"),
            ],
            Player.SHIMOCHA: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.TOIMEN][0].event_index = 1
        discard_map[Player.JICHA][1].event_index = 2

        highlighted = _same_jun_match_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset({1}))
        self.assertEqual(highlighted[int(Player.TOIMEN)], frozenset())

    def test_awaseuchi_candidate_marks_same_tile_within_recent_seven_public_events(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [
                Discard(tile_id=2, draw_type=DrawType.TEDASHI),
                Discard(tile_id=3, draw_type=DrawType.TEDASHI),
            ],
            Player.TOIMEN: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
                Discard(tile_id=4, draw_type=DrawType.TEDASHI),
            ],
            Player.KAMICHA: [
                Discard(tile_id=5, draw_type=DrawType.TEDASHI),
                Discard(tile_id=6, draw_type=DrawType.TEDASHI),
                Discard(tile_id=7, draw_type=DrawType.TEDASHI),
            ],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.TOIMEN][0].event_index = 1
        discard_map[Player.SHIMOCHA][0].event_index = 2
        discard_map[Player.KAMICHA][0].event_index = 3
        discard_map[Player.SHIMOCHA][1].event_index = 4
        discard_map[Player.TOIMEN][1].event_index = 5
        discard_map[Player.KAMICHA][1].event_index = 6
        discard_map[Player.KAMICHA][2].event_index = 7
        discard_map[Player.JICHA][1].event_index = 8

        highlighted = _same_jun_candidate_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset({1}))

    def test_awaseuchi_candidate_ignores_same_tile_older_than_recent_seven_public_events(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [
                Discard(tile_id=2, draw_type=DrawType.TEDASHI),
                Discard(tile_id=3, draw_type=DrawType.TEDASHI),
                Discard(tile_id=4, draw_type=DrawType.TEDASHI),
            ],
            Player.TOIMEN: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
                Discard(tile_id=5, draw_type=DrawType.TEDASHI),
                Discard(tile_id=6, draw_type=DrawType.TEDASHI),
            ],
            Player.KAMICHA: [
                Discard(tile_id=7, draw_type=DrawType.TEDASHI),
                Discard(tile_id=8, draw_type=DrawType.TEDASHI),
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
            ],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.TOIMEN][0].event_index = 1
        discard_map[Player.SHIMOCHA][0].event_index = 2
        discard_map[Player.KAMICHA][0].event_index = 3
        discard_map[Player.SHIMOCHA][1].event_index = 4
        discard_map[Player.TOIMEN][1].event_index = 5
        discard_map[Player.KAMICHA][1].event_index = 6
        discard_map[Player.SHIMOCHA][2].event_index = 7
        discard_map[Player.TOIMEN][2].event_index = 8
        discard_map[Player.KAMICHA][2].event_index = 9
        discard_map[Player.JICHA][1].event_index = 10

        highlighted = _same_jun_candidate_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset())

    def test_awaseuchi_ignores_visibility_increase_before_previous_own_discard(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
                Discard(tile_id=25, draw_type=DrawType.TEDASHI),
            ],
            Player.TOIMEN: [
                Discard(tile_id=25, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.TOIMEN][0].event_index = 0
        discard_map[Player.JICHA][0].event_index = 1
        discard_map[Player.JICHA][1].event_index = 2

        highlighted = _same_jun_match_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset())

    def test_awaseuchi_marks_tsumogiri_too(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
                Discard(tile_id=25, draw_type=DrawType.TSUMOGIRI),
            ],
            Player.TOIMEN: [
                Discard(tile_id=25, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.TOIMEN][0].event_index = 1
        discard_map[Player.JICHA][1].event_index = 2

        highlighted = _same_jun_match_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset({1}))

    def test_awaseuchi_marks_discard_when_meld_reveals_same_tile(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
                Discard(tile_id=6, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.JICHA][1].event_index = 2
        melds_by_player = {
            Player.JICHA: [],
            Player.SHIMOCHA: [Meld(who=1, raw_m=0, meld_type="chi", tiles_37=[5, 6, 7], event_index=1)],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }

        highlighted = _same_jun_match_discard_indices_by_seat(discard_map, melds_by_player)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset({1}))

    def test_awaseuchi_marks_discard_when_dora_indicator_reveals_same_tile(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.JICHA][1].event_index = 2
        round_events = [
            Event(timestamp=None, event_type="noop"),
            Event(timestamp=None, event_type="dora", tile_136=0),
            Event(timestamp=None, event_type="noop"),
        ]

        highlighted = _same_jun_match_discard_indices_by_seat(
            discard_map,
            round_events=round_events,
        )

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset({1}))

    def test_awaseuchi_uses_dora_event_index_when_round_events_are_filtered(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.JICHA][1].event_index = 2
        dora_event = Event(timestamp=None, event_type="dora", tile_136=0)
        dora_event.event_index = 1

        highlighted = _same_jun_match_discard_indices_by_seat(
            discard_map,
            round_events=[dora_event],
        )

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset({1}))

    def test_awaseuchi_ignores_private_draw_events(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.JICHA][1].event_index = 2
        round_events = [
            Event(timestamp=None, event_type="noop"),
            Event(timestamp=None, event_type="draw", seat=int(Player.JICHA), tile_136=0),
            Event(timestamp=None, event_type="noop"),
        ]

        highlighted = _same_jun_match_discard_indices_by_seat(
            discard_map,
            round_events=round_events,
        )

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset())

    def test_awaseuchi_clears_flag_when_next_discard_is_different_tile(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
                Discard(tile_id=25, draw_type=DrawType.TEDASHI),
            ],
            Player.TOIMEN: [
                Discard(tile_id=25, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.TOIMEN][0].event_index = 1
        discard_map[Player.JICHA][1].event_index = 2
        discard_map[Player.JICHA][2].event_index = 3

        highlighted = _same_jun_match_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset())

    def test_awaseuchi_flags_are_independent_per_players_next_discard(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [
                Discard(tile_id=2, draw_type=DrawType.TEDASHI),
                Discard(tile_id=25, draw_type=DrawType.TEDASHI),
            ],
            Player.TOIMEN: [
                Discard(tile_id=25, draw_type=DrawType.TEDASHI),
            ],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.SHIMOCHA][0].event_index = 1
        discard_map[Player.TOIMEN][0].event_index = 2
        discard_map[Player.JICHA][1].event_index = 3
        discard_map[Player.SHIMOCHA][1].event_index = 4

        highlighted = _same_jun_match_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset())
        self.assertEqual(highlighted[int(Player.SHIMOCHA)], frozenset({1}))

    def test_awaseuchi_supports_live_discard_shape_with_tile_136(self) -> None:
        discard_map = {
            Player.JICHA: [
                LiveDiscard(tile_136=0),
                LiveDiscard(tile_136=1),
            ],
            Player.TOIMEN: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.TOIMEN][0].event_index = 1
        discard_map[Player.JICHA][1].event_index = 2

        highlighted = _same_jun_match_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset({1}))

    def test_awaseuchi_flag_from_own_discard_does_not_apply_to_same_player(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
            ],
            Player.TOIMEN: [],
            Player.SHIMOCHA: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.JICHA][1].event_index = 1

        highlighted = _same_jun_match_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset())

    def test_awaseuchi_called_tile_from_other_discard_stays_valid_for_caller(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
                Discard(tile_id=5, draw_type=DrawType.TEDASHI),
            ],
            Player.TOIMEN: [
                Discard(tile_id=5, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [],
            Player.KAMICHA: [],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.TOIMEN][0].event_index = 1
        discard_map[Player.JICHA][1].event_index = 3
        melds_by_player = {
            Player.JICHA: [
                Meld(
                    who=0,
                    raw_m=0,
                    meld_type="chi",
                    tiles_37=[5, 6, 7],
                    called_tile_id=16,
                    called_index=0,
                    event_index=2,
                )
            ],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        }

        highlighted = _same_jun_match_discard_indices_by_seat(
            discard_map,
            melds_by_player=melds_by_player,
        )

        self.assertEqual(highlighted[int(Player.JICHA)], frozenset({1}))

    def test_awaseuchi_rearms_when_same_tile_becomes_visible_again_after_flags_expire(self) -> None:
        discard_map = {
            Player.JICHA: [
                Discard(tile_id=9, draw_type=DrawType.TEDASHI),
                Discard(tile_id=8, draw_type=DrawType.TEDASHI),
            ],
            Player.SHIMOCHA: [
                Discard(tile_id=7, draw_type=DrawType.TEDASHI),
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
            ],
            Player.TOIMEN: [
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
                Discard(tile_id=6, draw_type=DrawType.TEDASHI),
                Discard(tile_id=1, draw_type=DrawType.TEDASHI),
            ],
            Player.KAMICHA: [
                Discard(tile_id=5, draw_type=DrawType.TEDASHI),
            ],
        }
        discard_map[Player.JICHA][0].event_index = 0
        discard_map[Player.TOIMEN][0].event_index = 1
        discard_map[Player.SHIMOCHA][0].event_index = 2
        discard_map[Player.KAMICHA][0].event_index = 3
        discard_map[Player.JICHA][1].event_index = 4
        discard_map[Player.TOIMEN][1].event_index = 5
        discard_map[Player.TOIMEN][2].event_index = 6
        discard_map[Player.SHIMOCHA][1].event_index = 7

        highlighted = _same_jun_match_discard_indices_by_seat(discard_map)

        self.assertEqual(highlighted[int(Player.SHIMOCHA)], frozenset({1}))
        self.assertEqual(highlighted[int(Player.JICHA)], frozenset())
        self.assertEqual(highlighted[int(Player.TOIMEN)], frozenset())

    def test_peak_thinking_time_marker_ignores_first_discard(self) -> None:
        discards = [
            Discard(tile_id=1, draw_type=DrawType.TEDASHI, thinking_time_ms=5000.0),
            Discard(tile_id=2, draw_type=DrawType.TEDASHI, thinking_time_ms=1200.0),
            Discard(tile_id=3, draw_type=DrawType.TEDASHI, thinking_time_ms=1800.0),
        ]

        self.assertEqual(_peak_thinking_time_discard_local_index(discards), 2)

    def test_peak_thinking_time_marker_uses_latest_discard_on_tie(self) -> None:
        discards = [
            Discard(tile_id=1, draw_type=DrawType.TEDASHI, thinking_time_ms=400.0),
            Discard(tile_id=2, draw_type=DrawType.TEDASHI, thinking_time_ms=1800.0),
            Discard(tile_id=3, draw_type=DrawType.TEDASHI, thinking_time_ms=1800.0),
        ]

        self.assertEqual(_peak_thinking_time_discard_local_index(discards), 2)

    def test_peak_thinking_time_marker_ignores_riseki_completion_discards(self) -> None:
        discards = [
            SimpleNamespace(thinking_time_ms=800.0, is_tsumogiri_estimated=False),
            SimpleNamespace(thinking_time_ms=9000.0, is_tsumogiri_estimated=True),
            SimpleNamespace(thinking_time_ms=1800.0, is_tsumogiri_estimated=False),
        ]

        self.assertEqual(_peak_thinking_time_discard_local_index(discards), 2)

    def test_peak_thinking_time_marker_geometry_uses_pre_rotation_lower_edge(self) -> None:
        jicha_x, jicha_y, marker_radius = _peak_thinking_time_marker_geometry(
            Player.JICHA,
            10.0,
            20.0,
            50.0,
            80.0,
        )
        toimen_x, toimen_y, _ = _peak_thinking_time_marker_geometry(
            Player.TOIMEN,
            10.0,
            20.0,
            50.0,
            80.0,
        )
        shimo_x, shimo_y, _ = _peak_thinking_time_marker_geometry(
            Player.SHIMOCHA,
            10.0,
            20.0,
            50.0,
            80.0,
        )
        kami_x, kami_y, _ = _peak_thinking_time_marker_geometry(
            Player.KAMICHA,
            10.0,
            20.0,
            50.0,
            80.0,
        )

        self.assertEqual(marker_radius, 6.0)
        self.assertAlmostEqual(jicha_x, 30.0)
        self.assertAlmostEqual(jicha_y, 72.0)
        self.assertEqual((toimen_x, toimen_y), (30.0, 28.0))
        self.assertEqual((shimo_x, shimo_y), (42.0, 50.0))
        self.assertEqual((kami_x, kami_y), (18.0, 50.0))

    def test_push_discard_marker_geometry_stays_inside_next_to_lag_marker(self) -> None:
        jicha_x, jicha_y = _push_discard_marker_geometry(
            Player.JICHA,
            10.0,
            20.0,
            50.0,
            80.0,
            1.0,
        )
        toimen_x, toimen_y = _push_discard_marker_geometry(
            Player.TOIMEN,
            10.0,
            20.0,
            50.0,
            80.0,
            1.0,
        )
        shimo_x, shimo_y = _push_discard_marker_geometry(
            Player.SHIMOCHA,
            10.0,
            20.0,
            50.0,
            80.0,
            1.0,
        )
        kami_x, kami_y = _push_discard_marker_geometry(
            Player.KAMICHA,
            10.0,
            20.0,
            50.0,
            80.0,
            1.0,
        )

        self.assertAlmostEqual(jicha_x, 24.4)
        self.assertAlmostEqual(jicha_y, 27.0)
        self.assertAlmostEqual(toimen_x, 35.6)
        self.assertAlmostEqual(toimen_y, 73.0)
        self.assertAlmostEqual(shimo_x, 17.0)
        self.assertAlmostEqual(shimo_y, 58.4)
        self.assertAlmostEqual(kami_x, 43.0)
        self.assertAlmostEqual(kami_y, 41.6)

    def test_collect_multi_player_lag_tiles_34_ignores_riseki_completion_discards(self) -> None:
        discard_map = {
            Player.JICHA: [
                SimpleNamespace(
                    called=False,
                    lagged=LAG_FLAG_UNCONFIRMED,
                    tile_id=5,
                    is_tsumogiri_estimated=True,
                )
            ],
            Player.SHIMOCHA: [
                SimpleNamespace(
                    called=False,
                    lagged=LAG_FLAG_UNCONFIRMED,
                    tile_id=5,
                    is_tsumogiri_estimated=False,
                )
            ],
        }

        self.assertEqual(_collect_multi_player_lag_tiles_34(discard_map), set())

    def test_red_tint_turns_purple_when_highlighted_tile_is_four_visible(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[5],
            visible_counts_34_index=tuple([0, 0, 0, 0, 4] + [0] * 29),
        )
        tedashi = SimpleNamespace(called=False, tsumogiri=False)

        self.assertEqual(
            _discard_tile_tint_kind(
                tedashi,
                4,
                should_red_tint=True,
                visible_summary=visible_summary,
            ),
            "four_visible",
        )
        self.assertEqual(visible_summary.four_visible_tile34_index_set, frozenset({4}))

    def test_discard_tint_uses_white_brighten_band_before_color(self) -> None:
        brighten_band = (
            0.0,
            1.0,
            DISCARD_TINT_BRIGHTEN_COLOR,
            DISCARD_TINT_BRIGHTEN_COLOR,
            DISCARD_TINT_BRIGHTEN_BLEND,
        )
        red_band = (
            0.0,
            1.0,
            DISCARD_RED_TINT_COLOR,
            DISCARD_RED_TINT_COLOR,
            DISCARD_RED_TINT_BLEND,
        )

        self.assertEqual(_discard_tint_brighten_overlay_band("red"), brighten_band)
        self.assertEqual(_discard_tint_base_overlay_bands("red"), (brighten_band, red_band))
        self.assertIsNone(_discard_tint_brighten_overlay_band("none"))

    def test_red_tint_turns_brown_when_all_sequences_through_tile_are_blocked(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[3],
            visible_counts_34_index=tuple([0, 0, 4] + [0] * 31),
        )
        tedashi = SimpleNamespace(called=False, tsumogiri=False)

        self.assertEqual(
            _discard_tile_tint_kind(
                tedashi,
                1,
                should_red_tint=True,
                visible_summary=visible_summary,
            ),
            "brown",
        )
        self.assertIn(1, visible_summary.blocked_sequence_tile34_index_set)

    def test_brown_tint_requires_all_sequences_through_tile_to_be_blocked(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[4],
            visible_counts_34_index=tuple([0, 0, 0, 4] + [0] * 30),
        )
        tedashi = SimpleNamespace(called=False, tsumogiri=False)

        self.assertEqual(
            _discard_tile_tint_kind(
                tedashi,
                4,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "none",
        )
        self.assertNotIn(4, visible_summary.blocked_sequence_tile34_index_set)
        self.assertNotIn(6, visible_summary.blocked_sequence_tile34_index_set)

    def test_brown_tint_does_not_mark_three_when_only_123_and_234_are_blocked(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[2],
            visible_counts_34_index=tuple([0, 4] + [0] * 32),
        )
        tedashi = SimpleNamespace(called=False, tsumogiri=False)

        self.assertEqual(
            _discard_tile_tint_kind(
                tedashi,
                2,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "none",
        )
        self.assertNotIn(2, visible_summary.blocked_sequence_tile34_index_set)

    def test_brown_tint_marks_tile_only_when_multiple_blockers_kill_every_sequence(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[4, 7],
            visible_counts_34_index=tuple([0, 0, 0, 4, 0, 0, 4] + [0] * 27),
        )
        tedashi = SimpleNamespace(called=False, tsumogiri=False)

        self.assertEqual(
            _discard_tile_tint_kind(
                tedashi,
                4,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "brown",
        )
        self.assertIn(4, visible_summary.blocked_sequence_tile34_index_set)
        self.assertIn(5, visible_summary.blocked_sequence_tile34_index_set)
        self.assertNotIn(2, visible_summary.blocked_sequence_tile34_index_set)

    def test_brown_blocked_sequence_is_scoped_per_suit(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[3],
            visible_counts_34_index=tuple([0, 0, 4] + [0] * 31),
        )
        tedashi = SimpleNamespace(called=False, tsumogiri=False)

        self.assertEqual(
            _discard_tile_tint_kind(
                tedashi,
                0,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "brown",
        )
        self.assertEqual(
            _discard_tile_tint_kind(
                tedashi,
                9,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "none",
        )
        self.assertNotIn(9, visible_summary.blocked_sequence_tile34_index_set)

    def test_four_visible_priority_beats_brown_when_both_apply(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[3, 5],
            visible_counts_34_index=tuple([0, 0, 4, 0, 4] + [0] * 29),
        )
        tedashi = SimpleNamespace(called=False, tsumogiri=False)

        self.assertEqual(
            _discard_tile_tint_kind(
                tedashi,
                2,
                should_red_tint=True,
                visible_summary=visible_summary,
            ),
            "four_visible",
        )

    def test_tedashi_four_visible_tint_no_longer_requires_red_tint(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[5],
            visible_counts_34_index=tuple([0, 0, 0, 0, 4] + [0] * 29),
        )
        tedashi = SimpleNamespace(called=False, tsumogiri=False)

        self.assertEqual(
            _discard_tile_tint_kind(
                tedashi,
                4,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "four_visible",
        )

    def test_tsumogiri_four_visible_tint_stays_none_without_red_tint(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[5],
            visible_counts_34_index=tuple([0, 0, 0, 0, 4] + [0] * 29),
        )
        tsumogiri = SimpleNamespace(called=False, tsumogiri=True)

        self.assertEqual(
            _discard_tile_tint_kind(
                tsumogiri,
                4,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "none",
        )

    def test_called_tedashi_still_gets_four_visible_tint(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[5],
            visible_counts_34_index=tuple([0, 0, 0, 0, 4] + [0] * 29),
        )
        called_tedashi = SimpleNamespace(called=True, tsumogiri=False)

        self.assertEqual(
            _discard_tile_tint_kind(
                called_tedashi,
                4,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "four_visible",
        )

    def test_called_tsumogiri_stays_non_tedashi_for_tint(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[5],
            visible_counts_34_index=tuple([0, 0, 0, 0, 4] + [0] * 29),
        )
        called_tsumogiri = SimpleNamespace(called=True, tsumogiri=True)

        self.assertEqual(
            _discard_tile_tint_kind(
                called_tsumogiri,
                4,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "none",
        )

    def test_draw_type_tsumogiri_overrides_inconsistent_tedashi_flag_for_tint(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[5],
            visible_counts_34_index=tuple([0, 0, 0, 0, 4] + [0] * 29),
        )
        inconsistent_tsumogiri = SimpleNamespace(
            called=False,
            tsumogiri=False,
            draw_type=DrawType.TSUMOGIRI,
        )

        self.assertEqual(
            _discard_tile_tint_kind(
                inconsistent_tsumogiri,
                4,
                should_red_tint=False,
                visible_summary=visible_summary,
            ),
            "none",
        )

    def test_self_hand_honor_visible_count_uses_visible_summary_count(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=tuple([0] * 27 + [3, 1, 0, 0, 0, 0, 0]),
        )

        self.assertEqual(_self_hand_honor_visible_count(31, visible_summary), 3)
        self.assertEqual(_self_hand_honor_visible_count(32, visible_summary), 1)

    def test_self_hand_honor_visible_count_ignores_suited_tiles(self) -> None:
        visible_summary = VisibleTileSummary(
            three_visible_tiles=[],
            four_visible_tiles=[],
            visible_counts_34_index=tuple([2] * 34),
        )

        self.assertIsNone(_self_hand_honor_visible_count(1, visible_summary))

    def test_self_hand_honor_visible_count_geometry_uses_top_right_with_small_offset(self) -> None:
        text_x, text_y = _self_hand_honor_visible_count_geometry(
            10.0,
            20.0,
            50.0,
            80.0,
            1.0,
        )

        self.assertEqual(text_x, 47.0)
        self.assertEqual(text_y, 23.0)


if __name__ == "__main__":
    unittest.main()
