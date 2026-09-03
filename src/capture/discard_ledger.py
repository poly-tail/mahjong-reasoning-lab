from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableSequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Sequence


SEAT_COUNT = 4
CALLED_LAG_FLAG = 2


class DiscardResetReason(str, Enum):
    INIT_NEW_ROUND = "init_new_round"
    REINIT_DIFFERENT_ROUND = "reinit_different_round"
    MANUAL_FULL_RESET = "manual_full_reset"


class DiscardMutationError(RuntimeError):
    pass


def _tile136_to_tile34_index(tile_136: int | None) -> int | None:
    if tile_136 is None:
        return None
    try:
        tile_id = int(tile_136)
    except (TypeError, ValueError):
        return None
    if not 0 <= tile_id <= 135:
        return None
    return tile_id // 4


def _discard_tile34(discard: Any) -> int | None:
    tile_34 = getattr(discard, "tile_34", None)
    if tile_34 is not None:
        try:
            return int(tile_34)
        except (TypeError, ValueError):
            return None
    return _tile136_to_tile34_index(getattr(discard, "tile_136", None))


def _copy_discard_runtime_metadata(source: Any, target: Any) -> None:
    for attr in (
        "round_discard_index",
        "tsumogiri",
        "is_tsumogiri_estimated",
        "riichi_marker_before",
        "raw_tag",
        "called",
        "thinking_time_ms",
        "thinking_time_source",
        "thinking_time_before_reach_ms",
        "thinking_time_before_reach_source",
        "lagged",
        "lag_delay_ms",
        "event_index",
    ):
        if hasattr(source, attr):
            setattr(target, attr, getattr(source, attr))
    for attr in (
        "hand_tiles_before_discard_136",
        "self_hand_tiles_before_discard_136",
    ):
        if hasattr(source, attr):
            setattr(target, attr, list(getattr(source, attr, ()) or ()))


def _mark_projection_omitted_discard_as_called(discard: Any) -> Any:
    setattr(discard, "called", True)
    if getattr(discard, "lagged", None) in (None, 0):
        setattr(discard, "lagged", CALLED_LAG_FLAG)
    return discard


def _discard_slot_matches(previous_discard: Any, projection_discard: Any) -> bool:
    previous_tile34 = _discard_tile34(previous_discard)
    projection_tile34 = _discard_tile34(projection_discard)
    return (
        previous_tile34 is not None
        and projection_tile34 is not None
        and previous_tile34 == projection_tile34
    )


def _merge_projection_append_only(
    previous_discards: Sequence[Any],
    projection_discards: Sequence[Any],
    *,
    source: str,
) -> list[Any]:
    """Merge a visible river projection without shortening the full history."""

    previous_list = list(previous_discards)
    projection_list = list(projection_discards)
    if not previous_list:
        return projection_list
    if not projection_list:
        return [
            previous_discard
            if bool(getattr(previous_discard, "called", False))
            else _mark_projection_omitted_discard_as_called(previous_discard)
            for previous_discard in previous_list
        ]

    merged_discards: list[Any] = []
    projection_index = 0
    for previous_discard in previous_list:
        if bool(getattr(previous_discard, "called", False)):
            merged_discards.append(previous_discard)
            if (
                projection_index < len(projection_list)
                and bool(getattr(projection_list[projection_index], "called", False))
                and _discard_slot_matches(previous_discard, projection_list[projection_index])
            ):
                projection_index += 1
            continue

        if projection_index >= len(projection_list):
            merged_discards.append(_mark_projection_omitted_discard_as_called(previous_discard))
            continue

        projection_discard = projection_list[projection_index]
        if _discard_slot_matches(previous_discard, projection_discard):
            _copy_discard_runtime_metadata(previous_discard, projection_discard)
            merged_discards.append(projection_discard)
            projection_index += 1
            continue

        merged_discards.append(_mark_projection_omitted_discard_as_called(previous_discard))

    if projection_index < len(projection_list):
        merged_discards.extend(projection_list[projection_index:])

    if len(merged_discards) < len(previous_list):
        raise DiscardMutationError(
            "discard projection shortened history: "
            f"source={source} before={len(previous_list)} after={len(merged_discards)}"
        )
    return merged_discards


@dataclass
class RoundDiscardLedger:
    _discards_by_seat: dict[int, list[Any]] = field(
        default_factory=lambda: {seat: [] for seat in range(SEAT_COUNT)}
    )
    _revision: int = 0
    _view: "RoundDiscardMapView | None" = field(default=None, init=False, repr=False)

    @property
    def revision(self) -> int:
        return self._revision

    def snapshot_by_seat(self) -> Mapping[int, tuple[Any, ...]]:
        return MappingProxyType(
            {
                seat: tuple(self._discards_by_seat.get(seat, ()))
                for seat in range(SEAT_COUNT)
            }
        )

    def mutable_copy_by_seat(self) -> dict[int, list[Any]]:
        return {
            seat: list(self._discards_by_seat.get(seat, ()))
            for seat in range(SEAT_COUNT)
        }

    def mutable_mapping_view(self) -> "RoundDiscardMapView":
        if self._view is None:
            self._view = RoundDiscardMapView(self)
        return self._view

    def counts_by_seat(self) -> dict[int, int]:
        return {
            seat: len(self._discards_by_seat.get(seat, ()))
            for seat in range(SEAT_COUNT)
        }

    def reset_for_new_round(self, *, reason: DiscardResetReason) -> None:
        self._validate_reset_reason(reason)
        self._discards_by_seat = {seat: [] for seat in range(SEAT_COUNT)}
        self._revision += 1

    def replace_for_reset(
        self,
        *,
        discards_by_seat: Mapping[int, Sequence[Any]] | None,
        reason: DiscardResetReason,
    ) -> None:
        self.reset_for_new_round(reason=reason)
        if not discards_by_seat:
            return
        for seat in range(SEAT_COUNT):
            self._discards_by_seat[seat] = list(discards_by_seat.get(seat, ()))
        self._revision += 1

    def append_discard(self, seat: int, discard: Any) -> None:
        seat = self._validate_seat(seat)
        self._discards_by_seat.setdefault(seat, []).append(discard)
        self._revision += 1

    def append_many(self, seat: int, discards: Sequence[Any]) -> None:
        seat = self._validate_seat(seat)
        items = list(discards)
        if not items:
            return
        self._discards_by_seat.setdefault(seat, []).extend(items)
        self._revision += 1

    def mark_called(
        self,
        *,
        source_seat: int,
        called_tile_136: int | None = None,
        called_tile_34: int | None = None,
        lagged: int | None = None,
    ) -> int | None:
        source_seat = self._validate_seat(source_seat)
        if called_tile_34 is None and called_tile_136 is not None:
            called_tile_34 = _tile136_to_tile34_index(called_tile_136)

        discards = self._discards_by_seat.get(source_seat, [])
        if called_tile_136 is not None:
            for index in range(len(discards) - 1, -1, -1):
                discard = discards[index]
                if bool(getattr(discard, "called", False)):
                    continue
                if getattr(discard, "tile_136", None) != called_tile_136:
                    continue
                setattr(discard, "called", True)
                if lagged is not None:
                    setattr(discard, "lagged", lagged)
                self._revision += 1
                return index

        for index in range(len(discards) - 1, -1, -1):
            discard = discards[index]
            if bool(getattr(discard, "called", False)):
                continue
            if called_tile_34 is None or _discard_tile34(discard) != called_tile_34:
                continue

            setattr(discard, "called", True)
            if lagged is not None:
                setattr(discard, "lagged", lagged)
            self._revision += 1
            return index

        return None

    def apply_projection_non_destructive(
        self,
        *,
        projection_by_seat: Mapping[int, Sequence[Any]],
        source: str,
    ) -> None:
        changed = False
        for seat in range(SEAT_COUNT):
            previous = list(self._discards_by_seat.get(seat, []))
            projection = list(projection_by_seat.get(seat, ()))
            merged = _merge_projection_append_only(previous, projection, source=source)
            if len(merged) < len(previous):
                raise DiscardMutationError(
                    "discard projection shortened history: "
                    f"seat={seat} source={source} before={len(previous)} after={len(merged)}"
                )
            if merged != previous:
                changed = True
            self._discards_by_seat[seat] = merged
        if changed:
            self._revision += 1

    def _items_for_seat(self, seat: int) -> list[Any]:
        seat = self._validate_seat(seat)
        return self._discards_by_seat.setdefault(seat, [])

    def _validate_seat(self, seat: int) -> int:
        try:
            normalized = int(seat)
        except (TypeError, ValueError) as exc:
            raise DiscardMutationError(f"invalid seat: {seat}") from exc
        if not 0 <= normalized < SEAT_COUNT:
            raise DiscardMutationError(f"invalid seat: {seat}")
        return normalized

    def _validate_reset_reason(self, reason: DiscardResetReason) -> None:
        if reason not in {
            DiscardResetReason.INIT_NEW_ROUND,
            DiscardResetReason.REINIT_DIFFERENT_ROUND,
            DiscardResetReason.MANUAL_FULL_RESET,
        }:
            raise DiscardMutationError(f"invalid discard reset reason: {reason}")


class RoundDiscardSeatView(MutableSequence[Any]):
    def __init__(self, ledger: RoundDiscardLedger, seat: int) -> None:
        self._ledger = ledger
        self._seat = seat

    def __len__(self) -> int:
        return len(self._items())

    def __getitem__(self, index: int | slice) -> Any:
        items = self._items()
        if isinstance(index, slice):
            return items[index]
        return items[index]

    def __setitem__(self, index: int | slice, value: Any) -> None:
        raise DiscardMutationError(
            "round_state.discards is append-only; mutate discard metadata or use "
            "RoundDiscardLedger reset/projection methods"
        )

    def __delitem__(self, index: int | slice) -> None:
        raise DiscardMutationError(
            "round_state.discards cannot be shortened outside a new-round reset"
        )

    def insert(self, index: int, value: Any) -> None:
        if index != len(self):
            raise DiscardMutationError("round_state.discards only supports tail append")
        self._ledger.append_discard(self._seat, value)

    def append(self, value: Any) -> None:
        self._ledger.append_discard(self._seat, value)

    def extend(self, values: Sequence[Any]) -> None:
        self._ledger.append_many(self._seat, values)

    def clear(self) -> None:
        raise DiscardMutationError(
            "round_state.discards cannot be cleared outside a new-round reset"
        )

    def copy(self) -> list[Any]:
        return list(self._items())

    def __iter__(self) -> Iterator[Any]:
        return iter(self._items())

    def __reversed__(self) -> Iterator[Any]:
        return reversed(self._items())

    def __eq__(self, other: object) -> bool:
        return list(self._items()) == other

    def __repr__(self) -> str:
        return repr(self._items())

    def _items(self) -> list[Any]:
        return self._ledger._items_for_seat(self._seat)


class RoundDiscardMapView(Mapping[int, RoundDiscardSeatView]):
    def __init__(self, ledger: RoundDiscardLedger) -> None:
        self._ledger = ledger
        self._seat_views: dict[int, RoundDiscardSeatView] = {}

    def __getitem__(self, seat: int) -> RoundDiscardSeatView:
        normalized = self._ledger._validate_seat(seat)
        view = self._seat_views.get(normalized)
        if view is None:
            view = RoundDiscardSeatView(self._ledger, normalized)
            self._seat_views[normalized] = view
        return view

    def __iter__(self) -> Iterator[int]:
        return iter(range(SEAT_COUNT))

    def __len__(self) -> int:
        return SEAT_COUNT

    def __setitem__(self, seat: int, value: Sequence[Any]) -> None:
        raise DiscardMutationError(
            "round_state.discards cannot be replaced; use "
            "apply_discard_projection_non_destructive() or reset_discards_for_new_round()"
        )

    def clear(self) -> None:
        raise DiscardMutationError(
            "round_state.discards cannot be cleared outside a new-round reset"
        )

    def copy(self) -> dict[int, list[Any]]:
        return self._ledger.mutable_copy_by_seat()

    def get(self, seat: int, default: Any = None) -> RoundDiscardSeatView | Any:
        try:
            return self[seat]
        except DiscardMutationError:
            return default

    def __eq__(self, other: object) -> bool:
        return self._ledger.mutable_copy_by_seat() == other

    def __repr__(self) -> str:
        return repr(self._ledger.mutable_copy_by_seat())
