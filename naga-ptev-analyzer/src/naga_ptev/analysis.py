from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from naga_ptev.models import AnalyzerResponse, KyokuState, PointConfig, RankProb, ScenarioSummary, SeatPrediction

if TYPE_CHECKING:
    import pandas as pd


def compute_ptev(rank_prob: RankProb | Sequence[float], point_config: PointConfig | None = None) -> float:
    config = point_config or PointConfig()
    probabilities = rank_prob.as_list() if isinstance(rank_prob, RankProb) else [float(value) for value in rank_prob]
    if len(probabilities) != 4:
        raise ValueError(f"rank probability vector must have 4 items, got {len(probabilities)}")
    return sum(prob * point for prob, point in zip(probabilities, config.rank_points, strict=True))


def compute_delta(
    base_response: Sequence[SeatPrediction],
    scenario_response: Sequence[SeatPrediction],
) -> list[dict[str, float]]:
    if len(base_response) != 4 or len(scenario_response) != 4:
        raise ValueError("base_response and scenario_response must each contain 4 seats")
    rows: list[dict[str, float]] = []
    for base_seat, scenario_seat in zip(base_response, scenario_response, strict=True):
        rows.append(
            {
                "seat": int(scenario_seat.seat),
                "delta_ptev": float(scenario_seat.ptev - base_seat.ptev),
                "delta_p1": float(scenario_seat.rank_prob.p1 - base_seat.rank_prob.p1),
                "delta_p2": float(scenario_seat.rank_prob.p2 - base_seat.rank_prob.p2),
                "delta_p3": float(scenario_seat.rank_prob.p3 - base_seat.rank_prob.p3),
                "delta_p4": float(scenario_seat.rank_prob.p4 - base_seat.rank_prob.p4),
            }
        )
    return rows


def _flatten_summaries(*summary_groups: Any) -> list[ScenarioSummary]:
    flattened: list[ScenarioSummary] = []
    for group in summary_groups:
        if group is None:
            continue
        if isinstance(group, ScenarioSummary):
            flattened.append(group)
            continue
        if isinstance(group, Iterable) and not isinstance(group, (str, bytes, bytearray)):
            for item in group:
                if isinstance(item, ScenarioSummary):
                    flattened.append(item)
                    continue
                raise TypeError(f"Unsupported summary item: {item!r}")
            continue
        raise TypeError(f"Unsupported summary group: {group!r}")
    return flattened


def branch_summaries_to_dataframe(*summary_groups: Any) -> "pd.DataFrame":
    import pandas as pd

    flattened = _flatten_summaries(*summary_groups)
    baseline_summary = next((summary for summary in flattened if summary.category == "base"), None)
    baseline_rank_probs = baseline_summary.rank_prob_by_seat if baseline_summary is not None else None

    rows: list[dict[str, Any]] = []
    for summary in flattened:
        for seat_index in range(4):
            rank_prob = summary.rank_prob_by_seat[seat_index]
            baseline_rank_prob = baseline_rank_probs[seat_index] if baseline_rank_probs is not None else None
            delta_p1 = rank_prob.p1 - baseline_rank_prob.p1 if baseline_rank_prob is not None else None
            delta_p2 = rank_prob.p2 - baseline_rank_prob.p2 if baseline_rank_prob is not None else None
            delta_p3 = rank_prob.p3 - baseline_rank_prob.p3 if baseline_rank_prob is not None else None
            delta_p4 = rank_prob.p4 - baseline_rank_prob.p4 if baseline_rank_prob is not None else None
            rows.append(
                {
                    "category": summary.category,
                    "scenario_name": summary.scenario_name,
                    "actor": summary.actor,
                    "target": summary.target,
                    "seat": seat_index,
                    "ptev": summary.ptev_by_seat[seat_index],
                    "delta_ptev": summary.delta_ptev_by_seat[seat_index],
                    "p1": rank_prob.p1,
                    "p2": rank_prob.p2,
                    "p3": rank_prob.p3,
                    "p4": rank_prob.p4,
                    "delta_p1": delta_p1,
                    "delta_p2": delta_p2,
                    "delta_p3": delta_p3,
                    "delta_p4": delta_p4,
                    "score_mv": summary.score_mv_actor if summary.actor == seat_index else None,
                    "is_actor": summary.actor == seat_index if summary.actor is not None else False,
                    "is_target": summary.target == seat_index if summary.target is not None else False,
                }
            )
    return pd.DataFrame(rows)


def response_to_dataframe(response: AnalyzerResponse) -> "pd.DataFrame":
    from naga_ptev.scenarios import (
        summarize_baseline,
        summarize_ron_branches,
        summarize_ryukyoku_branches,
        summarize_tsumo_branches,
    )

    return branch_summaries_to_dataframe(
        summarize_baseline(response),
        summarize_ron_branches(response),
        summarize_tsumo_branches(response),
        summarize_ryukyoku_branches(response),
    )


def compare_current_and_kyotaku_plus_one(
    state: KyokuState,
    add: int = 1,
) -> tuple[KyokuState, KyokuState]:
    return state, state.model_copy(update={"kyotaku": int(state.kyotaku) + int(add)})
