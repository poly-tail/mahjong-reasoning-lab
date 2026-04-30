from __future__ import annotations

from capture.state import (
    MELD_FROM_PLAYER_BY_CODE,
    Meld,
    tile136_to_tile34_index,
    tile136_to_tile37,
    tile136_to_tile37_index,
)


def _all_tiles_136(tile_kind_34: int) -> list[int]:
    """Return the four raw tile ids for a single 34-kind tile."""

    return [4 * tile_kind_34 + offset for offset in range(4)]


def _triplet_tiles_136_excluding_copy(tile_kind_34: int, excluded_copy_index: int) -> list[int]:
    """Return the three raw tile ids used by a pon/kakan in canonical copy order."""

    return [
        4 * tile_kind_34 + copy_index
        for copy_index in range(4)
        if copy_index != excluded_copy_index
    ]


def _build_meld(
    *,
    who: int,
    meld_type: str,
    from_code: int,
    tiles_136: list[int],
    consumed_tile_ids: list[int],
    raw_m: int,
    called_tile_id: int | None,
    called_index: int | None,
    rotate_index: int | None,
    is_open: bool,
) -> Meld:
    """Build a Meld with both spec-oriented and UI-oriented derived values."""

    representative_tile = called_tile_id if called_tile_id is not None else (tiles_136[0] if tiles_136 else None)
    tiles_34 = [
        tile_34
        for tile_34 in (tile136_to_tile34_index(tile_136) for tile_136 in tiles_136)
        if tile_34 is not None
    ]
    tiles_37 = [
        tile_id
        for tile_id in (tile136_to_tile37(tile_136) for tile_136 in tiles_136)
        if tile_id is not None
    ]
    return Meld(
        who=who,
        raw_m=raw_m,
        meld_type=meld_type,
        tile_34=tile136_to_tile34_index(representative_tile),
        tile_37=tile136_to_tile37_index(representative_tile),
        from_who=from_code,
        consumed_tile_ids=list(consumed_tile_ids),
        called_tile_id=called_tile_id,
        is_open=is_open,
        tiles_136=list(tiles_136),
        tiles_34=tiles_34,
        tiles_37=tiles_37,
        from_player=MELD_FROM_PLAYER_BY_CODE.get(from_code, "self"),
        called_index=called_index,
        rotate_index=rotate_index,
    )


def decode_meld(seat: int, meld_code: int) -> Meld:
    """Decode Tenhou's packed meld integer into a structured Meld.

    Supported meld kinds:
    - chi
    - pon
    - daiminkan
    - ankan
    - kakan
    """

    if meld_code < 0:
        raise ValueError(f"Invalid meld code: {meld_code}")

    # Lowest two bits encode the relative source seat.
    from_who = meld_code & 0x3

    if meld_code & 0x4:
        # Chi:
        #   bit 2 marks sequence calls.
        #   each consumed tile keeps a 0..3 copy selector.
        t0 = (meld_code >> 3) & 0x3
        t1 = (meld_code >> 5) & 0x3
        t2 = (meld_code >> 7) & 0x3
        base_and_called = meld_code >> 10
        called_tile_index = base_and_called % 3
        base = base_and_called // 3
        tile_kind_34 = (base // 7) * 9 + (base % 7)
        tiles_136 = [
            4 * (tile_kind_34 + 0) + t0,
            4 * (tile_kind_34 + 1) + t1,
            4 * (tile_kind_34 + 2) + t2,
        ]
        consumed_tile_ids = [
            tile_136
            for index, tile_136 in enumerate(tiles_136)
            if index != called_tile_index
        ]
        return _build_meld(
            who=seat,
            meld_type="chi",
            from_code=from_who,
            tiles_136=tiles_136,
            consumed_tile_ids=consumed_tile_ids,
            raw_m=meld_code,
            called_tile_id=tiles_136[called_tile_index],
            called_index=called_tile_index,
            rotate_index=called_tile_index,
            is_open=True,
        )

    if meld_code & 0x18:
        # Pon / Kakan:
        #   bit 3 indicates pon
        #   bit 4 combined with the above encodes the extended added-kan layout
        unused_copy_index = (meld_code >> 5) & 0x3
        base_and_called = meld_code >> 9
        called_tile_index = base_and_called % 3
        tile_kind_34 = base_and_called // 3
        if not 0 <= tile_kind_34 <= 33:
            raise ValueError(f"Invalid pon/kakan tile kind: {tile_kind_34}")

        triplet_tiles_136 = _triplet_tiles_136_excluding_copy(tile_kind_34, unused_copy_index)

        if meld_code & 0x8:
            consumed_tile_ids = [
                tile_136
                for index, tile_136 in enumerate(triplet_tiles_136)
                if index != called_tile_index
            ]
            return _build_meld(
                who=seat,
                meld_type="pon",
                from_code=from_who,
                tiles_136=triplet_tiles_136,
                consumed_tile_ids=consumed_tile_ids,
                raw_m=meld_code,
                called_tile_id=triplet_tiles_136[called_tile_index],
                called_index=called_tile_index,
                rotate_index=called_tile_index,
                is_open=True,
            )

        added_tile_136 = 4 * tile_kind_34 + unused_copy_index
        return _build_meld(
            who=seat,
            meld_type="kakan",
            from_code=from_who,
            tiles_136=triplet_tiles_136 + [added_tile_136],
            consumed_tile_ids=[added_tile_136],
            raw_m=meld_code,
            called_tile_id=triplet_tiles_136[called_tile_index],
            called_index=called_tile_index,
            rotate_index=called_tile_index,
            is_open=True,
        )

    if meld_code & 0x20:
        # Kita / nuki is not part of the current feature set.
        raise ValueError(f"Unsupported kita meld code: {meld_code}")

    # Remaining shape is kan. from_who == 0 means ankan, otherwise daiminkan.
    base_and_called = meld_code >> 8
    called_tile_index = base_and_called % 4
    tile_kind_34 = base_and_called // 4
    if not 0 <= tile_kind_34 <= 33:
        raise ValueError(f"Invalid kan tile kind: {tile_kind_34}")

    tiles_136 = _all_tiles_136(tile_kind_34)

    if from_who == 0:
        return _build_meld(
            who=seat,
            meld_type="ankan",
            from_code=from_who,
            tiles_136=tiles_136,
            consumed_tile_ids=tiles_136,
            raw_m=meld_code,
            called_tile_id=None,
            called_index=None,
            rotate_index=None,
            is_open=False,
        )

    consumed_tile_ids = [
        tile_136
        for index, tile_136 in enumerate(tiles_136)
        if index != called_tile_index
    ]
    return _build_meld(
        who=seat,
        meld_type="daiminkan",
        from_code=from_who,
        tiles_136=tiles_136,
        consumed_tile_ids=consumed_tile_ids,
        raw_m=meld_code,
        called_tile_id=tiles_136[called_tile_index],
        called_index=called_tile_index,
        rotate_index=called_tile_index,
        is_open=True,
    )
