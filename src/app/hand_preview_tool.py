from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = WORKSPACE_ROOT / "analysis_output" / "hand_previews"
DEFAULT_TILES_DIR = WORKSPACE_ROOT / "assets" / "tiles"
DEFAULT_DB_DIR = WORKSPACE_ROOT / "csv_db"
TILE_SCALE_DEFAULT = 1.0
TILE_ROW_WRAP = 14
_RED_TILE_MAP_136_TO_37 = {
    16: 10,
    52: 20,
    88: 30,
}
_MSPZ_SUIT_ORDER = ("m", "p", "s", "z")


@dataclass(frozen=True)
class HandPreview:
    source_kind: str
    source_value: str
    hand_tiles_37: tuple[int, ...]
    title_lines: tuple[str, ...] = ()
    discard_tile_text: str = ""
    player_name: str = ""
    player_rel_seat: int | None = None


def resolve_tiles_dir(tiles_dir: str | Path | None = None) -> Path:
    if tiles_dir is not None:
        resolved = Path(tiles_dir).expanduser().resolve()
    else:
        resolved = DEFAULT_TILES_DIR.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Tile directory not found: {resolved}")
    return resolved


def resolve_db_dir(db_dir: str | Path | None = None) -> Path:
    if db_dir is not None:
        resolved = Path(db_dir).expanduser().resolve()
    else:
        resolved = DEFAULT_DB_DIR.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"DB directory not found: {resolved}")
    return resolved


def tile136_to_tile37(tile_136: int | None) -> int | None:
    if tile_136 is None or not 0 <= int(tile_136) <= 135:
        return None
    normalized = int(tile_136)
    if normalized in _RED_TILE_MAP_136_TO_37:
        return _RED_TILE_MAP_136_TO_37[normalized]
    tile34 = normalized // 4
    if 0 <= tile34 <= 8:
        return tile34 + 1
    if 9 <= tile34 <= 17:
        return tile34 + 2
    if 18 <= tile34 <= 26:
        return tile34 + 3
    if 27 <= tile34 <= 33:
        return tile34 + 4
    return None


def tile37_to_compact_text(tile_37: int) -> str:
    normalized = int(tile_37)
    if normalized == 10:
        return "r5m"
    if 1 <= normalized <= 9:
        return f"{normalized}m"
    if normalized == 20:
        return "r5p"
    if 11 <= normalized <= 19:
        return f"{normalized - 9}p"
    if normalized == 30:
        return "r5s"
    if 21 <= normalized <= 29:
        return f"{normalized - 20}s"
    if 31 <= normalized <= 37:
        return f"{normalized - 30}z"
    raise ValueError(f"Unsupported tile_37: {tile_37}")


def _tile37_sort_key(tile_37: int) -> tuple[int, int, int]:
    normalized = int(tile_37)
    if normalized == 10:
        return (0, 5, 0)
    if 1 <= normalized <= 9:
        return (0, normalized, 1 if normalized == 5 else 0)
    if normalized == 20:
        return (1, 5, 0)
    if 11 <= normalized <= 19:
        return (1, normalized - 9, 1 if normalized == 15 else 0)
    if normalized == 30:
        return (2, 5, 0)
    if 21 <= normalized <= 29:
        return (2, normalized - 20, 1 if normalized == 25 else 0)
    if 31 <= normalized <= 37:
        return (3, normalized - 30, 0)
    raise ValueError(f"Unsupported tile_37: {tile_37}")


def sort_tiles_37(tile_ids_37: Iterable[int]) -> tuple[int, ...]:
    return tuple(sorted((int(tile) for tile in tile_ids_37), key=_tile37_sort_key))


def _parse_suit_group(group_text: str, suit: str) -> list[int]:
    tokens: list[str] = []
    index = 0
    while index < len(group_text):
        current = group_text[index]
        if current == "r":
            if index + 1 >= len(group_text) or group_text[index + 1] != "5":
                raise ValueError(f"Invalid red-five token in group: {group_text}{suit}")
            tokens.append("r5")
            index += 2
            continue
        if current.isdigit():
            tokens.append(current)
            index += 1
            continue
        raise ValueError(f"Invalid token `{current}` in group: {group_text}{suit}")

    parsed_tiles: list[int] = []
    for token in tokens:
        if suit == "z":
            if token in {"0", "r5"}:
                raise ValueError("Honors do not support red fives.")
            rank = int(token)
            if not 1 <= rank <= 7:
                raise ValueError(f"Honor rank out of range: {rank}")
            parsed_tiles.append(30 + rank)
            continue

        if token in {"0", "r5"}:
            parsed_tiles.append({"m": 10, "p": 20, "s": 30}[suit])
            continue
        rank = int(token)
        if not 1 <= rank <= 9:
            raise ValueError(f"Suit rank out of range: {rank}")
        if suit == "m":
            parsed_tiles.append(rank)
        elif suit == "p":
            parsed_tiles.append(9 + rank)
        else:
            parsed_tiles.append(20 + rank)
    return parsed_tiles


def _validate_tile_counts(tile_ids_37: Sequence[int]) -> None:
    counts_by_tile: dict[int, int] = {}
    counts_by_suited_five_bucket: dict[tuple[int, int], int] = {}
    for tile_37 in tile_ids_37:
        counts_by_tile[tile_37] = counts_by_tile.get(tile_37, 0) + 1
        if counts_by_tile[tile_37] > 4:
            raise ValueError(f"Too many copies of {tile37_to_compact_text(tile_37)}.")

        suit_rank = _tile37_sort_key(tile_37)[:2]
        if suit_rank[1] == 5 and suit_rank[0] in {0, 1, 2}:
            counts_by_suited_five_bucket[suit_rank] = counts_by_suited_five_bucket.get(suit_rank, 0) + 1
            if counts_by_suited_five_bucket[suit_rank] > 4:
                raise ValueError("Too many total copies of a suited 5 including red five.")


def parse_mspz_hand(mspz_text: str) -> tuple[int, ...]:
    normalized = re.sub(r"[\s,]+", "", str(mspz_text).lower())
    if not normalized:
        raise ValueError("mspz text is empty.")

    tiles_37: list[int] = []
    digit_buffer: list[str] = []
    for char in normalized:
        if char in _MSPZ_SUIT_ORDER:
            if not digit_buffer:
                raise ValueError(f"Missing tile digits before suit `{char}`.")
            tiles_37.extend(_parse_suit_group("".join(digit_buffer), char))
            digit_buffer = []
            continue
        digit_buffer.append(char)
    if digit_buffer:
        raise ValueError("Trailing digits without suit suffix.")

    _validate_tile_counts(tiles_37)
    return sort_tiles_37(tiles_37)


def _decode_hand_tiles_136_json(json_text: str) -> list[int]:
    try:
        payload = json.loads(str(json_text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid hand JSON: {json_text}") from exc
    if not isinstance(payload, list):
        raise ValueError("Hand JSON must be a list.")
    return [int(item) for item in payload]


def _discard_fact_csv_paths(db_dir: Path) -> list[Path]:
    return sorted(db_dir.glob("discard_fact_*.csv"))


def _find_discard_fact_row(discard_id: str, db_dir: Path) -> dict[str, str]:
    for csv_path in _discard_fact_csv_paths(db_dir):
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if str(row.get("discard_id", "")).strip() == discard_id:
                    return {str(key): str(value or "") for key, value in row.items()}
    raise FileNotFoundError(f"discard_id not found in discard_fact CSVs: {discard_id}")


def build_hand_preview_from_discard_id(
    discard_id: str,
    *,
    db_dir: str | Path | None = None,
) -> HandPreview:
    resolved_db_dir = resolve_db_dir(db_dir)
    row = _find_discard_fact_row(discard_id, resolved_db_dir)
    try:
        player_rel_seat = int(row.get("player_rel_seat", ""))
    except ValueError as exc:
        raise ValueError(f"player_rel_seat is invalid for {discard_id}") from exc

    hand_json_key = f"seat{player_rel_seat}_hand_tiles_136_json"
    hand_tiles_136 = _decode_hand_tiles_136_json(row.get(hand_json_key, ""))
    hand_tiles_37: list[int] = []
    for tile_136 in hand_tiles_136:
        tile_37 = tile136_to_tile37(tile_136)
        if tile_37 is None:
            raise ValueError(f"Unsupported tile_136 in row {discard_id}: {tile_136}")
        hand_tiles_37.append(tile_37)

    player_name = str(row.get("player_name", "")).strip()
    discard_tile_text = str(row.get("discard_tile_37_text", "")).strip()
    title_lines = (
        f"discard_id: {discard_id}",
        f"seat: {player_rel_seat}" + (f" / player: {player_name}" if player_name else ""),
        f"discard: {discard_tile_text}" if discard_tile_text else "discard: unknown",
        "hand snapshot includes the discarded tile",
    )
    return HandPreview(
        source_kind="discard_id",
        source_value=discard_id,
        hand_tiles_37=sort_tiles_37(hand_tiles_37),
        title_lines=title_lines,
        discard_tile_text=discard_tile_text,
        player_name=player_name,
        player_rel_seat=player_rel_seat,
    )


def build_hand_preview_from_mspz(mspz_text: str) -> HandPreview:
    hand_tiles_37 = parse_mspz_hand(mspz_text)
    return HandPreview(
        source_kind="mspz",
        source_value=mspz_text,
        hand_tiles_37=hand_tiles_37,
        title_lines=(
            "input: mspz",
            f"tiles: {mspz_text}",
        ),
    )


def _load_tile_image(tile_37: int, tiles_dir: Path, tile_scale: float) -> Image.Image:
    tile_path = tiles_dir / f"{int(tile_37)}.png"
    if not tile_path.exists():
        raise FileNotFoundError(f"Tile image missing: {tile_path}")
    with Image.open(tile_path) as source_image:
        image = source_image.convert("RGBA")
    if abs(float(tile_scale) - 1.0) < 1e-9:
        return image
    scaled_width = max(1, int(round(image.width * float(tile_scale))))
    scaled_height = max(1, int(round(image.height * float(tile_scale))))
    resized = image.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
    image.close()
    return resized


def _measure_text_line_height(font: ImageFont.ImageFont | ImageFont.FreeTypeFont) -> int:
    bbox = font.getbbox("Ag")
    return max(1, int(bbox[3] - bbox[1]))


def _safe_output_stem(source_kind: str, source_value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z._-]+", "_", str(source_value).strip())
    normalized = normalized.strip("._")
    if not normalized:
        normalized = source_kind
    return f"{source_kind}_{normalized[:80]}"


def resolve_output_path(
    hand_preview: HandPreview,
    *,
    output_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> Path:
    if output_path is not None:
        return Path(output_path).expanduser().resolve()
    target_dir = (
        Path(output_dir).expanduser().resolve()
        if output_dir is not None
        else DEFAULT_OUTPUT_DIR
    )
    return target_dir / f"{_safe_output_stem(hand_preview.source_kind, hand_preview.source_value)}.png"


def render_hand_preview_image(
    hand_preview: HandPreview,
    *,
    output_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    tiles_dir: str | Path | None = None,
    tile_scale: float = TILE_SCALE_DEFAULT,
) -> Path:
    resolved_tiles_dir = resolve_tiles_dir(tiles_dir)
    resolved_output_path = resolve_output_path(
        hand_preview,
        output_path=output_path,
        output_dir=output_dir,
    )
    tile_images = [
        _load_tile_image(tile_37, resolved_tiles_dir, tile_scale)
        for tile_37 in hand_preview.hand_tiles_37
    ]
    if not tile_images:
        raise ValueError("No tiles to render.")

    margin = 12
    tile_gap = max(2, int(round(4 * float(tile_scale))))
    row_gap = max(8, int(round(10 * float(tile_scale))))
    title_gap = 6
    font = ImageFont.load_default()
    line_height = _measure_text_line_height(font)
    title_height = 0
    if hand_preview.title_lines:
        title_height = len(hand_preview.title_lines) * (line_height + 4) + title_gap

    row_count = max(1, (len(tile_images) + TILE_ROW_WRAP - 1) // TILE_ROW_WRAP)
    tile_width = max(image.width for image in tile_images)
    tile_height = max(image.height for image in tile_images)
    tiles_in_longest_row = min(len(tile_images), TILE_ROW_WRAP)
    canvas_width = (
        margin * 2
        + tiles_in_longest_row * tile_width
        + max(0, tiles_in_longest_row - 1) * tile_gap
    )
    canvas_height = (
        margin * 2
        + title_height
        + row_count * tile_height
        + max(0, row_count - 1) * row_gap
    )

    canvas = Image.new("RGBA", (canvas_width, canvas_height), (18, 25, 35, 255))
    rgb_canvas: Image.Image | None = None
    try:
        draw = ImageDraw.Draw(canvas)
        current_y = margin
        for title_line in hand_preview.title_lines:
            draw.text((margin, current_y), title_line, fill=(230, 236, 243, 255), font=font)
            current_y += line_height + 4
        if hand_preview.title_lines:
            current_y += title_gap

        for tile_index, tile_image in enumerate(tile_images):
            row_index = tile_index // TILE_ROW_WRAP
            column_index = tile_index % TILE_ROW_WRAP
            left = margin + column_index * (tile_width + tile_gap)
            top = current_y + row_index * (tile_height + row_gap)
            canvas.alpha_composite(tile_image, (left, top))

        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        rgb_canvas = canvas.convert("RGB")
        rgb_canvas.save(resolved_output_path)
    finally:
        if rgb_canvas is not None:
            rgb_canvas.close()
        canvas.close()
        for tile_image in tile_images:
            tile_image.close()
    return resolved_output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a Mahjong hand preview image from mspz text or a discard_id row."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--mspz", help="Mahjong hand in mspz text such as `123m456p789s12344z`.")
    input_group.add_argument("--discard-id", help="discard_fact.discard_id to render.")
    parser.add_argument("--db-dir", help="Directory containing discard_fact_*.csv when using --discard-id.")
    parser.add_argument("--tiles-dir", help="Directory containing assets/tiles/1.png..37.png.")
    parser.add_argument("--output", help="Explicit output PNG path.")
    parser.add_argument("--output-dir", help="Output directory when --output is omitted.")
    parser.add_argument("--tile-scale", type=float, default=TILE_SCALE_DEFAULT, help="Tile image scale multiplier.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.mspz:
        hand_preview = build_hand_preview_from_mspz(args.mspz)
    else:
        hand_preview = build_hand_preview_from_discard_id(str(args.discard_id), db_dir=args.db_dir)

    output_path = render_hand_preview_image(
        hand_preview,
        output_path=args.output,
        output_dir=args.output_dir,
        tiles_dir=args.tiles_dir,
        tile_scale=float(args.tile_scale),
    )
    print(f"saved: {output_path}")
    if hand_preview.discard_tile_text:
        print(f"discard: {hand_preview.discard_tile_text}")
    print("tiles:", " ".join(tile37_to_compact_text(tile_37) for tile_37 in hand_preview.hand_tiles_37))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
