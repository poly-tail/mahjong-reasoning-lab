import unittest
from unittest.mock import patch

from capture.state import Meld
from sutehai import Player
from ui.table_renderer import (
    MELD_RYANMEN_CHI_BORDER,
    MELD_RYANMEN_CHI_BORDER_WIDTH,
    _draw_meld_group,
    _is_ryanmen_chi_meld,
)


class _RecordingCanvas:
    def __init__(self) -> None:
        self.current_ui_scale = 1.0
        self.rectangles: list[tuple[tuple[float, float, float, float], dict[str, object]]] = []
        self.images: list[tuple[float, float, dict[str, object]]] = []

    def create_rectangle(self, *coords: float, **kwargs: object) -> None:
        self.rectangles.append((coords, kwargs))

    def create_image(self, x: float, y: float, **kwargs: object) -> None:
        self.images.append((x, y, kwargs))


class MeldDisplayTest(unittest.TestCase):
    def test_ryanmen_chi_detection_accepts_two_sided_called_edge(self) -> None:
        meld = Meld(
            who=0,
            raw_m=0,
            meld_type="chi",
            tiles_136=[4, 8, 12],
            called_tile_id=4,
            called_index=0,
        )

        self.assertTrue(_is_ryanmen_chi_meld(meld))

    def test_ryanmen_chi_detection_rejects_kanchan_and_penchan(self) -> None:
        kanchan = Meld(
            who=0,
            raw_m=0,
            meld_type="chi",
            tiles_136=[4, 8, 12],
            called_tile_id=8,
            called_index=1,
        )
        penchan = Meld(
            who=0,
            raw_m=0,
            meld_type="chi",
            tiles_136=[0, 4, 8],
            called_tile_id=8,
            called_index=2,
        )

        self.assertFalse(_is_ryanmen_chi_meld(kanchan))
        self.assertFalse(_is_ryanmen_chi_meld(penchan))

    def test_ryanmen_chi_group_gets_yellow_frame(self) -> None:
        canvas = _RecordingCanvas()
        meld = Meld(
            who=0,
            raw_m=0,
            meld_type="chi",
            tiles_37=[2, 3, 4],
            called_index=2,
        )

        with patch(
            "ui.table_renderer._build_rotated_meld_group_layout",
            return_value=(30.0, 20.0, [(2, Player.JICHA, 0.0, 0.0)]),
        ), patch(
            "ui.table_renderer._meld_tile_image",
            return_value="tile-image",
        ):
            _draw_meld_group(
                canvas,
                {},
                Player.JICHA,
                meld,
                10.0,
                20.0,
                30.0,
                20.0,
                tile_scale_multiplier=1.0,
            )

        self.assertEqual(canvas.images, [(10.0, 20.0, {"image": "tile-image", "anchor": "nw"})])
        self.assertEqual(len(canvas.rectangles), 1)
        coords, kwargs = canvas.rectangles[0]
        self.assertEqual(coords, (8.0, 18.0, 42.0, 42.0))
        self.assertEqual(kwargs["outline"], MELD_RYANMEN_CHI_BORDER)
        self.assertEqual(kwargs["width"], MELD_RYANMEN_CHI_BORDER_WIDTH)

    def test_non_ryanmen_chi_group_has_no_yellow_frame(self) -> None:
        canvas = _RecordingCanvas()
        meld = Meld(
            who=0,
            raw_m=0,
            meld_type="chi",
            tiles_37=[2, 3, 4],
            called_index=1,
        )

        with patch(
            "ui.table_renderer._build_rotated_meld_group_layout",
            return_value=(30.0, 20.0, [(3, Player.JICHA, 0.0, 0.0)]),
        ), patch(
            "ui.table_renderer._meld_tile_image",
            return_value="tile-image",
        ):
            _draw_meld_group(
                canvas,
                {},
                Player.JICHA,
                meld,
                10.0,
                20.0,
                30.0,
                20.0,
                tile_scale_multiplier=1.0,
            )

        self.assertEqual(canvas.rectangles, [])


if __name__ == "__main__":
    unittest.main()
