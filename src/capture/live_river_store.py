from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence


SEAT_COUNT = 4


class RiverResetAuthority(str, Enum):
    INIT_NEW_ROUND = "init_new_round"
    REINIT_DIFFERENT_ROUND_CONFIRMED = "reinit_different_round_confirmed"
    MANUAL_USER_RESET = "manual_user_reset"


class RiverProjectionSource(str, Enum):
    REINIT_SAME_OR_UNKNOWN = "reinit_same_or_unknown"
    WGC = "wgc"
    INITBYLOG = "initbylog"
    BROWSER_BRIDGE = "browser_bridge"


class RiverMutationError(RuntimeError):
    pass


def _tile136_to_tile34(tile_136: int | None) -> int | None:
    if tile_136 is None:
        return None
    try:
        tile_id = int(tile_136)
    except (TypeError, ValueError):
        return None
    if not 0 <= tile_id <= 135:
        return None
    return tile_id // 4


def _discard_tile34(discard: object) -> int | None:
    tile_34 = getattr(discard, "tile_34", None)
    if tile_34 is not None:
        try:
            return int(tile_34)
        except (TypeError, ValueError):
            return None
    return _tile136_to_tile34(getattr(discard, "tile_136", None))


@dataclass
class LiveRiverStore:
    """Long-lived base river history independent from RoundState lifetime."""

    epoch: int = 0
    round_key: object | None = None
    revision: int = 0
    reset_authority: RiverResetAuthority | None = None
    _discards_by_seat: dict[int, list[object]] = field(
        default_factory=lambda: {seat: [] for seat in range(SEAT_COUNT)}
    )
    _projection_by_source: dict[str, dict[int, tuple[object, ...]]] = field(
        default_factory=dict
    )

    def snapshot_by_seat(self) -> Mapping[int, tuple[object, ...]]:
        return MappingProxyType(
            {
                seat: tuple(self._discards_by_seat.get(seat, ()))
                for seat in range(SEAT_COUNT)
            }
        )

    def projection_snapshot_by_source(self) -> Mapping[str, Mapping[int, tuple[object, ...]]]:
        return MappingProxyType(
            {
                source: MappingProxyType(
                    {
                        seat: tuple(projection.get(seat, ()))
                        for seat in range(SEAT_COUNT)
                    }
                )
                for source, projection in self._projection_by_source.items()
            }
        )

    def mutable_copy_by_seat(self) -> dict[int, list[object]]:
        return {
            seat: list(self._discards_by_seat.get(seat, ()))
            for seat in range(SEAT_COUNT)
        }

    def counts_by_seat(self) -> dict[int, int]:
        return {
            seat: len(self._discards_by_seat.get(seat, ()))
            for seat in range(SEAT_COUNT)
        }

    def has_discards(self) -> bool:
        return any(
            len(self._discards_by_seat.get(seat, ())) > 0
            for seat in range(SEAT_COUNT)
        )

    def copy_for_snapshot(
        self,
        *,
        clone_item: Callable[[object], object] | None = None,
    ) -> "LiveRiverStore":
        copied = LiveRiverStore(
            epoch=self.epoch,
            round_key=self.round_key,
            revision=self.revision,
            reset_authority=self.reset_authority,
        )
        copied._discards_by_seat = {
            seat: [
                clone_item(item) if clone_item is not None else item
                for item in self._discards_by_seat.get(seat, ())
            ]
            for seat in range(SEAT_COUNT)
        }
        copied._projection_by_source = {
            source: {
                seat: tuple(projection.get(seat, ()))
                for seat in range(SEAT_COUNT)
            }
            for source, projection in self._projection_by_source.items()
        }
        return copied

    def reset_for_authoritative_new_round(
        self,
        *,
        authority: RiverResetAuthority,
        round_key: object | None,
        allow_non_empty_clear: bool = False,
        reset_source: str | None = None,
    ) -> None:
        try:
            normalized_authority = (
                authority
                if isinstance(authority, RiverResetAuthority)
                else RiverResetAuthority(authority)
            )
        except ValueError as exc:
            raise RiverMutationError(f"invalid river reset authority: {authority}")

        if self.has_discards() and not bool(allow_non_empty_clear):
            raise RiverMutationError(
                "non-empty base river reset blocked; only the actual INIT parser path or "
                "confirmed different-round REINIT may clear existing discards "
                f"(authority={normalized_authority.value} source={reset_source or 'unknown'})"
            )

        self.epoch += 1
        self.revision += 1
        self.round_key = round_key
        self.reset_authority = normalized_authority
        self._discards_by_seat = {seat: [] for seat in range(SEAT_COUNT)}
        self._projection_by_source.clear()

    def append_discard(self, *, seat: int, discard: object) -> None:
        seat = self._validate_seat(seat)
        self._discards_by_seat.setdefault(seat, []).append(discard)
        self.revision += 1

    def append_many(self, *, seat: int, discards: Sequence[object]) -> None:
        seat = self._validate_seat(seat)
        items = list(discards)
        if not items:
            return
        self._discards_by_seat.setdefault(seat, []).extend(items)
        self.revision += 1

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
            called_tile_34 = _tile136_to_tile34(called_tile_136)

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
                self.revision += 1
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
            self.revision += 1
            return index
        return None

    def store_projection_only(
        self,
        *,
        source: RiverProjectionSource,
        projection_by_seat: Mapping[int, Sequence[object]],
    ) -> None:
        self._projection_by_source[str(source.value)] = {
            seat: tuple(projection_by_seat.get(seat, ()))
            for seat in range(SEAT_COUNT)
        }
        self.revision += 1

    def assert_not_shortened(
        self,
        *,
        before_counts: Mapping[int, int],
        context: str,
    ) -> None:
        after_counts = self.counts_by_seat()
        for seat in range(SEAT_COUNT):
            before = int(before_counts.get(seat, 0) or 0)
            after = int(after_counts.get(seat, 0) or 0)
            if after < before:
                raise RiverMutationError(
                    "base river shortened outside authoritative reset: "
                    f"context={context} seat={seat} before={before} after={after}"
                )

    def _validate_seat(self, seat: int) -> int:
        try:
            normalized = int(seat)
        except (TypeError, ValueError) as exc:
            raise RiverMutationError(f"invalid seat={seat}") from exc
        if not 0 <= normalized < SEAT_COUNT:
            raise RiverMutationError(f"invalid seat={seat}")
        return normalized
