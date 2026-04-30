from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from naga_ptev.models import KyokuState


CollectorStatus = Literal["pending", "success", "failed", "skipped"]


@dataclass(frozen=True)
class SampleSet:
    method: str
    states: tuple[KyokuState, ...]


class CollectorStateRow(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    state_hash: str
    kyoku: int
    honba: int
    kyotaku: int
    score0: int
    score1: int
    score2: int
    score3: int
    status: CollectorStatus = "pending"
    raw_path: str = ""
    error_message: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def state(self) -> KyokuState:
        return KyokuState(
            kyoku=int(self.kyoku),
            honba=int(self.honba),
            kyotaku=int(self.kyotaku),
            scores=[int(self.score0), int(self.score1), int(self.score2), int(self.score3)],
        )

    @field_validator("state_hash")
    @classmethod
    def _validate_state_hash(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if len(normalized) != 64:
            raise ValueError("state_hash must be a sha256 hex digest")
        return normalized


class DatasetBuildResult(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    base_csv: Path
    branch_csv: Path
    base_rows: int
    branch_rows: int


class TrainResult(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    model_path: Path
    feature_columns_path: Path
    model_name: str
    feature_count: int

