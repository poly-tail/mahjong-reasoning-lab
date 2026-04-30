from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_length(name: str, values: list[Any], expected_length: int) -> list[Any]:
    if len(values) != expected_length:
        raise ValueError(f"{name} must have exactly {expected_length} items, got {len(values)}")
    return values


class KyokuState(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    kyoku: int
    honba: int
    kyotaku: int
    scores: list[int]

    @field_validator("scores")
    @classmethod
    def _validate_scores(cls, value: list[int]) -> list[int]:
        return [int(item) for item in _validate_length("scores", value, 4)]


class PointConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    rank_points: list[float] = Field(default_factory=lambda: [75.0, 30.0, 0.0, -105.0])

    @field_validator("rank_points")
    @classmethod
    def _validate_rank_points(cls, value: list[float]) -> list[float]:
        return [float(item) for item in _validate_length("rank_points", value, 4)]


class RankProb(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    p1: float
    p2: float
    p3: float
    p4: float

    def as_list(self) -> list[float]:
        return [self.p1, self.p2, self.p3, self.p4]


class SeatPrediction(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    seat: int
    rank_prob: RankProb
    score_mv: float | None = None
    is_actor: bool = False
    is_target: bool = False
    ptev: float


class AnalyzerResponse(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    state: KyokuState
    base: list[SeatPrediction]
    ron_branches: list[list[SeatPrediction]]
    tsumo_branches: list[list[SeatPrediction]]
    ryukyoku_branches: list[list[SeatPrediction]]
    raw: dict[str, Any]

    @field_validator("base")
    @classmethod
    def _validate_base(cls, value: list[SeatPrediction]) -> list[SeatPrediction]:
        return _validate_length("base", value, 4)


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    category: str
    scenario_name: str
    actor: int | None = None
    target: int | None = None
    score_mv_actor: float | None = None
    ptev_by_seat: list[float]
    delta_ptev_by_seat: list[float]
    rank_prob_by_seat: list[RankProb]

    @field_validator("ptev_by_seat")
    @classmethod
    def _validate_ptev_by_seat(cls, value: list[float]) -> list[float]:
        return [float(item) for item in _validate_length("ptev_by_seat", value, 4)]

    @field_validator("delta_ptev_by_seat")
    @classmethod
    def _validate_delta_ptev_by_seat(cls, value: list[float]) -> list[float]:
        return [float(item) for item in _validate_length("delta_ptev_by_seat", value, 4)]

    @field_validator("rank_prob_by_seat")
    @classmethod
    def _validate_rank_prob_by_seat(cls, value: list[RankProb]) -> list[RankProb]:
        return _validate_length("rank_prob_by_seat", value, 4)

