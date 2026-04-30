from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

# SIMULATOR_TILE_COUNT の定義。
SIMULATOR_TILE_COUNT = 37
# SIMULATOR_TILE_IDS の並びを定義する。
SIMULATOR_TILE_IDS = tuple(range(SIMULATOR_TILE_COUNT))
# SIMULATOR_NORMAL_FIVE_TILE_IDS の並びを定義する。
SIMULATOR_NORMAL_FIVE_TILE_IDS = (4, 13, 22)
# SIMULATOR_RED_FIVE_TILE_IDS の並びを定義する。
SIMULATOR_RED_FIVE_TILE_IDS = (34, 35, 36)
# SIMULATOR_DEFAULT_ROUND_WIND の定義。
SIMULATOR_DEFAULT_ROUND_WIND = 27
# SIMULATOR_DEFAULT_SEAT_WIND の定義。
SIMULATOR_DEFAULT_SEAT_WIND = 27
# SIMULATOR_DEFAULT_DORA_INDICATORS の並びを定義する。
SIMULATOR_DEFAULT_DORA_INDICATORS = (27,)
# SIMULATOR_FALLBACK_DISPLAY_TURN_INDEX の定義。
SIMULATOR_FALLBACK_DISPLAY_TURN_INDEX = 3
# SIMULATOR_VERSION の定義。
SIMULATOR_VERSION = "0.9.1"

# The simulator uses 34 normal tiles plus three red fives. Normal tiles start with four copies,
# red-fives start with one copy each, and each normal five therefore starts with three copies.
SIMULATOR_BASE_WALL_COUNTS = tuple(
    [4] * 4
    + [3]
    + [4] * 4
    + [4] * 4
    + [3]
    + [4] * 4
    + [4] * 4
    + [3]
    + [4] * 11
    + [1, 1, 1]
)

# SIMULATOR_TILE_TEXT_KANJI の対応表。
SIMULATOR_TILE_TEXT_KANJI = {
    27: "東",
    28: "南",
    29: "西",
    30: "北",
    31: "白",
    32: "發",
    33: "中",
}


@dataclass(frozen=True)
class PystyleRequestMeld:
    """One meld entry inside the simulator request payload."""

    # type を保持する。
    type: int | str
    # tiles の並びを保持する。
    tiles: tuple[int, ...]
    # discarded_tile を保持する。
    discarded_tile: int | None = None
    # from_seat を保持する。
    from_seat: int | None = None
    # extras の対応表。
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PystyleRequestPayload:
    """Validated request payload sent from the frontend to `post.py`."""

    # enable_reddora を保持する。
    enable_reddora: bool
    # enable_uradora を保持する。
    enable_uradora: bool
    # enable_shanten_down を保持する。
    enable_shanten_down: bool
    # enable_tegawari を保持する。
    enable_tegawari: bool
    # enable_riichi を保持する。
    enable_riichi: bool
    # round_wind を保持する。
    round_wind: int
    # dora_indicators の並びを保持する。
    dora_indicators: tuple[int, ...]
    # hand の並びを保持する。
    hand: tuple[int, ...]
    # melds の並びを保持する。
    melds: tuple[PystyleRequestMeld, ...]
    # seat_wind を保持する。
    seat_wind: int
    # wall の並びを保持する。
    wall: tuple[int, ...]
    # version を保持する。
    version: str
    # extras の対応表。
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PystyleNecessaryTile:
    """One effective tile entry inside one simulator response stat row."""

    # tile を保持する。
    tile: int
    # count を保持する。
    count: int


@dataclass(frozen=True)
class PystyleResponseStat:
    """One discard-candidate row inside `response.stats`."""

    # tile を保持する。
    tile: int
    # shanten を保持する。
    shanten: int
    # necessary_tiles の並びを保持する。
    necessary_tiles: tuple[PystyleNecessaryTile, ...]
    # exp_score の並びを保持する。
    exp_score: tuple[float, ...] = ()
    # win_prob の並びを保持する。
    win_prob: tuple[float, ...] = ()
    # tenpai_prob の並びを保持する。
    tenpai_prob: tuple[float, ...] = ()
    # extras の対応表。
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PystyleResponseShanten:
    """The grouped shanten values returned by the simulator backend."""

    # all を保持する。
    all: int
    # regular を保持する。
    regular: int
    # seven_pairs を保持する。
    seven_pairs: int
    # thirteen_orphans を保持する。
    thirteen_orphans: int
    # extras の対応表。
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PystyleResponseConfig:
    """Known response-side config fields used by the frontend result renderer."""

    # t_min を保持する。
    t_min: int
    # t_max を保持する。
    t_max: int
    # sum を保持する。
    sum: int
    # extra を保持する。
    extra: int | None = None
    # shanten_type を保持する。
    shanten_type: int | None = None
    # calc_stats を保持する。
    calc_stats: bool = False
    # num_tiles を保持する。
    num_tiles: int | None = None
    # extras の対応表。
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PystyleResponsePayload:
    """Validated `response` body returned by the simulator backend."""

    # shanten を保持する。
    shanten: PystyleResponseShanten
    # stats の並びを保持する。
    stats: tuple[PystyleResponseStat, ...]
    # config を保持する。
    config: PystyleResponseConfig
    # searched を保持する。
    searched: int | None = None
    # time を保持する。
    time: int | None = None
    # extras の対応表。
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PystyleWireResponse:
    """Top-level response wrapper returned to the frontend by `post.py`."""

    # success を保持する。
    success: bool
    # request を保持する。
    request: PystyleRequestPayload | None = None
    # response を保持する。
    response: PystyleResponsePayload | None = None
    # err_msg を保持する。
    err_msg: str | None = None
    # extras の対応表。
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PystyleDisplayContext:
    """Frontend-side display/request context for one AI TOP3 POST."""
    turn_index: int = SIMULATOR_FALLBACK_DISPLAY_TURN_INDEX
    turn_source: str = "frontend_fallback"
    wall_tiles_remaining: int | None = None
    round_wind: int = SIMULATOR_DEFAULT_ROUND_WIND
    seat_wind: int = SIMULATOR_DEFAULT_SEAT_WIND
    dora_indicator_tiles_37: tuple[int, ...] = field(default_factory=tuple)
    melds: tuple[PystyleRequestMeld, ...] = field(default_factory=tuple)
    remaining_wall: tuple[int, ...] | None = None
    round_token: str = ""
    request_fallback_tile_37: int | None = None
    allow_history_persist: bool = False

    # turn_index を保持する。
    turn_index: int = SIMULATOR_FALLBACK_DISPLAY_TURN_INDEX
    # turn_source を保持する。
    turn_source: str = "frontend_fallback"
    # wall_tiles_remaining を保持する。
    wall_tiles_remaining: int | None = None


@dataclass(frozen=True)
class WallVectorEntry:
    """One explanatory row for the request-side remaining-wall count vector."""

    # tile を保持する。
    tile: int
    # tile_text を保持する。
    tile_text: str
    # remaining_count を保持する。
    remaining_count: int
    # base_count を保持する。
    base_count: int
    # hand_count を保持する。
    hand_count: int
    # dora_indicator_count を保持する。
    dora_indicator_count: int
    # note を保持する。
    note: str = ""


def build_remaining_wall_from_visible_tiles37(
    visible_tiles_37: Sequence[int],
    *,
    enable_reddora: bool = True,
) -> tuple[int, ...]:
    """Build the simulator `wall` vector from exact visible local 1..37 tiles."""

    remaining_wall = list(SIMULATOR_BASE_WALL_COUNTS)
    for tile_37 in visible_tiles_37:
        simulator_tile = tile37_to_simulator_tile(int(tile_37))
        if simulator_tile is None:
            raise ValueError(f"Unsupported local tile id: {tile_37}")
        remaining_wall[simulator_tile] -= 1
    if any(count < 0 for count in remaining_wall):
        raise ValueError("visible tiles exceed the available wall counts.")

    if enable_reddora:
        remaining_wall[4] += remaining_wall[34]
        remaining_wall[13] += remaining_wall[35]
        remaining_wall[22] += remaining_wall[36]
    else:
        remaining_wall[34] = 0
        remaining_wall[35] = 0
        remaining_wall[36] = 0
    return tuple(int(count) for count in remaining_wall)


def tile37_to_simulator_tile(tile_37: int) -> int | None:
    """Convert local 1..37 UI ids into the simulator's 0..36 tile enum."""

    if 1 <= tile_37 <= 9:
        return tile_37 - 1
    if tile_37 == 10:
        return 34
    if 11 <= tile_37 <= 19:
        return tile_37 - 2
    if tile_37 == 20:
        return 35
    if 21 <= tile_37 <= 29:
        return tile_37 - 3
    if tile_37 == 30:
        return 36
    if 31 <= tile_37 <= 37:
        return tile_37 - 4
    return None


def tile37_to_compact_text(tile_37: int) -> str:
    """Convert the local 1..37 UI tile id into compact text such as `5m` or `r5p`."""

    simulator_tile = tile37_to_simulator_tile(tile_37)
    if simulator_tile is None:
        raise ValueError(f"Unsupported local tile id: {tile_37}")
    return simulator_tile_to_text(simulator_tile, honor_style="mpsz")


def simulator_tile_to_tile37(tile: int) -> int | None:
    """Convert the simulator's 0..36 tile enum back into local 1..37 UI ids."""

    if 0 <= tile <= 8:
        return tile + 1
    if tile == 34:
        return 10
    if 9 <= tile <= 17:
        return tile + 2
    if tile == 35:
        return 20
    if 18 <= tile <= 26:
        return tile + 3
    if tile == 36:
        return 30
    if 27 <= tile <= 33:
        return tile + 4
    return None


def simulator_tile_to_text(tile: int, *, honor_style: str = "kanji") -> str:
    """Convert one simulator tile id into compact human-readable text."""

    if tile == 34:
        return "r5m"
    if tile == 35:
        return "r5p"
    if tile == 36:
        return "r5s"
    if 0 <= tile <= 8:
        return f"{tile + 1}m"
    if 9 <= tile <= 17:
        return f"{tile - 8}p"
    if 18 <= tile <= 26:
        return f"{tile - 17}s"
    if 27 <= tile <= 33:
        if honor_style == "kanji":
            return SIMULATOR_TILE_TEXT_KANJI[tile]
        return f"{tile - 26}z"
    raise ValueError(f"Unsupported simulator tile id: {tile}")


def format_simulator_tiles_compact(
    tiles: Sequence[int],
    *,
    honor_style: str = "kanji",
) -> str:
    """Render simulator tile ids as grouped compact text such as `334445m r567p 345s 白白`."""

    sorted_tiles = sorted(int(tile) for tile in tiles)
    suit_groups: list[str] = []

    # Suit tiles are grouped by their trailing suit letter while preserving red-five markers.
    for suit_start, suit_end, suit_letter in ((0, 8, "m"), (9, 17, "p"), (18, 26, "s")):
        suit_tokens: list[str] = []
        for tile in sorted_tiles:
            if suit_start <= tile <= suit_end:
                suit_tokens.append(str((tile - suit_start) + 1))
        red_tile = {0: 34, 9: 35, 18: 36}[suit_start]
        red_count = sum(1 for tile in sorted_tiles if tile == red_tile)
        suit_tokens = (
            ["r5"] * red_count
            + suit_tokens
        )
        if suit_tokens:
            suit_groups.append("".join(suit_tokens) + suit_letter)

    honor_tiles = [tile for tile in sorted_tiles if 27 <= tile <= 33]
    if honor_tiles:
        if honor_style == "kanji":
            suit_groups.append("".join(SIMULATOR_TILE_TEXT_KANJI[tile] for tile in honor_tiles))
        else:
            suit_groups.append("".join(str(tile - 26) for tile in honor_tiles) + "z")
    return " ".join(suit_groups)


def _require_mapping(data: Any, *, label: str) -> Mapping[str, Any]:
    """Validate that one decoded JSON node is a mapping."""

    if not isinstance(data, Mapping):
        raise ValueError(f"{label} must be an object.")
    return data


def _require_bool(data: Mapping[str, Any], key: str, *, label: str) -> bool:
    """Read one required boolean field."""

    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{label}.{key} must be a bool.")
    return value


def _require_int(data: Mapping[str, Any], key: str, *, label: str) -> int:
    """Read one required integer field."""

    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{label}.{key} must be an int.")
    return value


def _optional_int(data: Mapping[str, Any], key: str) -> int | None:
    """Read one optional integer field."""

    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an int when present.")
    return value


def _require_tile_id(tile: Any, *, label: str) -> int:
    """Validate one 0..36 simulator tile id."""

    if not isinstance(tile, int) or tile not in SIMULATOR_TILE_IDS:
        raise ValueError(f"{label} must be a simulator tile id in 0..36.")
    return tile


def _require_tile_id_sequence(value: Any, *, label: str) -> tuple[int, ...]:
    """Validate one simulator tile-id list."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} must be an array of simulator tile ids.")
    return tuple(_require_tile_id(tile, label=f"{label}[]") for tile in value)


def validate_request_payload(data: Mapping[str, Any]) -> PystyleRequestPayload:
    """Validate a decoded request payload without confusing it with the response body."""

    request_data = _require_mapping(data, label="request")
    known_keys = {
        "enable_reddora",
        "enable_uradora",
        "enable_shanten_down",
        "enable_tegawari",
        "enable_riichi",
        "round_wind",
        "dora_indicators",
        "hand",
        "melds",
        "seat_wind",
        "wall",
        "version",
    }
    melds_raw = request_data.get("melds")
    if not isinstance(melds_raw, Sequence) or isinstance(melds_raw, (str, bytes, bytearray)):
        raise ValueError("request.melds must be an array.")

    melds: list[PystyleRequestMeld] = []
    for index, raw_meld in enumerate(melds_raw):
        meld_data = _require_mapping(raw_meld, label=f"request.melds[{index}]")
        meld_known_keys = {"type", "tiles", "discardedTile", "from"}
        melds.append(
            PystyleRequestMeld(
                type=meld_data.get("type"),
                tiles=_require_tile_id_sequence(meld_data.get("tiles"), label=f"request.melds[{index}].tiles"),
                discarded_tile=(
                    _require_tile_id(meld_data.get("discardedTile"), label=f"request.melds[{index}].discardedTile")
                    if meld_data.get("discardedTile") is not None
                    else None
                ),
                from_seat=_optional_int(meld_data, "from"),
                extras={key: value for key, value in meld_data.items() if key not in meld_known_keys},
            )
        )

    wall = request_data.get("wall")
    if not isinstance(wall, Sequence) or isinstance(wall, (str, bytes, bytearray)):
        raise ValueError("request.wall must be an array.")
    normalized_wall = tuple(int(count) for count in wall)
    if len(normalized_wall) != SIMULATOR_TILE_COUNT:
        raise ValueError("request.wall must contain exactly 37 remaining-count slots.")
    if any(count < 0 for count in normalized_wall):
        raise ValueError("request.wall must not contain negative counts.")

    version = request_data.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("request.version must be a non-empty string.")

    return PystyleRequestPayload(
        enable_reddora=_require_bool(request_data, "enable_reddora", label="request"),
        enable_uradora=_require_bool(request_data, "enable_uradora", label="request"),
        enable_shanten_down=_require_bool(request_data, "enable_shanten_down", label="request"),
        enable_tegawari=_require_bool(request_data, "enable_tegawari", label="request"),
        enable_riichi=_require_bool(request_data, "enable_riichi", label="request"),
        round_wind=_require_tile_id(_require_int(request_data, "round_wind", label="request"), label="request.round_wind"),
        dora_indicators=_require_tile_id_sequence(request_data.get("dora_indicators"), label="request.dora_indicators"),
        hand=_require_tile_id_sequence(request_data.get("hand"), label="request.hand"),
        melds=tuple(melds),
        seat_wind=_require_tile_id(_require_int(request_data, "seat_wind", label="request"), label="request.seat_wind"),
        wall=normalized_wall,
        version=version,
        extras={key: value for key, value in request_data.items() if key not in known_keys},
    )


def request_payload_to_wire_dict(request: PystyleRequestPayload) -> dict[str, Any]:
    """Serialize a validated request model back into the JSON shape sent over the wire."""

    payload = {
        "enable_reddora": request.enable_reddora,
        "enable_uradora": request.enable_uradora,
        "enable_shanten_down": request.enable_shanten_down,
        "enable_tegawari": request.enable_tegawari,
        "enable_riichi": request.enable_riichi,
        "round_wind": request.round_wind,
        "dora_indicators": list(request.dora_indicators),
        "hand": list(request.hand),
        "melds": [
            {
                "type": meld.type,
                "tiles": list(meld.tiles),
                "discardedTile": meld.discarded_tile,
                "from": meld.from_seat,
                **meld.extras,
            }
            for meld in request.melds
        ],
        "seat_wind": request.seat_wind,
        "wall": list(request.wall),
        "version": request.version,
        **request.extras,
    }
    return payload


def build_request_payload_from_hand_tiles37(
    hand_tiles_37: Sequence[int],
    *,
    round_wind: int = SIMULATOR_DEFAULT_ROUND_WIND,
    seat_wind: int = SIMULATOR_DEFAULT_SEAT_WIND,
    dora_indicator_tiles_37: Sequence[int] | None = None,
    dora_indicators: Sequence[int] | None = None,
    melds: Sequence[PystyleRequestMeld] | None = None,
    remaining_wall: Sequence[int] | None = None,
    enable_reddora: bool = True,
    enable_uradora: bool = True,
    enable_shanten_down: bool = True,
    enable_tegawari: bool = True,
    enable_riichi: bool = False,
    version: str = SIMULATOR_VERSION,
) -> PystyleRequestPayload:
    """Build a validated request payload from local 1..37 hand tiles."""

    simulator_hand_tiles: list[int] = []
    for tile_37 in sorted(int(tile) for tile in hand_tiles_37):
        simulator_tile = tile37_to_simulator_tile(tile_37)
        if simulator_tile is None:
            raise ValueError(f"Unsupported local tile id: {tile_37}")
        simulator_hand_tiles.append(simulator_tile)

    effective_dora_indicator_tiles_37: list[int]
    if dora_indicator_tiles_37 is not None:
        effective_dora_indicator_tiles_37 = [int(tile) for tile in dora_indicator_tiles_37]
    elif dora_indicators is not None:
        effective_dora_indicator_tiles_37 = []
        for tile in dora_indicators:
            local_tile = simulator_tile_to_tile37(int(tile))
            if local_tile is None:
                raise ValueError(f"Unsupported simulator dora tile id: {tile}")
            effective_dora_indicator_tiles_37.append(local_tile)
    else:
        effective_dora_indicator_tiles_37 = [31]

    simulator_dora_indicators: list[int] = []
    for tile_37 in effective_dora_indicator_tiles_37:
        simulator_tile = tile37_to_simulator_tile(tile_37)
        if simulator_tile is None:
            raise ValueError(f"Unsupported local dora tile id: {tile_37}")
        simulator_dora_indicators.append(simulator_tile)

    if remaining_wall is None:
        remaining_wall_vector = build_remaining_wall_from_visible_tiles37(
            [*hand_tiles_37, *effective_dora_indicator_tiles_37],
            enable_reddora=enable_reddora,
        )
    else:
        remaining_wall_vector = tuple(int(count) for count in remaining_wall)

    raw_melds = [
        {
            "type": meld.type,
            "tiles": [int(tile) for tile in meld.tiles],
            **(
                {"discardedTile": int(meld.discarded_tile)}
                if meld.discarded_tile is not None
                else {}
            ),
            **(
                {"from": int(meld.from_seat)}
                if meld.from_seat is not None
                else {}
            ),
            **dict(meld.extras),
        }
        for meld in (melds or ())
    ]

    return validate_request_payload(
        {
            "enable_reddora": enable_reddora,
            "enable_uradora": enable_uradora,
            "enable_shanten_down": enable_shanten_down,
            "enable_tegawari": enable_tegawari,
            "enable_riichi": enable_riichi,
            "round_wind": round_wind,
            "dora_indicators": simulator_dora_indicators,
            "hand": simulator_hand_tiles,
            "melds": raw_melds,
            "seat_wind": seat_wind,
            "wall": remaining_wall_vector,
            "version": version,
        }
    )


def validate_response_body(data: Mapping[str, Any]) -> PystyleWireResponse:
    """Validate a decoded response body without confusing it with the request payload."""

    body = _require_mapping(data, label="response_body")
    known_top_level_keys = {"success", "request", "response", "err_msg"}
    success = body.get("success")
    if not isinstance(success, bool):
        raise ValueError("response_body.success must be a bool.")

    err_msg = body.get("err_msg")
    if err_msg is not None and not isinstance(err_msg, str):
        raise ValueError("response_body.err_msg must be a string when present.")

    request_model = None
    if body.get("request") is not None:
        request_model = validate_request_payload(_require_mapping(body.get("request"), label="response_body.request"))

    response_model = None
    if body.get("response") is not None:
        response_payload = _require_mapping(body.get("response"), label="response_body.response")
        shanten_raw = _require_mapping(response_payload.get("shanten"), label="response_body.response.shanten")
        config_raw = _require_mapping(response_payload.get("config"), label="response_body.response.config")
        stats_raw = response_payload.get("stats")
        if not isinstance(stats_raw, Sequence) or isinstance(stats_raw, (str, bytes, bytearray)):
            raise ValueError("response_body.response.stats must be an array.")

        stats: list[PystyleResponseStat] = []
        for index, raw_stat in enumerate(stats_raw):
            stat_data = _require_mapping(raw_stat, label=f"response_body.response.stats[{index}]")
            necessary_tiles_raw = stat_data.get("necessary_tiles")
            if not isinstance(necessary_tiles_raw, Sequence) or isinstance(
                necessary_tiles_raw,
                (str, bytes, bytearray),
            ):
                raise ValueError(f"response_body.response.stats[{index}].necessary_tiles must be an array.")
            necessary_tiles = tuple(
                PystyleNecessaryTile(
                    tile=_require_tile_id(
                        _require_int(
                            _require_mapping(tile_data, label=f"response_body.response.stats[{index}].necessary_tiles[{tile_index}]"),
                            "tile",
                            label=f"response_body.response.stats[{index}].necessary_tiles[{tile_index}]",
                        ),
                        label=f"response_body.response.stats[{index}].necessary_tiles[{tile_index}].tile",
                    ),
                    count=_require_int(
                        _require_mapping(tile_data, label=f"response_body.response.stats[{index}].necessary_tiles[{tile_index}]"),
                        "count",
                        label=f"response_body.response.stats[{index}].necessary_tiles[{tile_index}]",
                    ),
                )
                for tile_index, tile_data in enumerate(necessary_tiles_raw)
            )
            stats.append(
                PystyleResponseStat(
                    tile=_require_tile_id(
                        _require_int(stat_data, "tile", label=f"response_body.response.stats[{index}]"),
                        label=f"response_body.response.stats[{index}].tile",
                    ),
                    shanten=_require_int(stat_data, "shanten", label=f"response_body.response.stats[{index}]"),
                    necessary_tiles=necessary_tiles,
                    exp_score=tuple(float(value) for value in stat_data.get("exp_score", ()) or ()),
                    win_prob=tuple(float(value) for value in stat_data.get("win_prob", ()) or ()),
                    tenpai_prob=tuple(float(value) for value in stat_data.get("tenpai_prob", ()) or ()),
                    extras={
                        key: value
                        for key, value in stat_data.items()
                        if key not in {"tile", "shanten", "necessary_tiles", "exp_score", "win_prob", "tenpai_prob"}
                    },
                )
            )

        response_model = PystyleResponsePayload(
            shanten=PystyleResponseShanten(
                all=_require_int(shanten_raw, "all", label="response_body.response.shanten"),
                regular=_require_int(shanten_raw, "regular", label="response_body.response.shanten"),
                seven_pairs=_require_int(shanten_raw, "seven_pairs", label="response_body.response.shanten"),
                thirteen_orphans=_require_int(
                    shanten_raw,
                    "thirteen_orphans",
                    label="response_body.response.shanten",
                ),
                extras={
                    key: value
                    for key, value in shanten_raw.items()
                    if key not in {"all", "regular", "seven_pairs", "thirteen_orphans"}
                },
            ),
            stats=tuple(stats),
            config=PystyleResponseConfig(
                t_min=_require_int(config_raw, "t_min", label="response_body.response.config"),
                t_max=_require_int(config_raw, "t_max", label="response_body.response.config"),
                sum=_require_int(config_raw, "sum", label="response_body.response.config"),
                extra=_optional_int(config_raw, "extra"),
                shanten_type=_optional_int(config_raw, "shanten_type"),
                calc_stats=_require_bool(config_raw, "calc_stats", label="response_body.response.config"),
                num_tiles=_optional_int(config_raw, "num_tiles"),
                extras={
                    key: value
                    for key, value in config_raw.items()
                    if key not in {"t_min", "t_max", "sum", "extra", "shanten_type", "calc_stats", "num_tiles"}
                },
            ),
            searched=_optional_int(response_payload, "searched"),
            time=_optional_int(response_payload, "time"),
            extras={
                key: value
                for key, value in response_payload.items()
                if key not in {"shanten", "stats", "config", "searched", "time"}
            },
        )

    return PystyleWireResponse(
        success=success,
        request=request_model,
        response=response_model,
        err_msg=err_msg,
        extras={key: value for key, value in body.items() if key not in known_top_level_keys},
    )


def restore_wall_vector_entries(request: PystyleRequestPayload) -> tuple[WallVectorEntry, ...]:
    """Explain one request-side `wall` vector as remaining-count rows, not wall order."""

    hand_counter = Counter(request.hand)
    dora_counter = Counter(request.dora_indicators)
    entries: list[WallVectorEntry] = []
    for tile, remaining_count in enumerate(request.wall):
        note = ""
        if request.enable_reddora and tile in SIMULATOR_NORMAL_FIVE_TILE_IDS:
            paired_red_tile = SIMULATOR_RED_FIVE_TILE_IDS[SIMULATOR_NORMAL_FIVE_TILE_IDS.index(tile)]
            note = (
                "normal five slot; remaining_count already includes the paired red-five slot "
                f"({simulator_tile_to_text(paired_red_tile)})."
            )
        elif not request.enable_reddora and tile in SIMULATOR_RED_FIVE_TILE_IDS:
            note = "red-five slot forced to 0 when enable_reddora=false."
        entries.append(
            WallVectorEntry(
                tile=tile,
                tile_text=simulator_tile_to_text(tile),
                remaining_count=remaining_count,
                base_count=SIMULATOR_BASE_WALL_COUNTS[tile],
                hand_count=hand_counter.get(tile, 0),
                dora_indicator_count=dora_counter.get(tile, 0),
                note=note,
            )
        )
    return tuple(entries)


def summarize_request_example(request: PystyleRequestPayload) -> dict[str, Any]:
    """Build a compact human-readable summary for one validated request payload."""

    wall_entries = restore_wall_vector_entries(request)
    changed_entries = [
        entry
        for entry in wall_entries
        if (
            entry.hand_count > 0
            or entry.dora_indicator_count > 0
            or entry.base_count != entry.remaining_count
            or entry.note
        )
    ]
    return {
        "round_wind": simulator_tile_to_text(request.round_wind),
        "seat_wind": simulator_tile_to_text(request.seat_wind),
        "dora_indicators": [simulator_tile_to_text(tile) for tile in request.dora_indicators],
        "hand_compact": format_simulator_tiles_compact(request.hand),
        "meld_count": len(request.melds),
        "wall_changes": [
            {
                "tile": entry.tile,
                "tile_text": entry.tile_text,
                "remaining_count": entry.remaining_count,
                "base_count": entry.base_count,
                "hand_count": entry.hand_count,
                "dora_indicator_count": entry.dora_indicator_count,
                "note": entry.note,
            }
            for entry in changed_entries
        ],
    }


def build_debug_log_payload(
    *,
    request_payload: PystyleRequestPayload,
    raw_response_body: Mapping[str, Any] | None,
    parsed_response: PystyleWireResponse | None,
    display_context: PystyleDisplayContext,
    top_ranked_tiles: Sequence[str] = (),
) -> dict[str, Any]:
    """Return a request/response/render-separated debug record design."""

    return {
        "request_payload": request_payload_to_wire_dict(request_payload),
        "response_body": dict(raw_response_body) if raw_response_body is not None else None,
        "render_context": {
            "display_turn_index": display_context.turn_index,
            "display_turn_source": display_context.turn_source,
            "top_ranked_tiles": list(top_ranked_tiles),
            "response_success": parsed_response.success if parsed_response is not None else None,
            "response_error": parsed_response.err_msg if parsed_response is not None else None,
        },
        "todo_unconfirmed": [
            "MeldType enum numeric values are not confirmed from the backend.",
            "The backend may emit additional response fields beyond the validated subset.",
            "The frontend display turn source is separate from the POST payload and is not fully wired here.",
        ],
    }
