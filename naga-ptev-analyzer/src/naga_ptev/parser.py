from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import warnings

from naga_ptev.models import AnalyzerResponse, KyokuState, PointConfig, RankProb, SeatPrediction


class ResponseStructureError(ValueError):
    """Raised when the observed NAGA response shape does not match expectations."""


def _ensure_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResponseStructureError(f"{path}: expected mapping, got {type(value).__name__}: {value!r}")
    return value


def _ensure_sequence(value: Any, path: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ResponseStructureError(f"{path}: expected sequence, got {type(value).__name__}: {value!r}")
    return list(value)


def _coerce_probability_vector(raw_values: Sequence[Any], path: str) -> RankProb:
    if len(raw_values) < 4:
        raise ResponseStructureError(f"{path}: expected at least 4 probability values, got {len(raw_values)}")
    try:
        values = [float(raw_values[index]) for index in range(4)]
    except (TypeError, ValueError) as exc:
        raise ResponseStructureError(f"{path}: could not convert probability values: {raw_values!r}") from exc

    total = sum(values)
    if 0.99 <= total <= 1.01:
        normalized = values
    elif 99.0 <= total <= 101.0:
        normalized = [value / 100.0 for value in values]
    else:
        warnings.warn(
            f"{path}: unexpected probability sum {total:.4f}; keeping original values",
            stacklevel=2,
        )
        normalized = values

    return RankProb(
        p1=float(normalized[0]),
        p2=float(normalized[1]),
        p3=float(normalized[2]),
        p4=float(normalized[3]),
    )


def _coerce_flag(raw_value: Any) -> bool:
    try:
        return int(raw_value) == 1
    except (TypeError, ValueError):
        return bool(raw_value)


def _compute_ptev(rank_prob: RankProb, point_config: PointConfig) -> float:
    return sum(prob * point for prob, point in zip(rank_prob.as_list(), point_config.rank_points, strict=True))


def _parse_seat_prediction(
    raw_seat: Any,
    *,
    seat: int,
    path: str,
    point_config: PointConfig,
) -> SeatPrediction:
    values = _ensure_sequence(raw_seat, path)
    rank_prob = _coerce_probability_vector(values, path)
    score_mv = float(values[4]) if len(values) >= 5 and values[4] is not None else None
    is_actor = _coerce_flag(values[5]) if len(values) >= 6 else False
    is_target = _coerce_flag(values[6]) if len(values) >= 7 else False
    return SeatPrediction(
        seat=seat,
        rank_prob=rank_prob,
        score_mv=score_mv,
        is_actor=is_actor,
        is_target=is_target,
        ptev=_compute_ptev(rank_prob, point_config),
    )


def _parse_seat_block(
    raw_block: Any,
    *,
    path: str,
    point_config: PointConfig,
) -> list[SeatPrediction]:
    seat_rows = _ensure_sequence(raw_block, path)
    if len(seat_rows) != 4:
        raise ResponseStructureError(f"{path}: expected 4 seats, got {len(seat_rows)}")
    return [
        _parse_seat_prediction(
            seat_rows[seat_index],
            seat=seat_index,
            path=f"{path}[{seat_index}]",
            point_config=point_config,
        )
        for seat_index in range(4)
    ]


def _parse_branch_group(
    raw_group: Any,
    *,
    path: str,
    point_config: PointConfig,
) -> list[list[SeatPrediction]]:
    branches = _ensure_sequence(raw_group, path)
    return [
        _parse_seat_block(branch, path=f"{path}[{branch_index}]", point_config=point_config)
        for branch_index, branch in enumerate(branches)
    ]


def parse_analyzer_response(
    raw_response: Mapping[str, Any],
    state: KyokuState,
    point_config: PointConfig | None = None,
) -> AnalyzerResponse:
    normalized_point_config = point_config or PointConfig()
    payload = dict(_ensure_mapping(raw_response, "raw_response"))
    result = _ensure_sequence(payload.get("result"), "raw_response.result")
    if len(result) < 4:
        raise ResponseStructureError(
            f"raw_response.result: expected at least 4 top-level entries, got {len(result)}"
        )

    base = _parse_seat_block(result[0], path="raw_response.result[0]", point_config=normalized_point_config)
    ron_branches = _parse_branch_group(result[1], path="raw_response.result[1]", point_config=normalized_point_config)
    tsumo_branches = _parse_branch_group(result[2], path="raw_response.result[2]", point_config=normalized_point_config)
    ryukyoku_branches = _parse_branch_group(
        result[3],
        path="raw_response.result[3]",
        point_config=normalized_point_config,
    )
    return AnalyzerResponse(
        state=state,
        base=base,
        ron_branches=ron_branches,
        tsumo_branches=tsumo_branches,
        ryukyoku_branches=ryukyoku_branches,
        raw=payload,
    )

