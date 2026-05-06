import json
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sutehai import DrawType, Player
import ui.table_renderer as table_renderer
from ui.table_renderer import (
    LAYOUT_TUNING_CONTROLS,
    LayoutTuningSettings,
    _build_layout,
    _normalize_layout_tuning_settings,
)


class _FakeImage:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height


def _build_fake_image_table() -> dict[Player, dict[DrawType, dict[int, _FakeImage]]]:
    table: dict[Player, dict[DrawType, dict[int, _FakeImage]]] = {}
    for player in Player:
        if player in (Player.JICHA, Player.TOIMEN):
            width, height = 26, 36
        else:
            width, height = 36, 26
        table[player] = {
            draw_type: {
                tile_id: _FakeImage(width, height)
                for tile_id in range(1, 38)
            }
            for draw_type in DrawType
        }
    return table


class _FakeCanvas:
    def __init__(self) -> None:
        self.text_items: list[dict[str, object]] = []

    def create_rectangle(self, *args: object, **kwargs: object) -> int:
        return 1

    def create_text(self, x: float, y: float, **kwargs: object) -> int:
        self.text_items.append({"x": x, "y": y, **kwargs})
        return len(self.text_items)


class LayoutTuningTest(unittest.TestCase):
    def test_reset_defaults_match_saved_layout_snapshot(self) -> None:
        settings_path = Path(__file__).resolve().parents[1] / "csv_db" / "ui_layout_tuning.json"
        saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        saved_settings.pop("layout_schema_version", None)

        self.assertEqual(
            asdict(_normalize_layout_tuning_settings(saved_settings)),
            asdict(LayoutTuningSettings()),
        )

    def test_visible_layout_controls_drop_obsolete_meld_min_and_ai_top3_sliders(self) -> None:
        fields = {control.field_name for control in LAYOUT_TUNING_CONTROLS}

        self.assertIn("side_meld_width", fields)
        self.assertIn("top_meld_width", fields)
        self.assertIn("bottom_meld_width", fields)
        self.assertNotIn("side_meld_min_width", fields)
        self.assertNotIn("top_meld_min_width", fields)
        self.assertNotIn("hand_response_button_offset_x", fields)
        self.assertNotIn("hand_response_button_offset_y", fields)

    def test_legacy_side_meld_width_field_is_still_accepted(self) -> None:
        normalized = _normalize_layout_tuning_settings(
            {
                "side_meld_min_width": 123,
            }
        )

        self.assertEqual(normalized.side_meld_width, 123)
        self.assertEqual(normalized.top_meld_width, LayoutTuningSettings().top_meld_width)

    def test_normalize_layout_tuning_settings_tolerates_missing_control_bound(self) -> None:
        original_control = table_renderer.LAYOUT_TUNING_CONTROL_BY_FIELD["top_summary_ratio"]
        patched_control = SimpleNamespace(
            field_name=original_control.field_name,
            label=original_control.label,
            min_value=original_control.min_value,
            max_value=None,
            resolution=original_control.resolution,
        )

        with patch.dict(
            table_renderer.LAYOUT_TUNING_CONTROL_BY_FIELD,
            {"top_summary_ratio": patched_control},
            clear=False,
        ):
            normalized = _normalize_layout_tuning_settings({"top_summary_ratio": 0.6})

        self.assertEqual(normalized.top_summary_ratio, 0.6)

    def test_build_layout_respects_independent_top_and_bottom_meld_widths(self) -> None:
        layout = _build_layout(
            0,
            0,
            1400,
            900,
            _build_fake_image_table(),
            1.0,
            layout_tuning=LayoutTuningSettings(
                top_meld_width=140,
                bottom_meld_width=220,
                component_offsets={},
            ),
        )

        top_rect = layout["meld_rects"][Player.TOIMEN]
        bottom_rect = layout["meld_rects"][Player.JICHA]

        self.assertEqual(round(top_rect[2] - top_rect[0]), 140)
        self.assertEqual(round(bottom_rect[2] - bottom_rect[0]), 220)

    def test_center_panel_has_room_for_bootstrap_row(self) -> None:
        layout = _build_layout(
            0,
            0,
            1400,
            900,
            _build_fake_image_table(),
            1.0,
            layout_tuning=LayoutTuningSettings(component_offsets={}),
        )

        center_panel = layout["center_panel"]

        self.assertEqual(round(center_panel[3] - center_panel[1]), table_renderer.CENTER_PANEL_HEIGHT)

    def test_center_panel_draws_bootstrap_above_dora_without_overlap(self) -> None:
        canvas = _FakeCanvas()

        table_renderer._draw_center_panel(
            canvas,
            (0.0, 0.0, float(table_renderer.CENTER_PANEL_WIDTH), float(table_renderer.CENTER_PANEL_HEIGHT)),
            [],
            table_renderer.RoundInfoPanelData(
                round_text="東1局 0本場",
                bootstrap_text="REINIT #3",
            ),
        )

        y_by_text = {
            str(item.get("text")): float(item.get("y", 0.0))
            for item in canvas.text_items
        }
        self.assertGreaterEqual(y_by_text["DORA"] - y_by_text["REINIT #3"], 20.0)


if __name__ == "__main__":
    unittest.main()
