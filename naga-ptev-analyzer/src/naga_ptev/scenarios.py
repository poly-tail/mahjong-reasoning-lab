from __future__ import annotations

from collections.abc import Iterable, Sequence
from statistics import fmean

from naga_ptev.analysis import compute_delta
from naga_ptev.models import AnalyzerResponse, RankProb, ScenarioSummary, SeatPrediction

RYUKYOKU_TENPAI_LABELS: dict[int, list[int]] = {
    0: [],
    1: [0, 1, 2, 3],
    2: [0],
    3: [1],
    4: [2],
    5: [3],
    6: [1, 2, 3],
    7: [0, 2, 3],
    8: [0, 1, 3],
    9: [0, 1, 2],
    10: [0, 1],
    11: [0, 2],
    12: [0, 3],
    13: [1, 2],
    14: [1, 3],
    15: [2, 3],
}


def _seat_index_with_flag(seats: Sequence[SeatPrediction], flag_name: str) -> int | None:
    for seat in seats:
        if getattr(seat, flag_name):
            return int(seat.seat)
    return None


def _rank_probs(seats: Sequence[SeatPrediction]) -> list[RankProb]:
    return [seat.rank_prob for seat in seats]


def _ptev_values(seats: Sequence[SeatPrediction]) -> list[float]:
    return [float(seat.ptev) for seat in seats]


def _delta_values(base: Sequence[SeatPrediction], seats: Sequence[SeatPrediction]) -> list[float]:
    return [float(row["delta_ptev"]) for row in compute_delta(base, seats)]


def _score_mv_for_actor(seats: Sequence[SeatPrediction], actor: int | None) -> float | None:
    if actor is None:
        return None
    return seats[actor].score_mv


def _scenario_summary(
    *,
    category: str,
    scenario_name: str,
    base: Sequence[SeatPrediction],
    seats: Sequence[SeatPrediction],
    actor: int | None = None,
    target: int | None = None,
) -> ScenarioSummary:
    return ScenarioSummary(
        category=category,
        scenario_name=scenario_name,
        actor=actor,
        target=target,
        score_mv_actor=_score_mv_for_actor(seats, actor),
        ptev_by_seat=_ptev_values(seats),
        delta_ptev_by_seat=_delta_values(base, seats),
        rank_prob_by_seat=_rank_probs(seats),
    )


def summarize_baseline(response: AnalyzerResponse) -> list[ScenarioSummary]:
    return [
        ScenarioSummary(
            category="base",
            scenario_name="baseline",
            actor=None,
            target=None,
            score_mv_actor=None,
            ptev_by_seat=_ptev_values(response.base),
            delta_ptev_by_seat=[0.0, 0.0, 0.0, 0.0],
            rank_prob_by_seat=_rank_probs(response.base),
        )
    ]


def summarize_ron_branches(
    response: AnalyzerResponse,
    actor: int | None = None,
    target: int | None = None,
) -> list[ScenarioSummary]:
    summaries: list[ScenarioSummary] = []
    for branch_index, seats in enumerate(response.ron_branches):
        branch_actor = _seat_index_with_flag(seats, "is_actor")
        branch_target = _seat_index_with_flag(seats, "is_target")
        if actor is not None and branch_actor != actor:
            continue
        if target is not None and branch_target != target:
            continue
        score_mv = _score_mv_for_actor(seats, branch_actor)
        score_label = f"{score_mv:.1f}" if score_mv is not None else "na"
        summaries.append(
            _scenario_summary(
                category="ron",
                scenario_name=f"ron_{branch_index:03d}_actor{branch_actor}_target{branch_target}_mv{score_label}",
                base=response.base,
                seats=seats,
                actor=branch_actor,
                target=branch_target,
            )
        )
    return summaries


def summarize_tsumo_branches(
    response: AnalyzerResponse,
    actor: int | None = None,
) -> list[ScenarioSummary]:
    summaries: list[ScenarioSummary] = []
    for branch_index, seats in enumerate(response.tsumo_branches):
        branch_actor = _seat_index_with_flag(seats, "is_actor")
        if actor is not None and branch_actor != actor:
            continue
        score_mv = _score_mv_for_actor(seats, branch_actor)
        score_label = f"{score_mv:.1f}" if score_mv is not None else "na"
        summaries.append(
            _scenario_summary(
                category="tsumo",
                scenario_name=f"tsumo_{branch_index:03d}_actor{branch_actor}_mv{score_label}",
                base=response.base,
                seats=seats,
                actor=branch_actor,
                target=None,
            )
        )
    return summaries


def summarize_ryukyoku_branches(response: AnalyzerResponse) -> list[ScenarioSummary]:
    summaries: list[ScenarioSummary] = []
    for branch_index, seats in enumerate(response.ryukyoku_branches):
        tenpai_seats = RYUKYOKU_TENPAI_LABELS.get(branch_index, [])
        label = ",".join(str(seat) for seat in tenpai_seats) if tenpai_seats else "none"
        summaries.append(
            _scenario_summary(
                category="ryukyoku",
                scenario_name=f"ryukyoku_{branch_index:02d}_tenpai_{label}",
                base=response.base,
                seats=seats,
                actor=None,
                target=None,
            )
        )
    return summaries


def extract_ron_by_score_mv(
    response: AnalyzerResponse,
    actor: int,
    target: int | None,
    score_mv: float,
    tolerance: float = 0.1,
) -> list[ScenarioSummary]:
    matches: list[ScenarioSummary] = []
    for summary in summarize_ron_branches(response, actor=actor, target=target):
        if summary.score_mv_actor is None:
            continue
        if abs(float(summary.score_mv_actor) - float(score_mv)) <= float(tolerance):
            matches.append(summary)
    return matches


def aggregate_three_target_average(branches: Iterable[ScenarioSummary]) -> ScenarioSummary:
    branch_list = list(branches)
    if not branch_list:
        raise ValueError("branches must not be empty")

    base = branch_list[0]
    averaged_rank_probs: list[RankProb] = []
    for seat_index in range(4):
        p1_values = [branch.rank_prob_by_seat[seat_index].p1 for branch in branch_list]
        p2_values = [branch.rank_prob_by_seat[seat_index].p2 for branch in branch_list]
        p3_values = [branch.rank_prob_by_seat[seat_index].p3 for branch in branch_list]
        p4_values = [branch.rank_prob_by_seat[seat_index].p4 for branch in branch_list]
        averaged_rank_probs.append(
            RankProb(
                p1=fmean(p1_values),
                p2=fmean(p2_values),
                p3=fmean(p3_values),
                p4=fmean(p4_values),
            )
        )

    score_values = [branch.score_mv_actor for branch in branch_list if branch.score_mv_actor is not None]
    return ScenarioSummary(
        category=f"{base.category}_avg",
        scenario_name=f"{base.category}_three_target_average",
        actor=base.actor,
        target=None,
        score_mv_actor=fmean(score_values) if score_values else None,
        ptev_by_seat=[fmean(branch.ptev_by_seat[seat] for branch in branch_list) for seat in range(4)],
        delta_ptev_by_seat=[fmean(branch.delta_ptev_by_seat[seat] for branch in branch_list) for seat in range(4)],
        rank_prob_by_seat=averaged_rank_probs,
    )

