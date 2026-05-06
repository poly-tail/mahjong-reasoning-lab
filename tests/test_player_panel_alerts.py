import unittest
from unittest.mock import Mock, patch

from app.main import build_player_score_diffs_by_seat
from capture.state import Discard, LAG_FLAG_UNCONFIRMED, Meld, RoundState
from logic.danger_suji import (
    _top_weighted_line_summaries,
    _format_suji_line_weight,
    build_opponent_suji_danger_profile,
    build_kamicha_no_lag_menzen_alert_score,
    build_latest_discard_push_alert_percentages,
    build_opponent_suji_panel_summary,
    build_tedashi_thinking_rise_alert,
)
from ui.table_renderer import (
    PLAYER_PANEL_BUTTON_LABELS,
    PLAYER_PANEL_SCORE_BUTTON_LABEL,
    PLAYER_ALERT_PURPLE,
    PLAYER_ALERT_RED,
    PLAYER_ALERT_YELLOW,
    PlayerAlertIndicator,
    _public_honor_tiles_below_three_visible,
    _play_player_panel_alert_sound_if_needed,
    _build_player_panel_alert_indicators_by_seat,
    _draw_public_honor_shortlist,
    _format_player_panel_line_summary_text,
    _format_player_panel_score_diff,
    _format_player_panel_remain_text,
    _normalize_player_score_diffs_by_seat,
    _normalize_opponent_suji_panel_summaries,
    _player_panel_alert_sound_tone,
    _player_panel_display_name,
    _player_panel_alert_sound_priority,
    _player_panel_remain_sound_level,
    _persist_player_push_alerts,
    _push_discard_marker_indices_by_seat,
    _push_marker_alerts_for_render,
    _player_panel_remain_text_color,
    _handle_detail_memo_save_shortcut,
    _ensure_detail_memo_widgets,
    _resolve_public_honor_shortlist_top,
    _self_discarded_public_honor_tiles,
    _split_player_panel_remain_text,
)


class PlayerPanelAlertTest(unittest.TestCase):
    class _DummyTkWidget:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.bindings: dict[str, object] = {}
            self.state = kwargs.get("state", "normal")
            self.configured: dict[str, object] = {}

        def grid(self, *args, **kwargs) -> None:
            self.grid_args = args
            self.grid_kwargs = kwargs

        def configure(self, **kwargs) -> None:
            self.configured.update(kwargs)
            if "state" in kwargs:
                self.state = kwargs["state"]

        def bind(self, sequence: str, callback) -> None:
            self.bindings[sequence] = callback

        def cget(self, key: str):
            if key == "state":
                return self.state
            return self.configured.get(key, self.kwargs.get(key))

        def yview(self, *args, **kwargs) -> None:
            self.yview_args = args
            self.yview_kwargs = kwargs

    class _DummyTkFrame(_DummyTkWidget):
        def grid_columnconfigure(self, *args, **kwargs) -> None:
            self.grid_columnconfigure_args = (args, kwargs)

        def grid_rowconfigure(self, *args, **kwargs) -> None:
            self.grid_rowconfigure_args = (args, kwargs)

    class _DummyTkScrollbar(_DummyTkWidget):
        def set(self, *args, **kwargs) -> None:
            self.set_args = args
            self.set_kwargs = kwargs

    class _DummyFont:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def metrics(self, _key: str) -> int:
            return 10

    class _DummyCanvas:
        def __init__(self) -> None:
            self.text_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
            self.image_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def create_text(self, *args, **kwargs) -> int:
            self.text_calls.append((args, kwargs))
            return len(self.text_calls)

        def create_image(self, *args, **kwargs) -> int:
            self.image_calls.append((args, kwargs))
            return len(self.image_calls)

    class _DummyTileImage:
        def width(self) -> int:
            return 10

        def height(self) -> int:
            return 16

    @staticmethod
    def _honor_discard(tile_37: int, *, called: bool = False) -> Discard:
        return Discard(
            tile_136=108 + (int(tile_37) - 31) * 4,
            tile_34=int(tile_37) - 4,
            tile_37=int(tile_37),
            called=called,
        )

    def test_player_panel_uses_only_three_configured_buttons(self) -> None:
        self.assertEqual(
            PLAYER_PANEL_BUTTON_LABELS,
            ("DETAIL", "STATUS", "プレイヤー補正"),
        )

    def test_score_section_uses_dedicated_condition_button_label(self) -> None:
        self.assertEqual(PLAYER_PANEL_SCORE_BUTTON_LABEL, "条件表示")

    def test_score_diff_builder_uses_self_relative_gaps(self) -> None:
        round_state = RoundState()
        round_state.scores = [25000, 28900, 13000, 25000]

        self.assertEqual(
            build_player_score_diffs_by_seat(round_state),
            {
                3: 0,
                2: -12000,
                1: 3900,
            },
        )

    def test_kamicha_no_lag_menzen_alert_score_ignores_missing_tile37(self) -> None:
        round_state = RoundState()
        discard = Discard(
            tile_136=16,
            tsumogiri=False,
            round_discard_index=0,
        )
        discard.tile_37 = None
        round_state.discards[1].append(discard)

        self.assertEqual(build_kamicha_no_lag_menzen_alert_score(round_state, 2), 0)

    def test_kamicha_no_lag_menzen_alert_score_ignores_riseki_completion_discard(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=4,
                tile_34=1,
                tile_37=2,
                tsumogiri=True,
                is_tsumogiri_estimated=True,
                lagged=LAG_FLAG_UNCONFIRMED,
                round_discard_index=0,
            )
        )

        self.assertEqual(build_kamicha_no_lag_menzen_alert_score(round_state, 2), 0)

    def test_score_diff_normalization_accepts_numeric_strings(self) -> None:
        self.assertEqual(
            _normalize_player_score_diffs_by_seat(
                {
                    "3": "0",
                    2: "-12000",
                    1: 3900.8,
                    0: 999,
                    "x": 123,
                }
            ),
            {
                3: 0,
                2: -12000,
                1: 3900,
            },
        )

    def test_score_diff_formatting_adds_sign_and_grouping(self) -> None:
        self.assertEqual(_format_player_panel_score_diff(3900), "+3,900")
        self.assertEqual(_format_player_panel_score_diff(-12000), "-12,000")
        self.assertEqual(_format_player_panel_score_diff(0), "0")

    def test_player_panel_remain_text_color_uses_no_temp_thresholds_only(self) -> None:
        self.assertEqual(
            _player_panel_remain_text_color(
                {
                    "denominator_count": 3.0,
                    "denominator_count_without_temporary_safe": 6.0,
                },
                "#ffffff",
            ),
            PLAYER_ALERT_PURPLE,
        )
        self.assertEqual(
            _player_panel_remain_text_color(
                {
                    "denominator_count": 3.0,
                    "denominator_count_without_temporary_safe": 12.0,
                },
                "#ffffff",
            ),
            PLAYER_ALERT_YELLOW,
        )
        self.assertEqual(
            _player_panel_remain_text_color(
                {
                    "denominator_count": 20.0,
                    "denominator_count_without_temporary_safe": 9.0,
                },
                "#ffffff",
            ),
            PLAYER_ALERT_RED,
        )
        self.assertEqual(
            _player_panel_remain_text_color(
                {
                    "denominator_count": 7.0,
                    "denominator_count_without_temporary_safe": 12.1,
                },
                "#ffffff",
            ),
            "#ffffff",
        )
        self.assertEqual(
            _player_panel_remain_text_color(
                {"denominator_count": 7.0},
                "#ffffff",
            ),
            "#ffffff",
        )

    def test_public_honor_shortlist_uses_discards_melds_and_dora(self) -> None:
        discard_map = {
            0: [
                self._honor_discard(31),
                self._honor_discard(31),
                self._honor_discard(32),
            ],
            1: [
                self._honor_discard(32),
                self._honor_discard(33, called=True),
            ],
            2: [],
            3: [],
        }
        melds_by_player = {
            0: [],
            1: [],
            2: [
                Meld(
                    who=2,
                    raw_m=0,
                    meld_type="pon",
                    tiles_37=[33, 34, 34],
                )
            ],
            3: [],
        }

        shortlist = _public_honor_tiles_below_three_visible(discard_map, melds_by_player, (33,))

        self.assertEqual(shortlist, (31, 32, 33, 34, 35, 36, 37))

    def test_public_honor_shortlist_keeps_all_honor_kinds_below_three_visible(self) -> None:
        discard_map = {
            0: [self._honor_discard(31), self._honor_discard(31)],
            1: [],
            2: [],
            3: [],
        }

        shortlist = _public_honor_tiles_below_three_visible(
            discard_map,
            {0: [], 1: [], 2: [], 3: []},
            (),
        )

        self.assertEqual(shortlist, (31, 32, 33, 34, 35, 36, 37))

    def test_public_honor_shortlist_top_biases_toward_self_meld_side(self) -> None:
        resolved_top = _resolve_public_honor_shortlist_top((0.0, 100.0, 40.0, 220.0), 40.0)

        self.assertGreater(resolved_top, 140.0)
        self.assertLess(resolved_top, 180.0)

    def test_self_discarded_public_honor_tiles_marks_any_discard_history_tiles(self) -> None:
        discard_map = {
            0: [
                self._honor_discard(31),
                self._honor_discard(33, called=True),
            ],
            1: [
                self._honor_discard(32),
            ],
            2: [],
            3: [],
        }

        discarded_tiles = _self_discarded_public_honor_tiles(
            discard_map,
            (31, 32, 33, 34),
        )

        self.assertEqual(discarded_tiles, (31, 32, 33))

    def test_public_honor_shortlist_dims_self_discarded_tiles(self) -> None:
        canvas = self._DummyCanvas()
        tile_image_requests: list[tuple[int, bool]] = []

        def _fake_player_panel_tile_rank_image(
            _canvas,
            tile_37: int,
            *,
            dimmed: bool = False,
        ):
            tile_image_requests.append((int(tile_37), bool(dimmed)))
            return self._DummyTileImage()

        with (
            patch("ui.table_renderer._fit_text_to_width", side_effect=lambda *_args, **_kwargs: "字牌2見え以下"),
            patch("ui.table_renderer.tkfont.Font", self._DummyFont),
            patch(
                "ui.table_renderer._player_panel_tile_rank_image",
                side_effect=_fake_player_panel_tile_rank_image,
            ),
        ):
            _draw_public_honor_shortlist(
                canvas,
                0.0,
                0.0,
                (31, 32),
                "#9fb0c6",
                max_text_width=40.0,
                dim_tile_ids=(31,),
            )

        self.assertIn((31, True), tile_image_requests)
        self.assertIn((32, False), tile_image_requests)
        self.assertEqual(len(canvas.image_calls), 2)

    def test_detail_memo_save_shortcut_invokes_background_save_and_stops_propagation(self) -> None:
        canvas = object()

        with patch("ui.table_renderer._save_detail_memo_in_background", return_value=True) as mock_save:
            result = _handle_detail_memo_save_shortcut(canvas)

        mock_save.assert_called_once_with(canvas)
        self.assertEqual(result, "break")

    def test_detail_memo_widgets_bind_ctrl_s_shortcuts(self) -> None:
        canvas = type("DummyCanvas", (), {})()

        with patch("ui.table_renderer.tkinter.Frame", self._DummyTkFrame):
            with patch("ui.table_renderer.tkinter.Label", self._DummyTkWidget):
                with patch("ui.table_renderer.tkinter.Text", self._DummyTkWidget):
                    with patch("ui.table_renderer.tkinter.Scrollbar", self._DummyTkScrollbar):
                        with patch("ui.table_renderer.tkinter.Button", self._DummyTkWidget):
                            _ensure_detail_memo_widgets(canvas)

        text_widget = canvas.detail_memo_text_widget
        self.assertIn("<Control-s>", text_widget.bindings)
        self.assertIn("<Control-S>", text_widget.bindings)

        with patch("ui.table_renderer._save_detail_memo_in_background", return_value=True) as mock_save:
            result = text_widget.bindings["<Control-s>"](None)

        mock_save.assert_called_once_with(canvas)
        self.assertEqual(result, "break")

    def test_summary_tracks_no_temp_remain_alongside_current_remain(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=0,
                tile_34=0,
                tsumogiri=False,
                round_discard_index=0,
            )
        )
        round_state.discards[2].append(
            Discard(
                tile_136=4,
                tile_34=1,
                tsumogiri=True,
                round_discard_index=1,
            )
        )

        summary = build_opponent_suji_panel_summary(round_state, 1)

        self.assertAlmostEqual(summary.denominator_count, 16.0)
        self.assertAlmostEqual(summary.denominator_count_without_temporary_safe or 0.0, 16.75)
        self.assertGreater(
            summary.denominator_count_without_temporary_safe or 0.0,
            summary.denominator_count,
        )

    def test_no_temp_remain_decreases_when_target_seat_tsumogiri_suji_anchor_is_added(self) -> None:
        empty_summary = build_opponent_suji_panel_summary(RoundState(), 1)
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=0,
                tile_34=0,
                tsumogiri=True,
                round_discard_index=0,
            )
        )

        summary = build_opponent_suji_panel_summary(round_state, 1)

        self.assertLess(summary.denominator_count, empty_summary.denominator_count)
        self.assertLess(
            summary.denominator_count_without_temporary_safe or 0.0,
            empty_summary.denominator_count_without_temporary_safe or 0.0,
        )

    def test_remain_text_formats_current_and_no_temp_counts(self) -> None:
        remain_text = _format_player_panel_remain_text(
            {
                "denominator_count": 6.0,
                "denominator_count_without_temporary_safe": 8.0,
            }
        )

        self.assertEqual(remain_text, "Remain: 6/8")

    def test_remain_text_rounds_display_to_one_decimal_place(self) -> None:
        remain_text = _format_player_panel_remain_text(
            {
                "denominator_count": 16.75,
                "denominator_count_without_temporary_safe": 8.24,
            }
        )

        self.assertEqual(remain_text, "Remain: 16.8/8.2")

    def test_remain_text_shows_loading_placeholder(self) -> None:
        self.assertEqual(
            _format_player_panel_remain_text(
                {
                    "is_loading": True,
                    "denominator_count": 16.8,
                    "denominator_count_without_temporary_safe": 8.2,
                }
            ),
            "Remain: ...",
        )

    def test_split_remain_text_returns_label_and_value(self) -> None:
        self.assertEqual(
            _split_player_panel_remain_text(
                {
                    "denominator_count": 16.75,
                    "denominator_count_without_temporary_safe": 8.24,
                }
            ),
            ("Remain:", "16.8/8.2"),
        )

    def test_line_summary_text_uses_mspz_format_and_same_suit_remain(self) -> None:
        line_text = _format_player_panel_line_summary_text(
            {
                "rank_text": "1.",
                "left_tile_label": "1m",
                "right_tile_label": "4m",
                "suit_label": "m",
                "percent_text": "6%",
                "suit_remaining_count_text": "6",
            }
        )

        self.assertEqual(line_text, "1. 1-4m m6 6%")

    def test_line_summary_text_can_drop_rank_and_percent_for_tight_widths(self) -> None:
        line_text = _format_player_panel_line_summary_text(
            {
                "rank_text": "2.",
                "left_tile_label": "4p",
                "right_tile_label": "7p",
                "suit_label": "p",
                "percent_text": "20%",
                "suit_remaining_count_text": "3.2",
            },
            include_rank=False,
            include_percent=False,
        )

        self.assertEqual(line_text, "4-7p p3.2")

    def test_panel_summary_exposes_structured_line_rows_with_suit_remaining_counts(self) -> None:
        summary = build_opponent_suji_panel_summary(RoundState(), 1)

        self.assertEqual(
            summary.top_line_labels,
            ("3-6m m6 15.1%", "3-6p p6 15.1%", "3-6s s6 15.1%"),
        )
        self.assertEqual(
            tuple(line_summary.suit_label for line_summary in summary.top_line_summaries),
            ("m", "p", "s"),
        )
        self.assertEqual(summary.top_line_summaries[0].rank_text, "1.")
        self.assertEqual(summary.top_line_summaries[0].left_tile_label, "3m")
        self.assertEqual(summary.top_line_summaries[0].right_tile_label, "6m")
        self.assertEqual(summary.top_line_summaries[0].suit_label, "m")
        self.assertEqual(summary.top_line_summaries[0].line_weight_text, "1")
        self.assertEqual(summary.top_line_summaries[0].percent_text, "15.1%")
        self.assertEqual(summary.top_line_summaries[0].suit_remaining_count_text, "6")

    def test_panel_summary_limits_tile_rank_rows_to_three(self) -> None:
        summary = build_opponent_suji_panel_summary(RoundState(), 1)

        self.assertLessEqual(len(summary.top_tile_rank_labels), 3)

    def test_panel_summary_backfills_missing_third_line_with_fractional_remaining_line(self) -> None:
        profile = build_opponent_suji_danger_profile(RoundState(), 1)

        line_summaries = _top_weighted_line_summaries(
            profile,
            {
                (0, 3, 6): 1.0,
                (0, 4, 7): 0.7,
                (1, 3, 6): 1.0,
            },
        )

        self.assertEqual(len(line_summaries), 3)
        self.assertEqual(
            tuple(summary.line_weight_text for summary in line_summaries),
            ("1", "1", "0.7"),
        )
        self.assertEqual(line_summaries[2].left_tile_label, "4m")
        self.assertEqual(line_summaries[2].right_tile_label, "7m")
        self.assertEqual(line_summaries[2].suit_remaining_count_text, "1.7")

    def test_panel_summary_normalization_accepts_structured_line_rows(self) -> None:
        normalized = _normalize_opponent_suji_panel_summaries(
            {
                1: {
                    "top_line_summaries": (
                        {
                            "rank_text": "1.",
                            "left_tile_label": "1m",
                            "right_tile_label": "4m",
                            "suit_label": "m",
                            "line_weight_text": "0.7",
                            "percent_text": "20%",
                            "suit_remaining_count_text": "3.2",
                        },
                    ),
                }
            }
        )

        self.assertEqual(
            normalized[1]["top_line_summaries"],
            (
                {
                    "rank_text": "1.",
                    "left_tile_label": "1m",
                    "right_tile_label": "4m",
                    "suit_label": "m",
                    "line_weight_text": "0.7",
                    "percent_text": "20%",
                    "suit_remaining_count_text": "3.2",
                },
            ),
        )

    def test_panel_summary_normalization_truncates_tile_rank_rows_to_three(self) -> None:
        normalized = _normalize_opponent_suji_panel_summaries(
            {
                1: {
                    "top_tile_rank_labels": ("1. a", "2. b", "3. c", "4. d"),
                }
            }
        )

        self.assertEqual(
            normalized[1]["top_tile_rank_labels"],
            ("1. a", "2. b", "3. c"),
        )

    def test_panel_summary_normalization_accepts_new_line_labels_with_suit_remain(self) -> None:
        normalized = _normalize_opponent_suji_panel_summaries(
            {
                1: {
                    "top_line_labels": ("1-4m m6 20%",),
                }
            }
        )

        self.assertEqual(
            normalized[1]["top_line_summaries"],
            (
                {
                    "rank_text": "1.",
                    "left_tile_label": "1m",
                    "right_tile_label": "4m",
                    "suit_label": "m",
                    "line_weight_text": "",
                    "percent_text": "20%",
                    "suit_remaining_count_text": "6",
                },
            ),
        )

    def test_panel_summary_normalization_falls_back_to_legacy_line_labels(self) -> None:
        normalized = _normalize_opponent_suji_panel_summaries(
            {
                1: {
                    "top_line_labels": ("1-4m 0.7 20%",),
                }
            }
        )

        self.assertEqual(
            normalized[1]["top_line_summaries"],
            (
                {
                    "rank_text": "1.",
                    "left_tile_label": "1m",
                    "right_tile_label": "4m",
                    "suit_label": "m",
                    "line_weight_text": "0.7",
                    "percent_text": "20%",
                    "suit_remaining_count_text": "",
                },
            ),
        )

    def test_player_panel_display_name_hides_fallback_opponent_labels(self) -> None:
        self.assertEqual(_player_panel_display_name(1, "SHIMO"), "")
        self.assertEqual(_player_panel_display_name(2, "TOIMEN"), "")
        self.assertEqual(_player_panel_display_name(3, "KAMI"), "")

    def test_player_panel_display_name_keeps_real_names(self) -> None:
        self.assertEqual(_player_panel_display_name(1, "Alice"), "Alice")
        self.assertEqual(_player_panel_display_name(2, "TOIMEN-san"), "TOIMEN-san")

    def test_player_panel_alert_indicators_expose_stable_keys(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 5.5,
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 9.2,
                    "is_current": True,
                    "discard_index": 7,
                    "tile_label": "5p",
                }
            },
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("remain_red", "push:7"),
        )

    def test_player_panel_push_indicator_uses_payload_threshold_percent(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 9.0,
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 6.2,
                    "threshold_percent": 6.0,
                    "is_current": False,
                    "discard_index": 7,
                    "tile_label": "5p",
                }
            },
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("push:7",),
        )

    def test_menzen_alert_score_counts_distinct_no_lag_kamicha_tiles(self) -> None:
        round_state = RoundState()
        round_state.discards[0].extend(
            [
                Discard(
                    tile_136=4,
                    tile_34=1,
                    round_discard_index=0,
                ),
                Discard(
                    tile_136=8,
                    tile_34=2,
                    round_discard_index=1,
                ),
                Discard(
                    tile_136=9,
                    tile_34=2,
                    round_discard_index=2,
                ),
                Discard(
                    tile_136=16,
                    tile_34=4,
                    round_discard_index=3,
                ),
                Discard(
                    tile_136=17,
                    tile_34=4,
                    round_discard_index=4,
                    lagged=LAG_FLAG_UNCONFIRMED,
                ),
                Discard(
                    tile_136=24,
                    tile_34=6,
                    round_discard_index=5,
                    called=True,
                ),
                Discard(
                    tile_136=0,
                    tile_34=0,
                    round_discard_index=6,
                ),
                Discard(
                    tile_136=108,
                    tile_34=27,
                    round_discard_index=7,
                ),
            ]
        )

        self.assertEqual(build_kamicha_no_lag_menzen_alert_score(round_state, 1), 7)
        self.assertEqual(build_opponent_suji_panel_summary(round_state, 1).menzen_alert_score, 7)

    def test_menzen_alert_score_excludes_lagged_kamicha_source_discard(self) -> None:
        round_state = RoundState()
        round_state.discards[0].append(
            Discard(
                tile_136=4,
                tile_34=1,
                tile_37=2,
                lagged=LAG_FLAG_UNCONFIRMED,
                round_discard_index=0,
            )
        )

        self.assertEqual(build_kamicha_no_lag_menzen_alert_score(round_state, 1), 0)
        self.assertEqual(build_opponent_suji_panel_summary(round_state, 1).menzen_alert_score, 0)

    def test_player_panel_menzen_alert_uses_threshold_colors(self) -> None:
        yellow_indicators = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 14.0,
                    "menzen_alert_score": 3,
                }
            },
            {},
        )
        red_indicators = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 9.0,
                    "menzen_alert_score": 5,
                }
            },
            {},
        )

        self.assertEqual(
            tuple(indicator.key for indicator in yellow_indicators[1]),
            ("menzen_yellow",),
        )
        self.assertEqual(
            tuple(indicator.key for indicator in red_indicators[1]),
            ("menzen_red",),
        )
        self.assertEqual(red_indicators[1][0].color, PLAYER_ALERT_RED)

    def test_player_panel_menzen_red_turns_purple_when_no_temp_remain_is_below_13(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 9.0,
                    "denominator_count_without_temporary_safe": 12.9,
                    "menzen_alert_score": 5,
                }
            },
            {},
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("menzen_red",),
        )
        self.assertEqual(indicators_by_seat[1][0].color, PLAYER_ALERT_PURPLE)

    def test_player_panel_menzen_red_stays_red_when_no_temp_remain_is_13_or_more(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 9.0,
                    "denominator_count_without_temporary_safe": 13.0,
                    "menzen_alert_score": 5,
                }
            },
            {},
        )

        self.assertEqual(indicators_by_seat[1][0].color, PLAYER_ALERT_RED)

    def test_riichi_player_keeps_only_remain_alerts(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 5.5,
                    "menzen_alert_score": 5,
                    "hand_pattern_alert_level": 2,
                    "suit_bias_alert": True,
                    "tedashi_thinking_rise_alert": True,
                    "is_riichi": True,
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 12.3,
                    "is_current": True,
                    "discard_index": 7,
                    "tile_label": "5p",
                }
            },
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("remain_red",),
        )

    def test_loading_summary_suppresses_player_panel_alerts(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "is_loading": True,
                    "denominator_count": 0.0,
                    "menzen_alert_score": 5,
                    "hand_pattern_alert_level": 2,
                    "tedashi_thinking_rise_alert": True,
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 12.3,
                    "is_current": True,
                    "discard_index": 7,
                    "tile_label": "5p",
                }
            },
        )

        self.assertEqual(indicators_by_seat[1], ())

    def test_player_panel_alert_sound_uses_precomputed_indicators(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_player_panel_alert_keys_by_seat = {
                    1: (),
                    2: (),
                    3: (),
                }
                self.last_player_panel_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()
        precomputed_indicators = {
            1: (
                PlayerAlertIndicator(
                    color=PLAYER_ALERT_RED,
                    label="Remain 5.5",
                    key="remain_red",
                ),
            ),
        }

        with patch("ui.table_renderer.winsound", None), patch(
            "ui.table_renderer._build_player_panel_alert_indicators_by_seat",
            side_effect=AssertionError("synchronous alert rebuild should not run"),
        ):
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {1: {"denominator_count": 5.5}},
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )

        self.assertEqual(canvas.bell_calls, 1)
        self.assertEqual(canvas.last_player_panel_alert_keys_by_seat[1], ("remain_red",))

    def test_player_panel_alert_sound_stays_silent_when_same_priority_alert_key_is_added(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_player_panel_alert_keys_by_seat = {
                    1: ("remain_yellow",),
                    2: (),
                    3: (),
                }
                self.last_player_panel_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()
        precomputed_indicators = {
            1: (
                PlayerAlertIndicator(
                    color=PLAYER_ALERT_YELLOW,
                    label="Remain 7.5",
                    key="remain_yellow",
                ),
                PlayerAlertIndicator(
                    color=PLAYER_ALERT_YELLOW,
                    label="思考時間聴牌近",
                    key="tenpai_near",
                ),
            ),
        }

        with patch("ui.table_renderer.winsound", None):
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {1: {"denominator_count": 7.5}},
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )

        self.assertEqual(canvas.bell_calls, 0)
        self.assertEqual(
            canvas.last_player_panel_alert_keys_by_seat[1],
            ("remain_yellow", "tenpai_near"),
        )

    def test_player_panel_alert_sound_fires_when_alert_priority_upgrades(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_player_panel_alert_keys_by_seat = {
                    1: ("remain_yellow",),
                    2: (),
                    3: (),
                }
                self.last_player_panel_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()
        precomputed_indicators = {
            1: (
                PlayerAlertIndicator(
                    color=PLAYER_ALERT_RED,
                    label="Remain 5.5",
                    key="remain_red",
                ),
            ),
        }

        with patch("ui.table_renderer.winsound", None):
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {1: {"denominator_count": 5.5}},
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )

        self.assertEqual(canvas.bell_calls, 1)
        self.assertEqual(canvas.last_player_panel_alert_keys_by_seat[1], ("remain_red",))

    def test_player_panel_remain_sound_fires_only_when_thresholds_are_crossed(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_player_panel_alert_keys_by_seat = {
                    1: (),
                    2: (),
                    3: (),
                }
                self.last_player_panel_remain_sound_level_by_seat = {
                    1: 0,
                    2: 0,
                    3: 0,
                }
                self.last_player_panel_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()
        precomputed_indicators = {
            1: (
                PlayerAlertIndicator(
                    color=PLAYER_ALERT_YELLOW,
                    label="Remain 18/11.8",
                    key="remain_yellow",
                ),
            ),
        }

        with patch("ui.table_renderer.winsound", None), patch(
            "ui.table_renderer.time.monotonic",
            side_effect=[100.0, 101.0, 102.0],
        ):
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 18.0,
                        "denominator_count_without_temporary_safe": 11.8,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 17.5,
                        "denominator_count_without_temporary_safe": 11.4,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 16.0,
                        "denominator_count_without_temporary_safe": 8.9,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 15.5,
                        "denominator_count_without_temporary_safe": 8.4,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 14.0,
                        "denominator_count_without_temporary_safe": 6.0,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 13.5,
                        "denominator_count_without_temporary_safe": 5.7,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )

        self.assertEqual(canvas.bell_calls, 3)
        self.assertEqual(canvas.last_player_panel_remain_sound_level_by_seat[1], 3)

    def test_player_panel_remain_sound_can_fire_again_after_recovering_above_threshold(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_player_panel_alert_keys_by_seat = {
                    1: (),
                    2: (),
                    3: (),
                }
                self.last_player_panel_remain_sound_level_by_seat = {
                    1: 0,
                    2: 0,
                    3: 0,
                }
                self.last_player_panel_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()
        precomputed_indicators = {
            1: (
                PlayerAlertIndicator(
                    color=PLAYER_ALERT_YELLOW,
                    label="Remain 18/11.9",
                    key="remain_yellow",
                ),
            ),
        }

        with patch("ui.table_renderer.winsound", None), patch(
            "ui.table_renderer.time.monotonic",
            side_effect=[100.0, 101.0],
        ):
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 18.0,
                        "denominator_count_without_temporary_safe": 11.9,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 19.0,
                        "denominator_count_without_temporary_safe": 12.5,
                    }
                },
                {1: {}},
                alert_indicators_by_seat={1: ()},
            )
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 17.0,
                        "denominator_count_without_temporary_safe": 11.7,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=precomputed_indicators,
            )

        self.assertEqual(canvas.bell_calls, 2)
        self.assertEqual(canvas.last_player_panel_remain_sound_level_by_seat[1], 1)

    def test_player_panel_alert_sound_rate_limits_rapid_retriggers(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_player_panel_alert_keys_by_seat = {
                    1: (),
                    2: (),
                    3: (),
                }
                self.last_player_panel_remain_sound_level_by_seat = {
                    1: 0,
                    2: 0,
                    3: 0,
                }
                self.last_player_panel_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()
        yellow_indicators = {
            1: (
                PlayerAlertIndicator(
                    color=PLAYER_ALERT_YELLOW,
                    label="Remain 18/11.8",
                    key="remain_yellow",
                ),
            ),
        }

        with patch("ui.table_renderer.winsound", None), patch(
            "ui.table_renderer.time.monotonic",
            side_effect=[100.0, 100.3],
        ):
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 18.0,
                        "denominator_count_without_temporary_safe": 11.8,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=yellow_indicators,
            )
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 19.0,
                        "denominator_count_without_temporary_safe": 12.5,
                    }
                },
                {1: {}},
                alert_indicators_by_seat={1: ()},
            )
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {
                    1: {
                        "denominator_count": 17.0,
                        "denominator_count_without_temporary_safe": 11.7,
                    }
                },
                {1: {}},
                alert_indicators_by_seat=yellow_indicators,
            )

        self.assertEqual(canvas.bell_calls, 1)

    def test_menzen_alert_score_resets_to_zero_after_target_open_meld(self) -> None:
        round_state = RoundState()
        round_state.discards[0].extend(
            [
                Discard(
                    tile_136=4,
                    tile_34=1,
                    round_discard_index=0,
                ),
                Discard(
                    tile_136=8,
                    tile_34=2,
                    round_discard_index=1,
                ),
            ]
        )
        round_state.melds[1].append(
            Meld(
                who=1,
                raw_m=0,
                meld_type="pon",
                from_who=3,
                is_open=True,
                tiles_136=[48, 49, 50],
                called_tile_id=48,
                called_index=0,
            )
        )

        self.assertEqual(build_kamicha_no_lag_menzen_alert_score(round_state, 1), 0)
        self.assertEqual(build_opponent_suji_panel_summary(round_state, 1).menzen_alert_score, 0)

    def test_tedashi_thinking_rise_alert_uses_latest_three_tedashi(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(
                    tile_136=0,
                    tile_34=0,
                    tsumogiri=False,
                    thinking_time_ms=600.0,
                    thinking_time_source="draw",
                    round_discard_index=0,
                ),
                Discard(
                    tile_136=4,
                    tile_34=1,
                    tsumogiri=True,
                    thinking_time_ms=1400.0,
                    thinking_time_source="draw",
                    round_discard_index=1,
                ),
                Discard(
                    tile_136=8,
                    tile_34=2,
                    tsumogiri=False,
                    thinking_time_ms=900.0,
                    thinking_time_source="draw",
                    round_discard_index=2,
                ),
                Discard(
                    tile_136=12,
                    tile_34=3,
                    tsumogiri=False,
                    thinking_time_ms=1200.0,
                    thinking_time_source="call",
                    round_discard_index=3,
                ),
                Discard(
                    tile_136=16,
                    tile_34=4,
                    tsumogiri=False,
                    thinking_time_ms=1300.0,
                    thinking_time_source="draw",
                    round_discard_index=4,
                ),
            ]
        )

        self.assertTrue(build_tedashi_thinking_rise_alert(round_state, 1))
        self.assertTrue(build_opponent_suji_panel_summary(round_state, 1).tedashi_thinking_rise_alert)

    def test_tedashi_thinking_rise_alert_requires_strict_increase(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(
                    tile_136=0,
                    tile_34=0,
                    tsumogiri=False,
                    thinking_time_ms=700.0,
                    thinking_time_source="draw",
                    round_discard_index=0,
                ),
                Discard(
                    tile_136=4,
                    tile_34=1,
                    tsumogiri=False,
                    thinking_time_ms=700.0,
                    thinking_time_source="draw",
                    round_discard_index=1,
                ),
                Discard(
                    tile_136=8,
                    tile_34=2,
                    tsumogiri=False,
                    thinking_time_ms=900.0,
                    thinking_time_source="draw",
                    round_discard_index=2,
                ),
            ]
        )

        self.assertFalse(build_tedashi_thinking_rise_alert(round_state, 1))

    def test_tedashi_thinking_rise_alert_ignores_riseki_completion_discards(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(
                    tile_136=0,
                    tile_34=0,
                    tsumogiri=False,
                    thinking_time_ms=600.0,
                    thinking_time_source="draw",
                    round_discard_index=0,
                ),
                Discard(
                    tile_136=4,
                    tile_34=1,
                    tsumogiri=True,
                    is_tsumogiri_estimated=True,
                    thinking_time_ms=5000.0,
                    thinking_time_source="draw",
                    round_discard_index=1,
                ),
                Discard(
                    tile_136=8,
                    tile_34=2,
                    tsumogiri=False,
                    thinking_time_ms=900.0,
                    thinking_time_source="draw",
                    round_discard_index=2,
                ),
                Discard(
                    tile_136=12,
                    tile_34=3,
                    tsumogiri=False,
                    thinking_time_ms=1200.0,
                    thinking_time_source="draw",
                    round_discard_index=3,
                ),
            ]
        )

        self.assertTrue(build_tedashi_thinking_rise_alert(round_state, 1))

    def test_player_panel_tenpai_near_alert_uses_yellow_indicator(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 9.0,
                    "tedashi_thinking_rise_alert": True,
                }
            },
            {},
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("tenpai_near",),
        )
        self.assertEqual(indicators_by_seat[1][0].label, "思考時間聴牌近")

    def test_player_panel_tenpai_near_alert_requires_remain_14_or_less(self) -> None:
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {
                1: {
                    "denominator_count": 14.1,
                    "tedashi_thinking_rise_alert": True,
                }
            },
            {},
        )

        self.assertEqual(indicators_by_seat[1], ())

    def test_push_alert_persists_for_about_three_turns(self) -> None:
        persisted_alerts = _persist_player_push_alerts(
            {
                1: {
                    "seat": 1,
                    "percentage": 0.0,
                    "tile_label": "",
                    "discard_index": None,
                    "is_current": False,
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 9.2,
                    "tile_label": "5p",
                    "discard_index": 7,
                    "is_current": True,
                }
            },
            18,
        )

        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {1: {"denominator_count": 9.0}},
            persisted_alerts,
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("push:7",),
        )

    def test_push_alert_expires_after_persist_window(self) -> None:
        persisted_alerts = _persist_player_push_alerts(
            {
                1: {
                    "seat": 1,
                    "percentage": 0.0,
                    "tile_label": "",
                    "discard_index": None,
                    "is_current": False,
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 9.2,
                    "tile_label": "5p",
                    "discard_index": 7,
                    "is_current": True,
                }
            },
            20,
        )

        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {1: {"denominator_count": 9.0}},
            persisted_alerts,
        )

        self.assertEqual(indicators_by_seat[1], ())

    def test_new_current_push_alert_replaces_older_latched_one(self) -> None:
        persisted_alerts = _persist_player_push_alerts(
            {
                1: {
                    "seat": 1,
                    "percentage": 12.3,
                    "tile_label": "7m",
                    "discard_index": 10,
                    "is_current": True,
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 9.2,
                    "tile_label": "5p",
                    "discard_index": 7,
                    "is_current": False,
                }
            },
            10,
        )

        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {1: {"denominator_count": 9.0}},
            persisted_alerts,
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("push:10",),
        )

    def test_push_release_replaces_latched_push_when_tedashi_genbutsu_appears(self) -> None:
        persisted_alerts = _persist_player_push_alerts(
            {
                1: {
                    "seat": 1,
                    "percentage": 0.0,
                    "tile_label": "3m",
                    "discard_index": 10,
                    "is_current": True,
                    "exact_safe_target_seats": (0,),
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 12.3,
                    "tile_label": "7m",
                    "discard_index": 7,
                    "is_current": False,
                    "kind": "push",
                    "target_seats": (0,),
                }
            },
            10,
        )

        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {1: {"denominator_count": 9.0}},
            persisted_alerts,
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("push_release:10",),
        )
        self.assertEqual(indicators_by_seat[1][0].color, "#22c55e")

    def test_push_release_persists_for_about_three_turns(self) -> None:
        persisted_alerts = _persist_player_push_alerts(
            {
                1: {
                    "seat": 1,
                    "percentage": 0.0,
                    "tile_label": "",
                    "discard_index": None,
                    "is_current": False,
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 0.0,
                    "tile_label": "3m",
                    "discard_index": 10,
                    "is_current": True,
                    "kind": "release",
                    "target_seats": (0,),
                }
            },
            21,
        )

        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {1: {"denominator_count": 9.0}},
            persisted_alerts,
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("push_release:10",),
        )

    def test_new_current_push_replaces_existing_release(self) -> None:
        persisted_alerts = _persist_player_push_alerts(
            {
                1: {
                    "seat": 1,
                    "percentage": 11.1,
                    "tile_label": "8s",
                    "discard_index": 15,
                    "is_current": True,
                    "target_seats": (0,),
                }
            },
            {
                1: {
                    "seat": 1,
                    "percentage": 0.0,
                    "tile_label": "3m",
                    "discard_index": 10,
                    "is_current": False,
                    "kind": "release",
                    "target_seats": (0,),
                }
            },
            15,
        )

        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {1: {"denominator_count": 9.0}},
            persisted_alerts,
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("push:15",),
        )

    def test_push_alert_key_uses_color_based_sound_priority(self) -> None:
        self.assertEqual(_player_panel_alert_sound_priority("push:7"), 3)
        self.assertEqual(_player_panel_alert_sound_priority("push_release:10"), 1)
        self.assertEqual(_player_panel_alert_sound_priority("remain_purple"), 3)
        self.assertEqual(_player_panel_alert_sound_priority("remain_yellow"), 1)
        self.assertEqual(_player_panel_alert_sound_priority("remain_red"), 2)
        self.assertEqual(_player_panel_alert_sound_priority("menzen_yellow"), 0)
        self.assertEqual(_player_panel_alert_sound_priority("menzen_red"), 2)
        self.assertEqual(_player_panel_alert_sound_priority("tenpai_near"), 1)

    def test_push_discard_marker_stays_latched_for_round_after_panel_alert_expires(self) -> None:
        first_markers = _push_marker_alerts_for_render(
            {
                1: {
                    "seat": 1,
                    "percentage": 12.3,
                    "threshold_percent": 9.0,
                    "tile_label": "5p",
                    "discard_index": 7,
                    "is_current": True,
                }
            },
            {},
            7,
        )
        later_markers = _push_marker_alerts_for_render(
            {
                1: {
                    "seat": 1,
                    "percentage": 0.0,
                    "threshold_percent": 9.0,
                    "tile_label": "",
                    "discard_index": None,
                    "is_current": False,
                }
            },
            first_markers,
            20,
        )

        self.assertEqual(_push_discard_marker_indices_by_seat(later_markers)[1], frozenset({7}))

    def test_push_discard_marker_latches_multiple_push_discards_in_same_round(self) -> None:
        first_markers = _push_marker_alerts_for_render(
            {
                1: {
                    "seat": 1,
                    "percentage": 12.3,
                    "threshold_percent": 9.0,
                    "discard_index": 7,
                }
            },
            {},
            7,
        )
        later_markers = _push_marker_alerts_for_render(
            {
                1: {
                    "seat": 1,
                    "percentage": 11.1,
                    "threshold_percent": 9.0,
                    "discard_index": 15,
                }
            },
            first_markers,
            15,
        )

        self.assertEqual(_push_discard_marker_indices_by_seat(later_markers)[1], frozenset({7, 15}))

    def test_push_discard_marker_latch_resets_when_round_has_no_discards(self) -> None:
        markers = _push_marker_alerts_for_render(
            {},
            {1: frozenset({7})},
            None,
        )

        self.assertEqual(
            _push_discard_marker_indices_by_seat(markers).get(1, frozenset()),
            frozenset(),
        )

    def test_player_panel_alert_sound_tone_varies_by_alert_color(self) -> None:
        self.assertEqual(_player_panel_alert_sound_tone("remain_purple"), (520, 110))
        self.assertEqual(_player_panel_alert_sound_tone("push:7"), (520, 110))
        self.assertEqual(_player_panel_alert_sound_tone("remain_red"), (760, 90))
        self.assertEqual(_player_panel_alert_sound_tone("remain_yellow"), (960, 70))
        self.assertEqual(_player_panel_alert_sound_tone("push_release:10"), (1200, 60))

    def test_player_panel_remain_sound_level_uses_no_temp_thresholds(self) -> None:
        self.assertEqual(
            _player_panel_remain_sound_level(
                {"denominator_count_without_temporary_safe": 12.0}
            ),
            1,
        )
        self.assertEqual(
            _player_panel_remain_sound_level(
                {"denominator_count_without_temporary_safe": 9.0}
            ),
            2,
        )
        self.assertEqual(
            _player_panel_remain_sound_level(
                {"denominator_count_without_temporary_safe": 6.0}
            ),
            3,
        )
        self.assertEqual(
            _player_panel_remain_sound_level(
                {"denominator_count_without_temporary_safe": 12.1}
            ),
            0,
        )
        self.assertEqual(_player_panel_remain_sound_level({}), 0)

    def test_suji_line_weight_display_rounds_to_one_decimal_place(self) -> None:
        self.assertEqual(_format_suji_line_weight(0.375), "0.4")
        self.assertEqual(_format_suji_line_weight(1.0), "1")

    def test_push_alert_is_suppressed_when_dangerous_target_remain_is_above_13(self) -> None:
        round_state = RoundState()
        round_state.discards[2].append(
            Discard(
                tile_136=4,
                tile_34=1,
                round_discard_index=0,
            )
        )
        round_state.discards[3].append(
            Discard(
                tile_136=5,
                tile_34=1,
                round_discard_index=1,
            )
        )
        round_state.discards[1].append(
            Discard(
                tile_136=6,
                tile_34=1,
                round_discard_index=2,
            )
        )

        push_alerts = build_latest_discard_push_alert_percentages(round_state)

        self.assertEqual(push_alerts[1].percentage, 0.0)

    def test_push_alert_triggers_when_threshold_target_remain_is_13_or_less(self) -> None:
        round_state = RoundState()
        round_state.discards[0].append(
            Discard(
                tile_136=76,
                tile_34=19,
                tsumogiri=False,
                round_discard_index=0,
            )
        )
        round_state.discards[0].append(
            Discard(
                tile_136=72,
                tile_34=18,
                tsumogiri=True,
                round_discard_index=1,
            )
        )
        round_state.discards[1].append(
            Discard(
                tile_136=31,
                tile_34=7,
                tsumogiri=True,
                round_discard_index=2,
            )
        )
        round_state.discards[2].append(
            Discard(
                tile_136=12,
                tile_34=3,
                tsumogiri=False,
                round_discard_index=3,
            )
        )
        round_state.discards[2].append(
            Discard(
                tile_136=100,
                tile_34=25,
                tsumogiri=False,
                round_discard_index=4,
            )
        )
        round_state.discards[3].append(
            Discard(
                tile_136=104,
                tile_34=26,
                tsumogiri=False,
                round_discard_index=5,
            )
        )
        round_state.discards[3].append(
            Discard(
                tile_136=101,
                tile_34=25,
                tsumogiri=True,
                round_discard_index=6,
            )
        )
        round_state.discards[3].append(
            Discard(
                tile_136=88,
                tile_34=22,
                tsumogiri=False,
                round_discard_index=7,
            )
        )

        push_alerts = build_latest_discard_push_alert_percentages(round_state)

        self.assertGreater(push_alerts[1].percentage, 9.0)
        self.assertFalse(push_alerts[1].is_current)

        persisted_alerts = _persist_player_push_alerts(
            {
                1: {
                    "seat": push_alerts[1].seat,
                    "percentage": push_alerts[1].percentage,
                    "tile_label": push_alerts[1].tile_label,
                    "discard_index": push_alerts[1].discard_index,
                    "is_current": push_alerts[1].is_current,
                    "target_seats": push_alerts[1].target_seats,
                    "exact_safe_target_seats": push_alerts[1].exact_safe_target_seats,
                }
            },
            {},
            7,
        )
        indicators_by_seat = _build_player_panel_alert_indicators_by_seat(
            {1: {"denominator_count": 9.0}},
            persisted_alerts,
        )

        self.assertEqual(
            tuple(indicator.key for indicator in indicators_by_seat[1]),
            ("push:2",),
        )

    def test_push_alert_triggers_at_six_percent_against_riichi_target(self) -> None:
        round_state = RoundState()
        round_state.discards[1].append(
            Discard(
                tile_136=4,
                tile_34=1,
                tsumogiri=True,
                round_discard_index=0,
            )
        )

        def fake_profile_builder(_round_state, target_seat, **_kwargs):
            remain_count = 12.0 if target_seat == 0 else 20.0
            return Mock(corrected_musuji_count=remain_count)

        def fake_tile_total_percent(profile, _tile_34):
            if float(profile.corrected_musuji_count) <= 13.0:
                return 6.5
            return 5.5

        with (
            patch(
                "logic.danger_suji.build_opponent_suji_danger_profile",
                side_effect=fake_profile_builder,
            ),
            patch(
                "logic.danger_suji._tile_total_percent",
                side_effect=fake_tile_total_percent,
            ),
            patch(
                "logic.danger_suji._seat_has_riichi_tenpai",
                side_effect=lambda _round_state, seat: seat == 0,
            ),
        ):
            push_alerts = build_latest_discard_push_alert_percentages(round_state)

        self.assertEqual(push_alerts[1].percentage, 6.5)
        self.assertEqual(push_alerts[1].threshold_percent, 6.0)
        self.assertEqual(push_alerts[1].target_seats, (0,))

    def test_push_alert_triggers_for_late_honor_shonpai_discard(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=0, tile_34=0, round_discard_index=0),
                Discard(tile_136=4, tile_34=1, round_discard_index=1),
                Discard(tile_136=8, tile_34=2, round_discard_index=2),
                Discard(tile_136=12, tile_34=3, round_discard_index=3),
                Discard(tile_136=16, tile_34=4, round_discard_index=4),
                Discard(tile_136=20, tile_34=5, round_discard_index=5),
                Discard(tile_136=24, tile_34=6, round_discard_index=6),
                Discard(tile_136=108, tile_34=27, round_discard_index=7),
            ]
        )

        push_alerts = build_latest_discard_push_alert_percentages(round_state)

        self.assertEqual(push_alerts[1].percentage, 9.0)

    def test_late_honor_shonpai_push_requires_eighth_turn_or_later(self) -> None:
        round_state = RoundState()
        round_state.discards[1].extend(
            [
                Discard(tile_136=0, tile_34=0, round_discard_index=0),
                Discard(tile_136=4, tile_34=1, round_discard_index=1),
                Discard(tile_136=8, tile_34=2, round_discard_index=2),
                Discard(tile_136=12, tile_34=3, round_discard_index=3),
                Discard(tile_136=16, tile_34=4, round_discard_index=4),
                Discard(tile_136=20, tile_34=5, round_discard_index=5),
                Discard(tile_136=108, tile_34=27, round_discard_index=6),
            ]
        )

        push_alerts = build_latest_discard_push_alert_percentages(round_state)

        self.assertEqual(push_alerts[1].percentage, 0.0)

    def test_late_honor_shonpai_push_requires_discard_only_shonpai(self) -> None:
        round_state = RoundState()
        round_state.discards[0].append(
            Discard(
                tile_136=109,
                tile_34=27,
                round_discard_index=0,
            )
        )
        round_state.discards[1].extend(
            [
                Discard(tile_136=0, tile_34=0, round_discard_index=1),
                Discard(tile_136=4, tile_34=1, round_discard_index=2),
                Discard(tile_136=8, tile_34=2, round_discard_index=3),
                Discard(tile_136=12, tile_34=3, round_discard_index=4),
                Discard(tile_136=16, tile_34=4, round_discard_index=5),
                Discard(tile_136=20, tile_34=5, round_discard_index=6),
                Discard(tile_136=24, tile_34=6, round_discard_index=7),
                Discard(tile_136=108, tile_34=27, round_discard_index=8),
            ]
        )

        push_alerts = build_latest_discard_push_alert_percentages(round_state)

        self.assertEqual(push_alerts[1].percentage, 0.0)


if __name__ == "__main__":
    unittest.main()
