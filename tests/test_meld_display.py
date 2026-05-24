import unittest
from unittest.mock import patch

from capture.state import Meld
from sutehai import Player
import ui.table_renderer as table_renderer
from ui.table_renderer import (
    MELD_RYANMEN_CHI_BORDER,
    MELD_RYANMEN_CHI_BORDER_WIDTH,
    _draw_horizontal_melds,
    _draw_meld_group,
    _draw_vertical_melds,
    _is_ryanmen_chi_meld,
    _meld_dora_counts_by_player,
    _play_meld_dora_alert_sound_if_needed,
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

    def test_meld_groups_grow_left_from_each_players_right(self) -> None:
        canvas = _RecordingCanvas()
        first = Meld(who=0, raw_m=1, meld_type="pon", tiles_37=[1])
        second = Meld(who=0, raw_m=2, meld_type="pon", tiles_37=[2])
        melds = [first, second]

        def measure(_img_table, _player, _meld, *, tile_scale_multiplier: float):
            return (10.0, 10.0)

        def capture_positions(draw_call):
            placements: list[tuple[int, float, float]] = []

            def draw(
                _canvas,
                _img_table,
                _player,
                meld,
                left: float,
                top: float,
                _group_width: float,
                _group_height: float,
                *,
                tile_scale_multiplier: float,
            ) -> None:
                placements.append((meld.raw_m, left, top))

            with patch("ui.table_renderer._measure_meld_group", side_effect=measure), patch(
                "ui.table_renderer._draw_meld_group",
                side_effect=draw,
            ):
                draw_call()
            return {raw_m: (left, top) for raw_m, left, top in placements}

        jicha = capture_positions(
            lambda: _draw_horizontal_melds(canvas, {}, (0.0, 0.0, 120.0, 30.0), melds, Player.JICHA, "right")
        )
        toimen = capture_positions(
            lambda: _draw_horizontal_melds(canvas, {}, (0.0, 0.0, 120.0, 30.0), melds, Player.TOIMEN, "left")
        )
        shimocha = capture_positions(
            lambda: _draw_vertical_melds(canvas, {}, (0.0, 0.0, 30.0, 120.0), melds, Player.SHIMOCHA, "top")
        )
        kamicha = capture_positions(
            lambda: _draw_vertical_melds(canvas, {}, (0.0, 0.0, 30.0, 120.0), melds, Player.KAMICHA, "bottom")
        )

        self.assertGreater(jicha[1][0], jicha[2][0])
        self.assertLess(toimen[1][0], toimen[2][0])
        self.assertLess(shimocha[1][1], shimocha[2][1])
        self.assertGreater(kamicha[1][1], kamicha[2][1])

    def test_meld_dora_count_is_per_player_and_includes_red_dora(self) -> None:
        counts = _meld_dora_counts_by_player(
            {
                Player.SHIMOCHA: [
                    Meld(who=1, raw_m=1, meld_type="chi", tiles_37=[5, 6, 7]),
                    Meld(who=1, raw_m=2, meld_type="pon", tiles_37=[20, 12, 12]),
                ],
                Player.TOIMEN: [
                    Meld(who=2, raw_m=3, meld_type="chi", tiles_37=[5, 6, 7]),
                ],
            },
            (4,),
        )

        self.assertEqual(counts[int(Player.SHIMOCHA)], 2)
        self.assertEqual(counts[int(Player.TOIMEN)], 1)

    def test_meld_dora_alert_sound_fires_on_per_player_threshold_crossing(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_meld_dora_alert_counts_by_seat = {
                    int(player): 0 for player in Player
                }
                self.last_meld_dora_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()

        with patch("ui.table_renderer.winsound", None):
            _play_meld_dora_alert_sound_if_needed(
                canvas,
                {
                    Player.SHIMOCHA: [
                        Meld(who=1, raw_m=1, meld_type="chi", tiles_37=[5, 6, 7]),
                    ],
                    Player.TOIMEN: [
                        Meld(who=2, raw_m=2, meld_type="chi", tiles_37=[5, 6, 7]),
                    ],
                },
                (4,),
            )
            _play_meld_dora_alert_sound_if_needed(
                canvas,
                {
                    Player.SHIMOCHA: [
                        Meld(who=1, raw_m=3, meld_type="pon", tiles_37=[5, 5, 6]),
                    ],
                },
                (4,),
            )

        self.assertEqual(canvas.bell_calls, 3)
        self.assertEqual(
            canvas.last_meld_dora_alert_counts_by_seat[int(Player.SHIMOCHA)],
            2,
        )

    def test_meld_dora_alert_worker_uses_three_note_sequence(self) -> None:
        class WinsoundStub:
            def __init__(self) -> None:
                self.beep_calls: list[tuple[int, int]] = []

            def Beep(self, frequency_hz: int, duration_ms: int) -> None:
                self.beep_calls.append((frequency_hz, duration_ms))

            def MessageBeep(self) -> None:
                raise AssertionError("MessageBeep should not run when Beep succeeds")

        winsound_stub = WinsoundStub()

        with patch("ui.table_renderer.winsound", winsound_stub):
            table_renderer._play_meld_dora_alert_sound_worker()

        self.assertEqual(winsound_stub.beep_calls, [(880, 65), (1120, 65), (1440, 90)])

    def test_meld_dora_alert_sound_queues_worker_when_winsound_is_available(self) -> None:
        class CanvasStub:
            def __init__(self) -> None:
                self.last_meld_dora_alert_counts_by_seat = {
                    int(player): 0 for player in Player
                }
                self.last_meld_dora_alert_sound_monotonic_s = 0.0
                self.bell_calls = 0

            def bell(self) -> None:
                self.bell_calls += 1

        canvas = CanvasStub()

        with patch("ui.table_renderer.winsound", object()), patch(
            "ui.table_renderer._queue_alert_sound_job",
            return_value=True,
        ) as queue_sound:
            _play_meld_dora_alert_sound_if_needed(
                canvas,
                {
                    Player.SHIMOCHA: [
                        Meld(who=1, raw_m=3, meld_type="pon", tiles_37=[5, 5, 6]),
                    ],
                },
                (4,),
            )

        self.assertEqual(canvas.bell_calls, 0)
        queue_sound.assert_called_once()


if __name__ == "__main__":
    unittest.main()
