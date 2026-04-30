from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

import pandas as pd

from naga_ptev.analysis import compute_ptev
from naga_ptev.models import KyokuState, PointConfig
from naga_ptev.parser import parse_analyzer_response


DEFAULT_RANK_POINTS = [75.0, 30.0, 0.0, -105.0]


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _extract_response(raw_artifact: dict[str, Any]) -> dict[str, Any]:
    response = raw_artifact.get("response")
    if isinstance(response, dict):
        return response
    if "result" in raw_artifact:
        return raw_artifact
    raise ValueError("raw artifact does not contain analyzer response JSON")


def _extract_state(raw_artifact: dict[str, Any], fallback: KyokuState | None = None) -> KyokuState:
    raw_state = raw_artifact.get("state")
    if isinstance(raw_state, dict):
        return KyokuState(**raw_state)
    if fallback is not None:
        return fallback
    raise ValueError("raw artifact does not contain state")


def current_rank(scores: list[int], seat: int) -> int:
    self_score = int(scores[seat])
    higher = sum(1 for score in scores if int(score) > self_score)
    return int(higher + 1)


def _ranked_scores(scores: list[int]) -> list[int]:
    return sorted((int(score) for score in scores), reverse=True)


def _score_features(state: KyokuState, seat: int) -> dict[str, Any]:
    scores = [int(score) for score in state.scores]
    ranked = _ranked_scores(scores)
    rank = current_rank(scores, seat)
    self_score = scores[seat]
    score_mean = sum(scores) / 4.0
    score_std = (sum((score - score_mean) ** 2 for score in scores) / 4.0) ** 0.5
    oya_seat = int(state.kyoku) % 4
    gap_to_rank = {rank_index + 1: self_score - score for rank_index, score in enumerate(ranked)}
    gap_to_next_rank = 0
    if rank < 4:
        gap_to_next_rank = self_score - ranked[rank]
    gap_from_prev_rank = 0
    if rank > 1:
        gap_from_prev_rank = ranked[rank - 2] - self_score
    return {
        "kyoku": int(state.kyoku),
        "honba": int(state.honba),
        "kyotaku": int(state.kyotaku),
        "seat": int(seat),
        "score_self": int(self_score),
        "score_0": scores[0],
        "score_1": scores[1],
        "score_2": scores[2],
        "score_3": scores[3],
        "current_rank": rank,
        "gap_to_1st": gap_to_rank[1],
        "gap_to_2nd": gap_to_rank[2],
        "gap_to_3rd": gap_to_rank[3],
        "gap_to_4th": gap_to_rank[4],
        "gap_to_next_rank": gap_to_next_rank,
        "gap_from_prev_rank": gap_from_prev_rank,
        "score_range": max(scores) - min(scores),
        "score_std": score_std,
        "is_dealer": int(seat == oya_seat),
        "dealer_score": scores[oya_seat],
        "hands_remaining": max(0, 8 - int(state.kyoku)),
        "is_south_round": int(int(state.kyoku) >= 4),
        "is_oorasu": int(int(state.kyoku) == 7),
        "kyotaku_value": int(state.kyotaku) * 10,
    }


def _prediction_targets(seat_prediction: Any, point_config: PointConfig) -> dict[str, Any]:
    rank_prob = seat_prediction.rank_prob
    ptev = compute_ptev(rank_prob, point_config)
    return {
        "p1": float(rank_prob.p1),
        "p2": float(rank_prob.p2),
        "p3": float(rank_prob.p3),
        "p4": float(rank_prob.p4),
        "ptev_default": float(ptev),
    }


def _branch_rows(parsed: Any, state: KyokuState, point_config: PointConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    branch_groups = (
        ("ron", parsed.ron_branches),
        ("tsumo", parsed.tsumo_branches),
        ("ryukyoku", parsed.ryukyoku_branches),
    )
    for category, branches in branch_groups:
        for branch_index, branch in enumerate(branches):
            actor = next((int(seat.seat) for seat in branch if bool(seat.is_actor)), None)
            target = next((int(seat.seat) for seat in branch if bool(seat.is_target)), None)
            for seat_prediction in branch:
                seat = int(seat_prediction.seat)
                row = _score_features(state, seat)
                row.update(_prediction_targets(seat_prediction, point_config))
                row.update(
                    {
                        "category": category,
                        "branch_index": int(branch_index),
                        "actor": actor,
                        "target": target,
                        "score_mv": seat_prediction.score_mv if actor == seat else None,
                    }
                )
                rows.append(row)
    return rows


def rows_from_raw_artifact(raw_artifact: dict[str, Any], fallback_state: KyokuState | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    state = _extract_state(raw_artifact, fallback=fallback_state)
    response = _extract_response(raw_artifact)
    point_config = PointConfig(rank_points=DEFAULT_RANK_POINTS)
    parsed = parse_analyzer_response(response, state, point_config=point_config)
    base_rows: list[dict[str, Any]] = []
    for seat_prediction in parsed.base:
        seat = int(seat_prediction.seat)
        row = _score_features(state, seat)
        row.update(_prediction_targets(seat_prediction, point_config))
        row.update({"category": "base", "branch_index": None, "actor": None, "target": None, "score_mv": None})
        base_rows.append(row)
    return base_rows, _branch_rows(parsed, state, point_config)


def build_dataset_from_collector(
    *,
    db: str | Path,
    out: str | Path = "out/dataset/base_predictions.csv",
    branch_out: str | Path | None = None,
) -> tuple[Path, Path]:
    db_path = Path(db)
    out_path = Path(out)
    branch_path = Path(branch_out) if branch_out is not None else out_path.with_name("branch_predictions.csv")
    base_rows: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT kyoku, honba, kyotaku, score0, score1, score2, score3, raw_path
            FROM states
            WHERE status = 'success' AND raw_path != ''
            ORDER BY updated_at, state_hash
            """
        ).fetchall()
        for row in rows:
            raw_path = Path(str(row["raw_path"]))
            if not raw_path.exists():
                continue
            fallback_state = KyokuState(
                kyoku=int(row["kyoku"]),
                honba=int(row["honba"]),
                kyotaku=int(row["kyotaku"]),
                scores=[int(row[f"score{index}"]) for index in range(4)],
            )
            raw_artifact = _load_json(raw_path)
            current_base_rows, current_branch_rows = rows_from_raw_artifact(raw_artifact, fallback_state)
            base_rows.extend(current_base_rows)
            branch_rows.extend(current_branch_rows)
    finally:
        conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    branch_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(base_rows).to_csv(out_path, index=False)
    pd.DataFrame(branch_rows).to_csv(branch_path, index=False)
    return out_path, branch_path


def feature_columns_from_dataframe(df: pd.DataFrame) -> list[str]:
    excluded = {"p1", "p2", "p3", "p4", "ptev_default", "category", "branch_index", "actor", "target", "score_mv"}
    return [column for column in df.columns if column not in excluded and pd.api.types.is_numeric_dtype(df[column])]

