from __future__ import annotations

from types import SimpleNamespace

from sutehai import Discard, DrawType, Player
from ui import table_renderer as tr


def _discard(tile_id: int, *, called: bool = False) -> Discard:
    return Discard(tile_id=tile_id, draw_type=DrawType.TEDASHI, called=called)


def test_same_round_cache_identity_survives_wgc_wrapper_change() -> None:
    base_round = "game:0:0:0:0"
    previous = base_round
    current = (("wgc", base_round, 3), 3)

    assert tr._same_round_discard_cache_identity(previous, current)
    assert tr._same_round_discard_cache_identity(current, previous)


def test_same_round_cache_identity_survives_initbylog_wrapper_change() -> None:
    base_round = "game:0:0:0:0"
    previous = base_round
    current = (("initbylog", base_round, 3), 3)

    assert tr._same_round_discard_cache_identity(previous, current)
    assert tr._same_round_discard_cache_identity(current, previous)


def test_base_river_store_retains_called_gap_across_wrapper_change() -> None:
    base_round = "game:0:0:0:0"
    canvas = SimpleNamespace(
        current_round_identity=(("wgc", base_round, 2), 2),
        round_discard_map_cache_identity=tr._round_discard_cache_identity(base_round),
        round_discard_map_cache={
            Player.JICHA: [_discard(0)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    merged, retained = tr._merge_discard_map_with_round_cache(
        canvas,
        {
            Player.JICHA: [_discard(4)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
    )

    assert retained == 1
    assert [d.tile_id for d in merged[Player.JICHA]] == [0, 4]
    assert merged[Player.JICHA][0].called is True
    assert merged[Player.JICHA][1].called is False


def test_cached_layout_renderer_normalizes_river_before_draw(monkeypatch) -> None:
    base_round = "game:0:0:0:0"
    canvas = SimpleNamespace(
        current_round_identity=base_round,
        round_discard_map_cache_identity=tr._round_discard_cache_identity(base_round),
        round_discard_map_cache={
            Player.JICHA: [_discard(0)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
        last_render_layout={
            "detail_content_rect": (0.0, 0.0, 10.0, 10.0),
            "hand_rect": (0.0, 0.0, 10.0, 10.0),
        },
        winfo_exists=lambda: True,
        layout_drag_enabled=False,
        current_hand_rect=None,
        table_situation_scores_by_seat={},
    )

    seen: dict[str, object] = {}

    def fake_draw_discards(_canvas, _img_table, discard_map, *args, **kwargs):
        seen["tiles"] = [d.tile_id for d in discard_map[Player.JICHA]]
        seen["called"] = [d.called for d in discard_map[Player.JICHA]]

    monkeypatch.setattr(tr, "_draw_discards", fake_draw_discards)
    monkeypatch.setattr(tr, "_reset_transient_canvas_draw_state", lambda canvas: None)
    monkeypatch.setattr(tr, "_delete_canvas_items_by_tags", lambda canvas, *tags: None)
    monkeypatch.setattr(tr, "_build_visible_tile_inference_summary_for_canvas", lambda *a, **k: (None, ()))
    monkeypatch.setattr(tr, "_normalize_table_situation_scores_by_seat", lambda value: {})
    monkeypatch.setattr(tr, "_resolve_table_situation_auto_scores_by_seat", lambda *a, **k: {})
    monkeypatch.setattr(tr, "_resolve_table_situation_scores_by_seat", lambda *a, **k: {})
    monkeypatch.setattr(tr, "_build_table_frame_render_signature", lambda *a, **k: object())
    monkeypatch.setattr(tr, "_restore_table_frame_render_cache", lambda *a, **k: False)
    monkeypatch.setattr(tr, "_capture_canvas_item_ids", lambda canvas: set())
    monkeypatch.setattr(tr, "_draw_table_frame", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_tag_new_canvas_items", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_remember_table_frame_render_cache", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_log_slow_discard_redraw", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_redraw_side_panels_if_needed", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_draw_hand", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_draw_hand_response_button_and_panel", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_draw_naga_auto_panel", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_append_phase_timing", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_log_cached_layout_redraw", lambda *a, **k: None, raising=False)

    ok, _rect = tr._render_table_using_cached_layout_if_possible(
        canvas,
        img_table=None,
        discard_map={
            Player.JICHA: [_discard(4)],
            Player.SHIMOCHA: [],
            Player.TOIMEN: [],
            Player.KAMICHA: [],
        },
        hand_tiles=[],
        hand_draw_tile=None,
        hand_recommendation_panel=tr.HandRecommendationPanelData(),
        hand_danger_percentages=[],
        opponent_suji_panel_summaries={},
        player_push_alert_percentages={},
        push_marker_alert_percentages={},
        player_alert_indicators_by_seat={},
        player_score_diffs_by_seat={},
        discard_red_tint_indices_by_seat={},
        player_names_by_seat={},
        meld_tiles=[],
        dora_indicator_tiles=[],
        round_events=[],
        round_info_panel=tr.RoundInfoPanelData(),
        melds_by_player={},
        visible_summary=tr.VisibleTileSummary((), ()),
    )

    assert ok is True
    assert seen["tiles"] == [0, 4]
    assert seen["called"] == [True, False]


def test_table_frame_redraw_invalidates_cached_discard_layers(monkeypatch) -> None:
    canvas = SimpleNamespace(
        discard_render_cache_by_key={(0, 0): ("cached",)},
        discard_tile_image_refs={(0, 0): object()},
        discard_analysis_overlay_signature=("overlay",),
        discard_analysis_overlay_geometry_by_key={(0, 0): {"left": 0.0}},
    )
    deleted_tags: list[str] = []

    monkeypatch.setattr(
        tr,
        "_delete_canvas_items_by_tags",
        lambda _canvas, *tags: deleted_tags.extend(tags),
    )

    tr._invalidate_discard_layers_for_table_frame_redraw(canvas)

    assert deleted_tags == [
        tr._LIVE_ASYNC_DISCARD_TAG,
        tr._LIVE_DISCARD_ANALYSIS_OVERLAY_TAG,
    ]
    assert canvas.discard_render_cache_by_key == {}
    assert canvas.discard_tile_image_refs == {}
    assert canvas.discard_analysis_overlay_signature is None
    assert canvas.discard_analysis_overlay_geometry_by_key == {}


def test_cached_layout_frame_redraw_invalidates_discards_before_repaint(monkeypatch) -> None:
    canvas = SimpleNamespace(
        current_round_identity="round-1",
        round_discard_map_cache_identity=tr._round_discard_cache_identity("round-1"),
        round_discard_map_cache={player: [] for player in Player},
        last_render_layout={
            "detail_content_rect": (0.0, 0.0, 10.0, 10.0),
            "hand_rect": (0.0, 0.0, 10.0, 10.0),
        },
        winfo_exists=lambda: True,
        layout_drag_enabled=False,
        current_hand_rect=None,
        table_situation_scores_by_seat={},
        table_frame_render_cache=None,
    )
    order: list[str] = []

    monkeypatch.setattr(tr, "_reset_transient_canvas_draw_state", lambda canvas: None)
    monkeypatch.setattr(tr, "_delete_canvas_items_by_tags", lambda canvas, *tags: None)
    monkeypatch.setattr(tr, "_build_visible_tile_inference_summary_for_canvas", lambda *a, **k: (None, ()))
    monkeypatch.setattr(tr, "_normalize_table_situation_scores_by_seat", lambda value: {})
    monkeypatch.setattr(tr, "_resolve_table_situation_auto_scores_by_seat", lambda *a, **k: {})
    monkeypatch.setattr(tr, "_resolve_table_situation_scores_by_seat", lambda *a, **k: {})
    monkeypatch.setattr(tr, "_build_table_frame_render_signature", lambda *a, **k: ("frame-with-call",))
    monkeypatch.setattr(tr, "_restore_table_frame_render_cache", lambda *a, **k: False)
    monkeypatch.setattr(
        tr,
        "_invalidate_discard_layers_for_table_frame_redraw",
        lambda canvas: order.append("invalidate_discards"),
    )
    monkeypatch.setattr(tr, "_capture_canvas_item_ids", lambda canvas: set())
    monkeypatch.setattr(tr, "_draw_table_frame", lambda *a, **k: order.append("table_frame"))
    monkeypatch.setattr(tr, "_tag_new_canvas_items", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_remember_table_frame_render_cache", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_draw_discards", lambda *a, **k: order.append("discards"))
    monkeypatch.setattr(tr, "_log_slow_discard_redraw", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_redraw_side_panels_if_needed", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_draw_hand", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_draw_hand_response_button_and_panel", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_draw_naga_auto_panel", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_append_phase_timing", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_log_cached_layout_redraw", lambda *a, **k: None, raising=False)

    ok, _rect = tr._render_table_using_cached_layout_if_possible(
        canvas,
        img_table=None,
        discard_map={player: [] for player in Player},
        hand_tiles=[],
        hand_draw_tile=None,
        hand_recommendation_panel=tr.HandRecommendationPanelData(),
        hand_danger_percentages=[],
        opponent_suji_panel_summaries={},
        player_push_alert_percentages={},
        push_marker_alert_percentages={},
        player_alert_indicators_by_seat={},
        player_score_diffs_by_seat={},
        discard_red_tint_indices_by_seat={},
        player_names_by_seat={},
        meld_tiles=[],
        dora_indicator_tiles=[],
        round_events=[],
        round_info_panel=tr.RoundInfoPanelData(),
        melds_by_player={},
        visible_summary=tr.VisibleTileSummary((), ()),
    )

    assert ok is True
    assert order[:3] == ["invalidate_discards", "table_frame", "discards"]