from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_MAIN = ROOT / "src" / "app" / "main.py"
TABLE_RENDERER = ROOT / "src" / "ui" / "table_renderer.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.index(marker)
    next_def = source.find("\ndef ", start + len(marker))
    next_class = source.find("\nclass ", start + len(marker))
    candidates = [idx for idx in (next_def, next_class) if idx != -1]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def test_async_overlay_refresh_does_not_redraw_base_discards() -> None:
    source = _source(TABLE_RENDERER)
    func = _function_source(source, "_redraw_live_async_regions_if_possible")
    assert "_draw_discards(" not in func
    assert "_repair_called_discard_canvas_items_if_needed(" not in func
    assert "_defer_called_discard_canvas_repair_if_needed(" in func
    assert "_LIVE_ASYNC_DISCARD_TAG" in func
    assert "_draw_discard_analysis_overlays(" in func


def test_analysis_overlays_have_separate_canvas_tag() -> None:
    source = _source(TABLE_RENDERER)
    assert '_LIVE_DISCARD_ANALYSIS_OVERLAY_TAG = "live_discard_analysis_overlay"' in source
    overlay_func = _function_source(source, "_draw_discard_analysis_overlays")
    assert "_delete_canvas_items_by_tags(canvas, _LIVE_DISCARD_ANALYSIS_OVERLAY_TAG)" in overlay_func
    assert "discard_analysis_overlay_signature" in overlay_func
    assert "_LIVE_ASYNC_DISCARD_TAG" not in overlay_func
    assert "_draw_push_discard_marker(" in overlay_func
    assert "_draw_discard_tint_overlay(" in overlay_func


def test_called_discard_missing_items_are_deferred_by_async_helper() -> None:
    source = _source(TABLE_RENDERER)
    helper_func = _function_source(source, "_defer_called_discard_canvas_repair_if_needed")
    assert "_called_discard_missing_canvas_item_keys(" in helper_func
    assert "_draw_discards(" not in helper_func
    assert "deferred_to_full_redraw" in helper_func
    assert "UI called discard canvas repair deferred" in helper_func


def test_base_discard_draw_records_overlay_geometry_and_uses_plain_tile_image() -> None:
    source = _source(TABLE_RENDERER)
    func = _function_source(source, "_draw_discards")
    assert 'discard_tint_kind = "none"' in func
    assert "overlay_geometry_by_key[cache_key]" in func
    assert "canvas.discard_analysis_overlay_geometry_by_key = overlay_geometry_by_key" in func
    assert "_draw_discard_analysis_overlays(" in func


def test_worker_jobs_use_analysis_snapshot_not_capture_state_field() -> None:
    source = _source(APP_MAIN)
    assert "class LiveAnalysisSnapshot" in source
    suji_job_start = source.index("class LiveSujiComputationJob")
    red_job_start = source.index("class LiveRedTintComputationJob")
    suji_job = source[suji_job_start:red_job_start]
    red_job = source[red_job_start:source.index("class LiveSujiAsyncState")]
    assert "analysis_snapshot: LiveAnalysisSnapshot" in suji_job
    assert "snapshot_state: CaptureState" not in suji_job
    assert "analysis_snapshot: LiveAnalysisSnapshot" in red_job
    assert "snapshot_state: CaptureState" not in red_job


def test_render_snapshot_builder_publishes_stable_copy_without_history_writeback() -> None:
    source = _source(APP_MAIN)
    func = _function_source(source, "build_live_table_snapshot")
    publish_func = _function_source(source, "_publish_live_stable_discard_map")
    assert "_publish_live_stable_discard_map" in func
    assert "snapshot_state.tracker.discards =" not in func
    assert ".live_river_store.append" not in publish_func
    assert ".tracker.discards" not in publish_func
