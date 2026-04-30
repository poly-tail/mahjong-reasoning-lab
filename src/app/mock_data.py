from __future__ import annotations

from dataclasses import dataclass

from capture.state import (
    MELD_FROM_PLAYER_TO_CODE,
    Meld,
    RED_TILE_IDS_136,
    meld_from_player_to_seat,
    tile136_to_tile34_index,
    tile136_to_tile37,
    tile136_to_tile37_index,
)
from sutehai import Player, SutehaiTracker

# `--mock` の既定値と、互換 alias が参照する旧パターン番号。
DEFAULT_MOCK_PATTERN = 1
# LEGACY_MOCK_PATTERN の定義。
LEGACY_MOCK_PATTERN = 2
# AVAILABLE_MOCK_PATTERNS の並びを定義する。
AVAILABLE_MOCK_PATTERNS = (1, 2, 3)
# mock では 4 人とも 17 枚捨てに統一する。
MOCK_DISCARDS_PER_PLAYER = 17
# MOCK_HAND_TILE_COUNT の定義。
MOCK_HAND_TILE_COUNT = 13


# MockTileInputs クラスを定義する。
@dataclass(frozen=True)
class MockTileInputs:
    # mock の正本入力はすべて raw 136 で持つ。
    # 描画や tracker 反映の直前にだけ 37 種へ変換する。
    hand_tiles_136: list[int]
    # meld_tiles_136 の一覧。
    meld_tiles_136: list[int]
    # dora_indicator_tiles_136 の一覧。
    dora_indicator_tiles_136: list[int]
    # discard_events_136 の一覧。
    discard_events_136: list[tuple[Player, int, bool]]


# MockMeldSpec クラスを定義する。
@dataclass(frozen=True)
class MockMeldSpec:
    # actor を保持する。
    actor: Player
    # meld_type を保持する。
    meld_type: str
    # from_player を保持する。
    from_player: str
    # tiles_136 の並びを保持する。
    tiles_136: tuple[int, ...]
    # consumed_from_hand_136 の並びを保持する。
    consumed_from_hand_136: tuple[int, ...]
    # called_index を保持する。
    called_index: int | None = None


# 3 パターン共通の自家手牌。赤牌は raw ID のまま明示している。
_COMMON_HAND_TILES_136_INPUT = [
    0,
    4,
    8,
    12,
    17,
    20,
    24,
    28,
    32,
    40,
    44,
    48,
    53,
]

# _MOCK_MELD_SPECS_BY_PATTERN の対応表。
_MOCK_MELD_SPECS_BY_PATTERN = {
    1: (
        MockMeldSpec(
            actor=Player.JICHA,
            meld_type="chi",
            from_player="kamicha",
            tiles_136=(78, 80, 85),
            consumed_from_hand_136=(78, 85),
            called_index=1,
        ),
        MockMeldSpec(
            actor=Player.SHIMOCHA,
            meld_type="pon",
            from_player="shimocha",
            tiles_136=(69, 70, 71),
            consumed_from_hand_136=(70, 71),
            called_index=0,
        ),
        MockMeldSpec(
            actor=Player.TOIMEN,
            meld_type="chi",
            from_player="shimocha",
            tiles_136=(84, 89, 93),
            consumed_from_hand_136=(89, 93),
            called_index=0,
        ),
        MockMeldSpec(
            actor=Player.KAMICHA,
            meld_type="chi",
            from_player="kamicha",
            tiles_136=(74, 77, 81),
            consumed_from_hand_136=(74, 81),
            called_index=1,
        ),
    ),
    2: (
        MockMeldSpec(
            actor=Player.JICHA,
            meld_type="chi",
            from_player="kamicha",
            tiles_136=(79, 82, 87),
            consumed_from_hand_136=(79, 87),
            called_index=1,
        ),
        MockMeldSpec(
            actor=Player.SHIMOCHA,
            meld_type="pon",
            from_player="shimocha",
            tiles_136=(128, 130, 131),
            consumed_from_hand_136=(130, 131),
            called_index=0,
        ),
        MockMeldSpec(
            actor=Player.TOIMEN,
            meld_type="chi",
            from_player="kamicha",
            tiles_136=(63, 67, 69),
            consumed_from_hand_136=(63, 67),
            called_index=2,
        ),
        MockMeldSpec(
            actor=Player.KAMICHA,
            meld_type="chi",
            from_player="kamicha",
            tiles_136=(21, 26, 30),
            consumed_from_hand_136=(26, 30),
            called_index=0,
        ),
    ),
    3: (
        MockMeldSpec(
            actor=Player.JICHA,
            meld_type="chi",
            from_player="kamicha",
            tiles_136=(77, 80, 85),
            consumed_from_hand_136=(77, 85),
            called_index=1,
        ),
        MockMeldSpec(
            actor=Player.SHIMOCHA,
            meld_type="pon",
            from_player="shimocha",
            tiles_136=(68, 69, 71),
            consumed_from_hand_136=(68, 71),
            called_index=1,
        ),
        MockMeldSpec(
            actor=Player.TOIMEN,
            meld_type="chi",
            from_player="shimocha",
            tiles_136=(73, 76, 81),
            consumed_from_hand_136=(73, 81),
            called_index=1,
        ),
        MockMeldSpec(
            actor=Player.KAMICHA,
            meld_type="chi",
            from_player="shimocha",
            tiles_136=(57, 62, 64),
            consumed_from_hand_136=(57, 64),
            called_index=1,
        ),
    ),
}


def _meld_tiles_input_from_specs(specs: tuple[MockMeldSpec, ...]) -> list[int]:
    return [
        tile_136
        for spec in specs
        for tile_136 in spec.consumed_from_hand_136
    ]

# 各パターンの捨て牌正本。seat / tile_136 / tsumogiri の順で持つ。
_MOCK_DISCARD_EVENTS_PATTERN_1_136_INPUT = [
    (Player.JICHA, 2, False),
    (Player.JICHA, 6, True),
    (Player.JICHA, 10, False),
    (Player.JICHA, 14, False),
    (Player.JICHA, 18, True),
    (Player.JICHA, 22, False),
    (Player.JICHA, 26, False),
    (Player.JICHA, 30, True),
    (Player.JICHA, 34, False),
    (Player.JICHA, 36, False),
    (Player.JICHA, 41, True),
    (Player.JICHA, 45, False),
    (Player.JICHA, 49, False),
    (Player.JICHA, 54, True),
    (Player.JICHA, 58, False),
    (Player.JICHA, 62, False),
    (Player.JICHA, 66, True),
    (Player.SHIMOCHA, 3, False),
    (Player.SHIMOCHA, 7, True),
    (Player.SHIMOCHA, 11, False),
    (Player.SHIMOCHA, 15, False),
    (Player.SHIMOCHA, 19, True),
    (Player.SHIMOCHA, 23, False),
    (Player.SHIMOCHA, 27, False),
    (Player.SHIMOCHA, 31, True),
    (Player.SHIMOCHA, 35, False),
    (Player.SHIMOCHA, 37, False),
    (Player.SHIMOCHA, 42, True),
    (Player.SHIMOCHA, 46, False),
    (Player.SHIMOCHA, 50, False),
    (Player.SHIMOCHA, 55, True),
    (Player.SHIMOCHA, 59, False),
    (Player.SHIMOCHA, 63, False),
    (Player.SHIMOCHA, 67, True),
    (Player.TOIMEN, 5, False),
    (Player.TOIMEN, 9, True),
    (Player.TOIMEN, 13, False),
    (Player.TOIMEN, 21, False),
    (Player.TOIMEN, 25, True),
    (Player.TOIMEN, 29, False),
    (Player.TOIMEN, 33, False),
    (Player.TOIMEN, 38, True),
    (Player.TOIMEN, 43, False),
    (Player.TOIMEN, 47, False),
    (Player.TOIMEN, 51, True),
    (Player.TOIMEN, 56, False),
    (Player.TOIMEN, 61, False),
    (Player.TOIMEN, 65, True),
    (Player.TOIMEN, 69, False),
    (Player.TOIMEN, 73, False),
    (Player.TOIMEN, 77, True),
    (Player.KAMICHA, 39, False),
    (Player.KAMICHA, 52, True),
    (Player.KAMICHA, 57, False),
    (Player.KAMICHA, 64, False),
    (Player.KAMICHA, 68, True),
    (Player.KAMICHA, 72, False),
    (Player.KAMICHA, 76, False),
    (Player.KAMICHA, 80, True),
    (Player.KAMICHA, 84, False),
    (Player.KAMICHA, 88, False),
    (Player.KAMICHA, 92, True),
    (Player.KAMICHA, 96, False),
    (Player.KAMICHA, 100, False),
    (Player.KAMICHA, 104, True),
    (Player.KAMICHA, 108, False),
    (Player.KAMICHA, 112, False),
    (Player.KAMICHA, 116, True),
]

# _MOCK_DISCARD_EVENTS_PATTERN_2_136_INPUT の一覧。
_MOCK_DISCARD_EVENTS_PATTERN_2_136_INPUT = [
    (Player.JICHA, 1, False),
    (Player.JICHA, 18, True),
    (Player.JICHA, 64, False),
    (Player.JICHA, 68, False),
    (Player.JICHA, 72, True),
    (Player.JICHA, 76, False),
    (Player.JICHA, 80, False),
    (Player.JICHA, 84, True),
    (Player.JICHA, 89, False),
    (Player.JICHA, 92, False),
    (Player.JICHA, 96, True),
    (Player.JICHA, 100, False),
    (Player.JICHA, 104, False),
    (Player.JICHA, 108, True),
    (Player.JICHA, 112, False),
    (Player.JICHA, 116, False),
    (Player.JICHA, 120, True),
    (Player.SHIMOCHA, 5, False),
    (Player.SHIMOCHA, 19, True),
    (Player.SHIMOCHA, 65, False),
    (Player.SHIMOCHA, 69, False),
    (Player.SHIMOCHA, 73, True),
    (Player.SHIMOCHA, 77, False),
    (Player.SHIMOCHA, 81, False),
    (Player.SHIMOCHA, 85, True),
    (Player.SHIMOCHA, 90, False),
    (Player.SHIMOCHA, 93, False),
    (Player.SHIMOCHA, 97, True),
    (Player.SHIMOCHA, 101, False),
    (Player.SHIMOCHA, 105, False),
    (Player.SHIMOCHA, 109, True),
    (Player.SHIMOCHA, 113, False),
    (Player.SHIMOCHA, 117, False),
    (Player.SHIMOCHA, 121, True),
    (Player.TOIMEN, 9, False),
    (Player.TOIMEN, 13, True),
    (Player.TOIMEN, 21, False),
    (Player.TOIMEN, 25, False),
    (Player.TOIMEN, 29, True),
    (Player.TOIMEN, 33, False),
    (Player.TOIMEN, 41, False),
    (Player.TOIMEN, 45, True),
    (Player.TOIMEN, 49, False),
    (Player.TOIMEN, 54, False),
    (Player.TOIMEN, 57, True),
    (Player.TOIMEN, 61, False),
    (Player.TOIMEN, 66, False),
    (Player.TOIMEN, 70, True),
    (Player.TOIMEN, 74, False),
    (Player.TOIMEN, 124, False),
    (Player.TOIMEN, 128, True),
    (Player.KAMICHA, 62, False),
    (Player.KAMICHA, 78, True),
    (Player.KAMICHA, 82, False),
    (Player.KAMICHA, 86, False),
    (Player.KAMICHA, 91, True),
    (Player.KAMICHA, 94, False),
    (Player.KAMICHA, 98, False),
    (Player.KAMICHA, 102, True),
    (Player.KAMICHA, 106, False),
    (Player.KAMICHA, 110, False),
    (Player.KAMICHA, 114, True),
    (Player.KAMICHA, 118, False),
    (Player.KAMICHA, 122, False),
    (Player.KAMICHA, 125, True),
    (Player.KAMICHA, 129, False),
    (Player.KAMICHA, 132, False),
    (Player.KAMICHA, 133, True),
]

# _MOCK_DISCARD_EVENTS_PATTERN_3_136_INPUT の一覧。
_MOCK_DISCARD_EVENTS_PATTERN_3_136_INPUT = [
    (Player.JICHA, 1, False),
    (Player.JICHA, 5, True),
    (Player.JICHA, 9, False),
    (Player.JICHA, 13, False),
    (Player.JICHA, 18, True),
    (Player.JICHA, 22, False),
    (Player.JICHA, 26, False),
    (Player.JICHA, 30, True),
    (Player.JICHA, 34, False),
    (Player.JICHA, 38, False),
    (Player.JICHA, 42, True),
    (Player.JICHA, 46, False),
    (Player.JICHA, 50, False),
    (Player.JICHA, 54, True),
    (Player.JICHA, 58, False),
    (Player.JICHA, 62, False),
    (Player.JICHA, 66, True),
    (Player.SHIMOCHA, 2, False),
    (Player.SHIMOCHA, 6, True),
    (Player.SHIMOCHA, 10, False),
    (Player.SHIMOCHA, 14, False),
    (Player.SHIMOCHA, 19, True),
    (Player.SHIMOCHA, 23, False),
    (Player.SHIMOCHA, 27, False),
    (Player.SHIMOCHA, 31, True),
    (Player.SHIMOCHA, 35, False),
    (Player.SHIMOCHA, 39, False),
    (Player.SHIMOCHA, 43, True),
    (Player.SHIMOCHA, 47, False),
    (Player.SHIMOCHA, 51, False),
    (Player.SHIMOCHA, 55, True),
    (Player.SHIMOCHA, 59, False),
    (Player.SHIMOCHA, 63, False),
    (Player.SHIMOCHA, 67, True),
    (Player.TOIMEN, 3, False),
    (Player.TOIMEN, 7, True),
    (Player.TOIMEN, 11, False),
    (Player.TOIMEN, 15, False),
    (Player.TOIMEN, 21, True),
    (Player.TOIMEN, 25, False),
    (Player.TOIMEN, 29, False),
    (Player.TOIMEN, 33, True),
    (Player.TOIMEN, 37, False),
    (Player.TOIMEN, 41, False),
    (Player.TOIMEN, 45, True),
    (Player.TOIMEN, 49, False),
    (Player.TOIMEN, 52, False),
    (Player.TOIMEN, 56, True),
    (Player.TOIMEN, 61, False),
    (Player.TOIMEN, 65, False),
    (Player.TOIMEN, 69, True),
    (Player.KAMICHA, 70, False),
    (Player.KAMICHA, 72, True),
    (Player.KAMICHA, 74, False),
    (Player.KAMICHA, 76, False),
    (Player.KAMICHA, 78, True),
    (Player.KAMICHA, 80, False),
    (Player.KAMICHA, 82, False),
    (Player.KAMICHA, 84, True),
    (Player.KAMICHA, 86, False),
    (Player.KAMICHA, 88, False),
    (Player.KAMICHA, 90, True),
    (Player.KAMICHA, 92, False),
    (Player.KAMICHA, 94, False),
    (Player.KAMICHA, 96, True),
    (Player.KAMICHA, 98, False),
    (Player.KAMICHA, 100, False),
    (Player.KAMICHA, 102, True),
]

# _RAW_MOCK_INPUTS_BY_PATTERN の対応表。
_RAW_MOCK_INPUTS_BY_PATTERN = {
    1: MockTileInputs(
        # pattern 1 はドラ表示牌 1 枚。
        hand_tiles_136=list(_COMMON_HAND_TILES_136_INPUT),
        meld_tiles_136=_meld_tiles_input_from_specs(_MOCK_MELD_SPECS_BY_PATTERN[1]),
        dora_indicator_tiles_136=[16],
        discard_events_136=list(_MOCK_DISCARD_EVENTS_PATTERN_1_136_INPUT),
    ),
    2: MockTileInputs(
        # pattern 2 は既存 mock 相当でドラ表示牌 2 枚。
        hand_tiles_136=list(_COMMON_HAND_TILES_136_INPUT),
        meld_tiles_136=_meld_tiles_input_from_specs(_MOCK_MELD_SPECS_BY_PATTERN[2]),
        dora_indicator_tiles_136=[16, 60],
        discard_events_136=list(_MOCK_DISCARD_EVENTS_PATTERN_2_136_INPUT),
    ),
    3: MockTileInputs(
        # pattern 3 はドラ表示牌 3 枚。
        hand_tiles_136=list(_COMMON_HAND_TILES_136_INPUT),
        meld_tiles_136=_meld_tiles_input_from_specs(_MOCK_MELD_SPECS_BY_PATTERN[3]),
        dora_indicator_tiles_136=[16, 60, 126],
        discard_events_136=list(_MOCK_DISCARD_EVENTS_PATTERN_3_136_INPUT),
    ),
}


def tiles136_to_tiles37(tile_ids_136: list[int]) -> list[int]:
    # mock の描画直前変換。invalid 値があれば即失敗させる。
    tiles_37 = [tile136_to_tile37(tile_136) for tile_136 in tile_ids_136]
    if any(tile_37 is None for tile_37 in tiles_37):
        raise ValueError("Mock tile conversion from 136 to 37 failed.")
    return [tile_37 for tile_37 in tiles_37 if tile_37 is not None]


def _build_mock_meld(spec: MockMeldSpec, meld_id: str) -> Meld:
    # mock 表示用の簡易 `Meld` を raw 136 から組み立てる。
    tiles_136 = list(spec.tiles_136)
    consumed_from_hand_136 = list(spec.consumed_from_hand_136)
    tiles_37 = tiles136_to_tiles37(tiles_136)
    target_tile_136 = None
    if spec.called_index is not None:
        target_tile_136 = tiles_136[spec.called_index]
    return Meld(
        who=int(spec.actor),
        raw_m=0,
        meld_type=spec.meld_type,
        tile_34=tile136_to_tile34_index(target_tile_136 if target_tile_136 is not None else tiles_136[0]),
        tile_37=tile136_to_tile37_index(target_tile_136 if target_tile_136 is not None else tiles_136[0]),
        from_who=MELD_FROM_PLAYER_TO_CODE[spec.from_player],
        consumed_tile_ids=consumed_from_hand_136,
        called_tile_id=target_tile_136,
        is_open=(spec.meld_type != "kan_closed"),
        upgraded_from=None,
        meld_id=meld_id,
        from_player=spec.from_player,
        tiles_136=tiles_136,
        tiles_37=tiles_37,
        called_index=spec.called_index,
        rotate_index=spec.called_index,
    )


def _copy_mock_inputs(mock_inputs: MockTileInputs) -> MockTileInputs:
    # 呼び出し側で list を破壊変更しても正本へ影響しないよう毎回コピーを返す。
    return MockTileInputs(
        hand_tiles_136=list(mock_inputs.hand_tiles_136),
        meld_tiles_136=list(mock_inputs.meld_tiles_136),
        dora_indicator_tiles_136=list(mock_inputs.dora_indicator_tiles_136),
        discard_events_136=list(mock_inputs.discard_events_136),
    )


def _validate_tile_ids_136(tile_ids_136: list[int], label: str) -> None:
    # mock 正本に範囲外 ID が紛れたら起動時に止める。
    for tile_136 in tile_ids_136:
        if not 0 <= tile_136 <= 135:
            raise ValueError(f"Mock {label} contains invalid tile_136={tile_136}")


def _validate_mock_inputs(pattern_id: int, mock_inputs: MockTileInputs) -> None:
    # まず各配列ごとの tile_136 範囲を確認する。
    _validate_tile_ids_136(mock_inputs.hand_tiles_136, "hand")
    _validate_tile_ids_136(mock_inputs.meld_tiles_136, "meld")
    _validate_tile_ids_136(mock_inputs.dora_indicator_tiles_136, "dora")
    _validate_tile_ids_136(
        [tile_136 for _seat, tile_136, _tsumogiri in mock_inputs.discard_events_136],
        "discards",
    )

    if pattern_id not in AVAILABLE_MOCK_PATTERNS:
        raise ValueError(f"Unsupported mock pattern: {pattern_id}")
    if len(mock_inputs.hand_tiles_136) != MOCK_HAND_TILE_COUNT:
        raise ValueError(f"Mock hand count is invalid for pattern {pattern_id}: {len(mock_inputs.hand_tiles_136)}")
    if len(mock_inputs.dora_indicator_tiles_136) != pattern_id:
        raise ValueError(
            f"Mock pattern {pattern_id} must contain {pattern_id} dora indicators: "
            f"{len(mock_inputs.dora_indicator_tiles_136)}"
        )

    # 手牌・副露・ドラ・捨て牌をまとめて、一意性と総枚数を検証する。
    all_tiles_136 = (
        list(mock_inputs.hand_tiles_136)
        + list(mock_inputs.meld_tiles_136)
        + list(mock_inputs.dora_indicator_tiles_136)
        + [tile_136 for _seat, tile_136, _tsumogiri in mock_inputs.discard_events_136]
    )
    expected_total = (
        MOCK_HAND_TILE_COUNT
        + len(mock_inputs.meld_tiles_136)
        + pattern_id
        + MOCK_DISCARDS_PER_PLAYER * len(Player)
    )
    if len(all_tiles_136) != expected_total:
        raise ValueError(
            f"Mock total tile count is invalid for pattern {pattern_id}: "
            f"{len(all_tiles_136)} != {expected_total}"
        )
    if len(all_tiles_136) != len(set(all_tiles_136)):
        raise ValueError(f"Mock pattern {pattern_id} contains duplicate tile_136 values.")

    # 赤牌は 136 枚体系では各 1 枚しか存在しない。
    red_tile_count = sum(1 for tile_136 in all_tiles_136 if tile_136 in RED_TILE_IDS_136)
    if red_tile_count > len(RED_TILE_IDS_136):
        raise ValueError(f"Mock pattern {pattern_id} contains too many red tiles.")

    # 4 人とも 17 枚捨てで揃っていることを確認する。
    for player in Player:
        discard_count = sum(
            1
            for seat, _tile_136, _tsumogiri in mock_inputs.discard_events_136
            if seat == player
        )
        if discard_count != MOCK_DISCARDS_PER_PLAYER:
            raise ValueError(
                f"Mock discard count is invalid for pattern {pattern_id} {player.name}: {discard_count}"
            )


def _validate_mock_meld_specs(pattern_id: int, mock_inputs: MockTileInputs) -> None:
    """Validate meld/discard consistency for a mock pattern."""

    try:
        meld_specs = _MOCK_MELD_SPECS_BY_PATTERN[pattern_id]
    except KeyError as exc:
        raise ValueError(f"Missing mock meld specs for pattern {pattern_id}") from exc

    expected_meld_tiles_136 = _meld_tiles_input_from_specs(meld_specs)
    if sorted(mock_inputs.meld_tiles_136) != sorted(expected_meld_tiles_136):
        raise ValueError(f"Mock meld tiles are inconsistent for pattern {pattern_id}.")

    open_meld_types = {"chi", "pon", "kan_open"}
    meld_counts_by_actor = {player: 0 for player in Player}
    discard_event_keys = {(seat, tile_136) for seat, tile_136, _tsumogiri in mock_inputs.discard_events_136}
    used_called_discard_keys: set[tuple[Player, int]] = set()

    for spec in meld_specs:
        meld_counts_by_actor[spec.actor] += 1
        if meld_counts_by_actor[spec.actor] > 4:
            raise ValueError(
                f"Mock pattern {pattern_id} exceeds four melds for {spec.actor.name}."
            )

        if spec.called_index is None:
            if spec.meld_type in open_meld_types:
                raise ValueError(
                    f"Mock pattern {pattern_id} open meld is missing called_index for {spec.actor.name}."
                )
            continue

        if not 0 <= spec.called_index < len(spec.tiles_136):
            raise ValueError(f"Mock pattern {pattern_id} has an invalid called_index.")

        if spec.meld_type not in open_meld_types:
            continue

        source_seat_index = meld_from_player_to_seat(int(spec.actor), spec.from_player)
        if source_seat_index is None:
            raise ValueError(f"Mock pattern {pattern_id} has an invalid from_player value.")
        source_seat = Player(source_seat_index)
        discard_key = (source_seat, spec.tiles_136[spec.called_index])
        if discard_key not in discard_event_keys:
            raise ValueError(
                f"Mock pattern {pattern_id} is missing source discard for "
                f"{spec.actor.name} {spec.meld_type}."
            )
        if discard_key in used_called_discard_keys:
            raise ValueError(
                f"Mock pattern {pattern_id} reuses the same source discard twice."
            )
        used_called_discard_keys.add(discard_key)


def _build_mock_inputs_by_pattern() -> dict[int, MockTileInputs]:
    # import 時に全 pattern を検証しておく。
    mock_inputs_by_pattern: dict[int, MockTileInputs] = {}
    for pattern_id, mock_inputs in _RAW_MOCK_INPUTS_BY_PATTERN.items():
        copied_inputs = _copy_mock_inputs(mock_inputs)
        _validate_mock_inputs(pattern_id, copied_inputs)
        _validate_mock_meld_specs(pattern_id, copied_inputs)
        mock_inputs_by_pattern[pattern_id] = copied_inputs
    return mock_inputs_by_pattern


# _MOCK_INPUTS_BY_PATTERN の定義。
_MOCK_INPUTS_BY_PATTERN = _build_mock_inputs_by_pattern()


def get_mock_inputs(mock_pattern: int = DEFAULT_MOCK_PATTERN) -> MockTileInputs:
    # 呼び出しごとにコピーを返して、呼び出し側の変更を隔離する。
    try:
        return _copy_mock_inputs(_MOCK_INPUTS_BY_PATTERN[mock_pattern])
    except KeyError as exc:
        raise ValueError(f"Unsupported mock pattern: {mock_pattern}") from exc


# 既存コード互換用の既定 pattern 2。
_LEGACY_MOCK_INPUTS = get_mock_inputs(LEGACY_MOCK_PATTERN)

# _LEGACY_MOCK_INPUTS の定義。
_LEGACY_MOCK_INPUTS = get_mock_inputs(LEGACY_MOCK_PATTERN)


def build_mock_meld_map(mock_pattern: int = DEFAULT_MOCK_PATTERN) -> dict[Player, list[Meld]]:
    """mock 用の鳴き一覧を座席 enum キーで返す。"""

    try:
        meld_specs = _MOCK_MELD_SPECS_BY_PATTERN[mock_pattern]
    except KeyError as exc:
        raise ValueError(f"Unsupported mock pattern: {mock_pattern}") from exc
    meld_map = {player: [] for player in Player}
    for index, spec in enumerate(meld_specs):
        meld_map[spec.actor].append(
            _build_mock_meld(spec, meld_id=f"mock-meld-{index}-{spec.actor.name.lower()}")
        )
    return meld_map


def _mark_mock_called_discards(
    tracker: SutehaiTracker,
    mock_pattern: int,
) -> None:
    """Mark mock discards that are consumed by open melds."""

    mock_inputs = get_mock_inputs(mock_pattern)
    discard_index_by_raw: dict[tuple[Player, int], int] = {}
    tracker_indexes_by_seat = {player: 0 for player in Player}
    for seat, tile_136, _tsumogiri in mock_inputs.discard_events_136:
        discard_index_by_raw[(seat, tile_136)] = tracker_indexes_by_seat[seat]
        tracker_indexes_by_seat[seat] += 1

    for spec in _MOCK_MELD_SPECS_BY_PATTERN[mock_pattern]:
        if spec.meld_type not in {"chi", "pon", "kan_open"}:
            continue
        if spec.called_index is None:
            continue

        source_seat_index = meld_from_player_to_seat(int(spec.actor), spec.from_player)
        if source_seat_index is None:
            continue
        source_seat = Player(source_seat_index)
        called_tile_136 = spec.tiles_136[spec.called_index]
        discard_index = discard_index_by_raw.get((source_seat, called_tile_136))
        if discard_index is None:
            raise ValueError(
                f"Mock pattern {mock_pattern} meld source discard is missing: "
                f"{source_seat.name} tile_136={called_tile_136}"
            )

        seat_discards = tracker.discards[source_seat]
        if 0 <= discard_index < len(seat_discards):
            seat_discards[discard_index].called = True


# MOCK_HAND_TILES_136 の一覧。
MOCK_HAND_TILES_136 = list(_LEGACY_MOCK_INPUTS.hand_tiles_136)
# 互換公開の副露配列も、現行描画・見え牌集計と同じく面子 full 牌を返す。
# 鳴かれた捨て牌との重複は `Discard.called` 側で除外する。
MOCK_MELD_TILES_136 = list(_LEGACY_MOCK_INPUTS.meld_tiles_136)
# MOCK_DORA_INDICATOR_TILES_136 の一覧。
MOCK_DORA_INDICATOR_TILES_136 = list(_LEGACY_MOCK_INPUTS.dora_indicator_tiles_136)
# MOCK_DISCARD_EVENTS_136 の一覧。
MOCK_DISCARD_EVENTS_136 = list(_LEGACY_MOCK_INPUTS.discard_events_136)
# MOCK_TILE_POOL_136 の型定義。
MOCK_TILE_POOL_136 = (
    list(MOCK_HAND_TILES_136)
    + list(MOCK_MELD_TILES_136)
    + list(MOCK_DORA_INDICATOR_TILES_136)
    + [tile_136 for _seat, tile_136, _tsumogiri in MOCK_DISCARD_EVENTS_136]
)

# MOCK_HAND_TILES_37 の定義。
MOCK_HAND_TILES_37 = tiles136_to_tiles37(MOCK_HAND_TILES_136)
# MOCK_MELD_TILES_37 の定義。
MOCK_MELD_TILES_37 = tiles136_to_tiles37(MOCK_MELD_TILES_136)
# MOCK_DORA_INDICATOR_TILES_37 の定義。
MOCK_DORA_INDICATOR_TILES_37 = tiles136_to_tiles37(MOCK_DORA_INDICATOR_TILES_136)

# 旧コードは 37 種 ID 前提なので alias を残す。
MOCK_HAND_TILES = MOCK_HAND_TILES_37
# MOCK_MELD_TILES の型定義。
MOCK_MELD_TILES = MOCK_MELD_TILES_37
# MOCK_DORA_INDICATOR_TILES の型定義。
MOCK_DORA_INDICATOR_TILES = MOCK_DORA_INDICATOR_TILES_37


def build_mock_tracker(mock_pattern: int = DEFAULT_MOCK_PATTERN) -> SutehaiTracker:
    """unique な raw 136 捨て牌列から tracker を組み立てる。"""

    tracker = SutehaiTracker()
    timestamp = 0.0
    for seat, tile_136, tsumogiri in get_mock_inputs(mock_pattern).discard_events_136:
        # tracker は 37 種前提なのでここで変換する。
        tile_37 = tile136_to_tile37(tile_136)
        if tile_37 is None:
            raise ValueError(f"Failed to convert mock discard tile: {tile_136}")
        tracker.add_discard(
            seat,
            tile_37,
            tsumogiri=tsumogiri,
            tag=f"{seat.name[0]}{tile_136}",
            timestamp=timestamp,
        )
        timestamp += 1.2
    _mark_mock_called_discards(tracker, mock_pattern)
    return tracker
