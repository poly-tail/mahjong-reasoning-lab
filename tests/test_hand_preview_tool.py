from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.hand_preview_tool import (
    build_hand_preview_from_discard_id,
    parse_mspz_hand,
    render_hand_preview_image,
    tile37_to_compact_text,
)


class HandPreviewToolTest(unittest.TestCase):
    def test_parse_mspz_supports_red_five_tokens(self) -> None:
        parsed = parse_mspz_hand("123m405p 678s 12344z")

        self.assertEqual(
            tuple(tile37_to_compact_text(tile) for tile in parsed),
            ("1m", "2m", "3m", "4p", "r5p", "5p", "6s", "7s", "8s", "1z", "2z", "3z", "4z", "4z"),
        )

    def test_build_hand_preview_from_discard_id_uses_pre_discard_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_text:
            db_dir = Path(temp_dir_text)
            csv_path = db_dir / "discard_fact_202604.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("discard_id", "player_rel_seat", "player_name", "discard_tile_37_text", "seat2_hand_tiles_136_json"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "discard_id": "H_20260410_001",
                        "player_rel_seat": "2",
                        "player_name": "toimen",
                        "discard_tile_37_text": "5p",
                        "seat2_hand_tiles_136_json": json.dumps([0, 4, 8, 12, 52]),
                    }
                )

            preview = build_hand_preview_from_discard_id("H_20260410_001", db_dir=db_dir)

        self.assertEqual(preview.player_rel_seat, 2)
        self.assertEqual(preview.player_name, "toimen")
        self.assertEqual(preview.discard_tile_text, "5p")
        self.assertEqual(
            tuple(tile37_to_compact_text(tile) for tile in preview.hand_tiles_37),
            ("1m", "2m", "3m", "4m", "r5p"),
        )

    def test_render_hand_preview_image_writes_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            tiles_dir = temp_dir / "tiles"
            tiles_dir.mkdir()
            for tile_id in range(1, 38):
                Image.new("RGBA", (16, 24), (tile_id, tile_id, tile_id, 255)).save(
                    tiles_dir / f"{tile_id}.png"
                )

            output_path = render_hand_preview_image(
                build_hand_preview_from_discard_id(
                    "preview_discard_001",
                    db_dir=_build_fake_db(temp_dir),
                ),
                output_dir=temp_dir / "out",
                tiles_dir=tiles_dir,
            )

            self.assertTrue(output_path.exists())
            with Image.open(output_path) as rendered:
                self.assertGreater(rendered.width, 0)
                self.assertGreater(rendered.height, 0)


def _build_fake_db(temp_dir: Path) -> Path:
    db_dir = temp_dir / "csv_db"
    db_dir.mkdir()
    csv_path = db_dir / "discard_fact_202604.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("discard_id", "player_rel_seat", "player_name", "discard_tile_37_text", "seat0_hand_tiles_136_json"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "discard_id": "preview_discard_001",
                "player_rel_seat": "0",
                "player_name": "self",
                "discard_tile_37_text": "1m",
                "seat0_hand_tiles_136_json": json.dumps([0, 4, 8, 12]),
            }
        )
    return db_dir


if __name__ == "__main__":
    unittest.main()
