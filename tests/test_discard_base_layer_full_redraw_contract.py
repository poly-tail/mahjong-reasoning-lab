from pathlib import Path


def test_draw_discards_validates_cached_base_river_items_without_full_layer_delete() -> None:
    source = Path("src/ui/table_renderer.py").read_text(encoding="utf-8")
    start = source.index("def _draw_discards(")
    body_prefix = source[start: source.index("    # 自家向き牌", start)]
    body = source[start: source.index("def _draw_naga_auto_panel(", start)]

    assert "_delete_canvas_items_by_tags(canvas, _LIVE_ASYNC_DISCARD_TAG)" not in body_prefix
    assert "_reset_discard_render_cache(canvas)" not in body_prefix
    assert "_canvas_has_image_item_with_tag(canvas, item_tag)" in body
    assert "_delete_canvas_items_by_tags(canvas, item_tag)" in body


def test_full_render_still_clears_base_river_layer_before_rebuild() -> None:
    source = Path("src/ui/table_renderer.py").read_text(encoding="utf-8")
    start = source.index("def _render_table(")
    end = source.index("def _draw_background(", start)
    body = source[start:end]

    assert "_LIVE_ASYNC_DISCARD_TAG" in body
    assert "_reset_discard_render_cache(canvas)" in body


def test_async_refresh_still_does_not_redraw_base_discards() -> None:
    source = Path("src/ui/table_renderer.py").read_text(encoding="utf-8")
    start = source.index("def _redraw_live_async_regions_if_possible(")
    end = source.index("def _draw_table_situation_common_panel(", start)
    body = source[start:end]

    assert "_draw_discards(" not in body
    assert "_delete_canvas_items_by_tags(canvas, _LIVE_ASYNC_DISCARD_TAG)" not in body
