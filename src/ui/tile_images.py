from __future__ import annotations

from functools import lru_cache
import tkinter
from pathlib import Path
from typing import Dict, Mapping, Tuple

from PIL import Image, ImageChops, ImageOps, ImageTk

from sutehai import DrawType, Player

# TileImageTable の型定義。
TileImageTable = Dict[Player, Dict[DrawType, Dict[int, ImageTk.PhotoImage]]]
# OverlayBand の型定義。
OverlayBand = Tuple[float, float, tuple[int, int, int], tuple[int, int, int], float]

# N_TILES の定義。
N_TILES = 37
# TILE_MAX_WIDTH の定義。
TILE_MAX_WIDTH = 26
# TILE_MAX_HEIGHT の定義。
TILE_MAX_HEIGHT = 36
# TILE_FRAME_WIDTH の定義。
TILE_FRAME_WIDTH = 2
# PLAYER_ROTATIONS の対応表。
PLAYER_ROTATIONS = {
    Player.JICHA: 0,
    Player.SHIMOCHA: 90,
    Player.TOIMEN: 180,
    Player.KAMICHA: 270,
}

# _TILE_DIR_CANDIDATES の一覧。
_TILE_DIR_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "assets" / "tiles",
    Path(__file__).resolve().parent.parent.parent / "assets" / "tiles",
]


def resolve_tiles_dir() -> Path:
    for candidate in _TILE_DIR_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Tile directory not found in: {_TILE_DIR_CANDIDATES}")


def logical_tile_id_to_asset_tile_id(tile_id: int) -> int:
    if not 1 <= tile_id <= N_TILES:
        raise ValueError(f"Unsupported logical tile id: {tile_id}")
    return tile_id


@lru_cache(maxsize=None)
def _load_tile_source_image(tile_id: int) -> Image.Image:
    asset_tile_id = logical_tile_id_to_asset_tile_id(tile_id)
    tile_path = resolve_tiles_dir() / f"{asset_tile_id}.png"
    if not tile_path.exists():
        raise FileNotFoundError(f"Tile image missing: {tile_path}")

    return Image.open(tile_path).convert("RGBA")


def _normalize_tile_scale(tile_scale: float) -> float:
    return max(0.5, min(round(float(tile_scale), 3), 1.0))


@lru_cache(maxsize=None)
def _load_scaled_tile_base_image(tile_id: int, tile_scale: float) -> Image.Image:
    normalized_scale = _normalize_tile_scale(tile_scale)
    base_image = _load_tile_source_image(tile_id).copy()
    max_width = max(1, int(round(TILE_MAX_WIDTH * normalized_scale)))
    max_height = max(1, int(round(TILE_MAX_HEIGHT * normalized_scale)))
    base_image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return base_image


def _build_unrotated_tile_image(
    tile_id: int,
    draw_type: DrawType,
    tile_scale: float = 1.0,
) -> Image.Image:
    normalized_scale = _normalize_tile_scale(tile_scale)
    base_image = _load_scaled_tile_base_image(tile_id, normalized_scale)
    frame_width = max(1, int(round(TILE_FRAME_WIDTH * normalized_scale)))
    if draw_type == DrawType.TSUMOGIRI:
        tsumogiri_core = ImageChops.difference(
            base_image.convert("RGB"),
            Image.new("RGB", base_image.size, (72, 72, 72)),
        )
        return ImageOps.expand(
            tsumogiri_core.convert("RGBA"),
            border=frame_width,
            fill=(0, 0, 0, 0),
        )
    return ImageOps.expand(base_image, border=frame_width, fill=(0, 0, 0, 0))


def _clamp_unit(value: float) -> float:
    return max(0.0, min(value, 1.0))


def _interpolate_rgb(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    normalized_ratio = _clamp_unit(ratio)
    return tuple(
        int(round(start[index] + (end[index] - start[index]) * normalized_ratio))
        for index in range(3)
    )


def _apply_vertical_band_gradient_overlay(
    image: Image.Image,
    gradient_top_color: tuple[int, int, int] | None,
    gradient_bottom_color: tuple[int, int, int] | None,
    overlay_strength: float,
    band_start_ratio: float,
    band_end_ratio: float,
) -> Image.Image:
    """Apply one overlay band in the unrotated tile coordinate system."""

    if (
        gradient_top_color is None
        or gradient_bottom_color is None
        or overlay_strength <= 0.0
    ):
        return image

    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    start_ratio = _clamp_unit(band_start_ratio)
    end_ratio = _clamp_unit(band_end_ratio)
    if end_ratio <= start_ratio:
        return image

    start_y = int(round(height * start_ratio))
    end_y = min(max(start_y + 1, int(round(height * end_ratio))), height)
    row_count = max(end_y - start_y, 1)
    alpha_value = int(round(255 * _clamp_unit(overlay_strength)))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    for y in range(start_y, end_y):
        row_ratio = 0.0 if row_count <= 1 else (y - start_y) / (row_count - 1)
        row_color = _interpolate_rgb(gradient_top_color, gradient_bottom_color, row_ratio)
        overlay.paste((*row_color, alpha_value), (0, y, width, y + 1))

    masked_overlay_alpha = ImageChops.multiply(overlay.getchannel("A"), image.getchannel("A"))
    overlay.putalpha(masked_overlay_alpha)
    return Image.alpha_composite(image, overlay)


def _apply_overlay_bands(
    image: Image.Image,
    overlay_bands: tuple[OverlayBand, ...],
) -> Image.Image:
    """Apply multiple overlay bands in order on the unrotated tile image."""

    overlaid = image
    for band_start_ratio, band_end_ratio, top_color, bottom_color, overlay_strength in overlay_bands:
        overlaid = _apply_vertical_band_gradient_overlay(
            overlaid,
            top_color,
            bottom_color,
            overlay_strength,
            band_start_ratio,
            band_end_ratio,
        )
    return overlaid


@lru_cache(maxsize=None)
def _build_unrotated_tile_image_with_overlay_bands(
    tile_id: int,
    draw_type: DrawType,
    overlay_bands: tuple[OverlayBand, ...],
    tile_scale: float,
) -> Image.Image:
    """Return one cached unrotated tile image with its base overlays already applied."""

    normalized_scale = _normalize_tile_scale(tile_scale)
    return _apply_overlay_bands(
        _build_unrotated_tile_image(tile_id, draw_type, normalized_scale),
        overlay_bands,
    )


@lru_cache(maxsize=None)
def _build_oriented_tile_image(
    tile_id: int,
    player: Player,
    draw_type: DrawType,
    overlay_bands: tuple[OverlayBand, ...],
    tile_scale: float,
) -> Image.Image:
    # Apply overlays before seat rotation so every band uses the same base coordinates.
    normalized_scale = _normalize_tile_scale(tile_scale)
    overlaid = _apply_overlay_bands(
        _build_unrotated_tile_image(tile_id, draw_type, normalized_scale),
        overlay_bands,
    )
    return overlaid.rotate(PLAYER_ROTATIONS[player], expand=True)


def build_tile_photoimage_from_base_overlay(
    master: tkinter.Misc,
    tile_id: int,
    player: Player,
    draw_type: DrawType = DrawType.TEDASHI,
    *,
    base_overlay_bands: tuple[OverlayBand, ...] = (),
    overlay_bands: tuple[OverlayBand, ...] = (),
    tile_scale: float = 1.0,
) -> ImageTk.PhotoImage:
    """Build one PhotoImage from a pre-tinted unrotated base plus optional extra overlays."""

    normalized_scale = _normalize_tile_scale(tile_scale)
    base_image = _build_unrotated_tile_image_with_overlay_bands(
        tile_id,
        draw_type,
        tuple(base_overlay_bands),
        normalized_scale,
    )
    if overlay_bands:
        oriented = _apply_overlay_bands(
            base_image.copy(),
            tuple(overlay_bands),
        ).rotate(PLAYER_ROTATIONS[player], expand=True)
    else:
        oriented = base_image.rotate(PLAYER_ROTATIONS[player], expand=True)
    return ImageTk.PhotoImage(oriented, master=master)


def build_tile_photoimage(
    master: tkinter.Misc,
    tile_id: int,
    player: Player,
    draw_type: DrawType = DrawType.TEDASHI,
    *,
    overlay_bands: tuple[OverlayBand, ...] = (),
    tile_scale: float = 1.0,
) -> ImageTk.PhotoImage:
    return ImageTk.PhotoImage(
        _build_oriented_tile_image(
            tile_id,
            player,
            draw_type,
            overlay_bands,
            _normalize_tile_scale(tile_scale),
        ),
        master=master,
    )


def warm_unrotated_tile_overlay_bases(
    overlay_bands_by_name: Mapping[str, tuple[OverlayBand, ...]],
    *,
    tile_scale: float = 1.0,
) -> None:
    """Prewarm cached unrotated tile bases for the provided overlay variants."""

    normalized_scale = _normalize_tile_scale(tile_scale)
    for overlay_bands in overlay_bands_by_name.values():
        normalized_overlay_bands = tuple(overlay_bands)
        for tile_id in range(1, N_TILES + 1):
            for draw_type in (DrawType.TEDASHI, DrawType.TSUMOGIRI):
                _build_unrotated_tile_image_with_overlay_bands(
                    tile_id,
                    draw_type,
                    normalized_overlay_bands,
                    normalized_scale,
                )


def initialize_image(root: tkinter.Tk, tile_scale: float = 1.0) -> TileImageTable:
    # Prebuild the base tile table for every seat orientation and discard type.
    normalized_scale = _normalize_tile_scale(tile_scale)
    table: TileImageTable = {
        player: {
            DrawType.TEDASHI: {},
            DrawType.TSUMOGIRI: {},
        }
        for player in Player
    }

    for tile_id in range(1, N_TILES + 1):
        tedashi_image = _build_unrotated_tile_image(
            tile_id,
            DrawType.TEDASHI,
            normalized_scale,
        )
        tsumogiri_image = _build_unrotated_tile_image(
            tile_id,
            DrawType.TSUMOGIRI,
            normalized_scale,
        )

        for player, angle in PLAYER_ROTATIONS.items():
            table[player][DrawType.TEDASHI][tile_id] = ImageTk.PhotoImage(
                tedashi_image.rotate(angle, expand=True),
                master=root,
            )
            table[player][DrawType.TSUMOGIRI][tile_id] = ImageTk.PhotoImage(
                tsumogiri_image.rotate(angle, expand=True),
                master=root,
            )

    return table


def tile_size(
    img_table: TileImageTable,
    player: Player,
    draw_type: DrawType = DrawType.TEDASHI,
    tile_id: int = 1,
) -> tuple[int, int]:
    image = img_table[player][draw_type][tile_id]
    return image.width(), image.height()
