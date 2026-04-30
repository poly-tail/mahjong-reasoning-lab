from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Callable, Sequence

from runtime_paths import WORKSPACE_ROOT

SEAT_LABELS = ("YOU", "SHIMO", "TOIMEN", "KAMI")
DEFAULT_NAGA_STORAGE_ENV = "TENHOU_NAGA_STORAGE_STATE"
DEFAULT_NAGA_RAW_DIR_ENV = "TENHOU_NAGA_RAW_DIR"


@dataclass(frozen=True)
class NagaQueryState:
    kyoku: int
    honba: int
    kyotaku: int
    scores: tuple[int, int, int, int]
    oya_seat: int | None = None

    @property
    def round_text(self) -> str:
        wind_labels = ("East", "South", "West", "North")
        wind_index = max(0, int(self.kyoku)) // 4
        hand_index = int(self.kyoku) % 4 + 1
        wind_label = wind_labels[wind_index] if 0 <= wind_index < len(wind_labels) else "Round"
        return f"{wind_label} {hand_index} / Honba {int(self.honba)} / Kyotaku {int(self.kyotaku)}"

    @property
    def self_is_dealer(self) -> bool | None:
        if self.oya_seat is None:
            return None
        return int(self.oya_seat) == 0


@dataclass(frozen=True)
class NagaAnalysisText:
    query_state: NagaQueryState
    summary_lines: tuple[str, ...]
    detail_text: str
    graph_points: tuple["NagaGraphPoint", ...] = ()
    ron_3900_text: str = ""
    mangan_tsumo_text: str = ""
    raw_artifact_path: Path | None = None
    captured_call_count: int = 0


@dataclass(frozen=True)
class NagaGraphPoint:
    category: str
    label: str
    ptev: float
    p1: float
    p2: float
    p3: float
    p4: float
    delta_ptev: float


@dataclass(frozen=True)
class NagaFixedFormatSections:
    summary_lines: tuple[str, ...]
    ron_3900_lines: tuple[str, ...]
    mangan_tsumo_lines: tuple[str, ...]


def candidate_storage_state_paths() -> tuple[Path, ...]:
    return (
        WORKSPACE_ROOT / "src" / ".secrets" / "naga_state.json",
        WORKSPACE_ROOT / ".secrets" / "naga_state.json",
    )


def resolve_storage_state_path(explicit_path: str | Path | None = None) -> Path:
    if explicit_path is not None:
        return Path(explicit_path)
    explicit_env = str(os.environ.get(DEFAULT_NAGA_STORAGE_ENV, "")).strip()
    if explicit_env:
        return Path(explicit_env)
    for candidate in candidate_storage_state_paths():
        if candidate.exists():
            return candidate
    return candidate_storage_state_paths()[0]


def resolve_raw_output_dir() -> Path:
    explicit_env = str(os.environ.get(DEFAULT_NAGA_RAW_DIR_ENV, "")).strip()
    if explicit_env:
        return Path(explicit_env)
    return WORKSPACE_ROOT / "out" / "raw"


def normalize_scores_for_naga(raw_scores: Sequence[object]) -> tuple[int, int, int, int]:
    if len(raw_scores) != 4:
        raise ValueError(f"Expected 4 scores, got {len(raw_scores)}")
    normalized_scores = [int(value) for value in raw_scores]
    if max(abs(score) for score in normalized_scores) <= 1000:
        return (
            normalized_scores[0],
            normalized_scores[1],
            normalized_scores[2],
            normalized_scores[3],
        )
    return (
        int(round(normalized_scores[0] / 100.0)),
        int(round(normalized_scores[1] / 100.0)),
        int(round(normalized_scores[2] / 100.0)),
        int(round(normalized_scores[3] / 100.0)),
    )


def build_query_state_from_round_state(round_state: object | None) -> NagaQueryState | None:
    if round_state is None:
        return None
    raw_scores = getattr(round_state, "scores", None)
    if not isinstance(raw_scores, (list, tuple)) or len(raw_scores) < 4:
        return None
    try:
        kyoku = int(getattr(round_state, "kyoku_index"))
        honba = int(getattr(round_state, "honba"))
        kyotaku = int(getattr(round_state, "kyotaku"))
        scores = normalize_scores_for_naga(raw_scores[:4])
        oya_seat = getattr(round_state, "oya_rel", None)
        if oya_seat is not None:
            oya_seat = int(oya_seat)
    except (TypeError, ValueError):
        return None
    return NagaQueryState(
        kyoku=kyoku,
        honba=honba,
        kyotaku=kyotaku,
        scores=scores,
        oya_seat=oya_seat,
    )


def _ensure_naga_imports() -> dict[str, Any]:
    try:
        from naga_ptev.client import NagaPtevClient
        from naga_ptev.models import KyokuState
        from naga_ptev.parser import parse_analyzer_response
    except ImportError:
        analyzer_src = WORKSPACE_ROOT / "naga-ptev-analyzer" / "src"
        if not analyzer_src.exists():
            raise
        analyzer_src_text = str(analyzer_src)
        if analyzer_src_text not in sys.path:
            sys.path.insert(0, analyzer_src_text)
        from naga_ptev.client import NagaPtevClient
        from naga_ptev.models import KyokuState
        from naga_ptev.parser import parse_analyzer_response
    return {
        "NagaPtevClient": NagaPtevClient,
        "KyokuState": KyokuState,
        "parse_analyzer_response": parse_analyzer_response,
    }


def _format_probability(probability: float) -> str:
    return f"{float(probability) * 100.0:.1f}%"


def _seat_line(seat_prediction: Any) -> str:
    seat_label = SEAT_LABELS[int(getattr(seat_prediction, "seat", 0))]
    rank_prob = getattr(seat_prediction, "rank_prob")
    return (
        f"{seat_label:<6} "
        f"P1 {_format_probability(rank_prob.p1):>6} "
        f"P2 {_format_probability(rank_prob.p2):>6} "
        f"P3 {_format_probability(rank_prob.p3):>6} "
        f"P4 {_format_probability(rank_prob.p4):>6} "
        f"ptEV {float(getattr(seat_prediction, 'ptev', 0.0)):+6.1f}"
    )


def _branch_actor(branch: Sequence[Any]) -> int | None:
    for seat in branch:
        if bool(getattr(seat, "is_actor", False)):
            return int(getattr(seat, "seat", 0))
    return None


def _branch_target(branch: Sequence[Any]) -> int | None:
    for seat in branch:
        if bool(getattr(seat, "is_target", False)):
            return int(getattr(seat, "seat", 0))
    return None


def _ryukyoku_label(branch_index: int) -> str:
    tenpai_labels = {
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
    seats = tenpai_labels.get(int(branch_index), [])
    if not seats:
        return "tenpai none"
    labels = ",".join(SEAT_LABELS[seat] for seat in seats)
    return f"tenpai {labels}"


def _branch_delta_self(base_branch: Sequence[Any], branch: Sequence[Any], self_seat: int = 0) -> float:
    return float(getattr(branch[self_seat], "ptev", 0.0) - getattr(base_branch[self_seat], "ptev", 0.0))


def _branch_score_mv(branch: Sequence[Any], actor: int | None) -> float | None:
    if actor is None or not (0 <= actor < len(branch)):
        return None
    raw_value = getattr(branch[actor], "score_mv", None)
    if raw_value is None:
        return None
    return float(raw_value)


def _expected_bonus_score_mv(state: NagaQueryState) -> float:
    return float((3 * int(state.honba)) + (10 * int(state.kyotaku)))


def _expected_3900_ron_score_mv(state: NagaQueryState) -> float:
    return 39.0 + _expected_bonus_score_mv(state)


def _expected_mangan_tsumo_score_mvs(state: NagaQueryState) -> tuple[float, ...]:
    bonus_score_mv = _expected_bonus_score_mv(state)
    if state.self_is_dealer is True:
        return (120.0 + bonus_score_mv,)
    if state.self_is_dealer is False:
        return (80.0 + bonus_score_mv,)
    return (80.0 + bonus_score_mv, 120.0 + bonus_score_mv)


def _branch_probability(branch: Sequence[Any], seat: int, field_name: str) -> float:
    return float(getattr(getattr(branch[seat], "rank_prob"), field_name))


def _format_self_metric_line(
    label: str,
    *,
    score_mv: float | None,
    delta_ptev: float,
    p1: float,
    p2: float,
) -> str:
    mv_text = f"{score_mv:.1f}" if score_mv is not None else "na"
    return (
        f"{label:<16} "
        f"mv {mv_text:>5} "
        f"dEV {delta_ptev:+6.1f} "
        f"P1 {_format_probability(p1):>6} "
        f"P2 {_format_probability(p2):>6}"
    )


def _best_self_ron_representatives_by_target(
    parsed_response: Any,
    state: NagaQueryState,
    *,
    expected_score_mv: float,
    tight_tolerance: float = 1.0,
    fallback_tolerance: float = 6.0,
) -> dict[int, tuple[int, Sequence[Any]]]:
    representatives: dict[int, tuple[tuple[float, float, int], int, Sequence[Any]]] = {}
    for branch_index, branch in enumerate(parsed_response.ron_branches):
        actor = _branch_actor(branch)
        target = _branch_target(branch)
        if actor != 0 or target is None or target == 0:
            continue
        score_mv = _branch_score_mv(branch, actor)
        if score_mv is None:
            continue
        gap = abs(float(score_mv) - float(expected_score_mv))
        if gap > fallback_tolerance:
            continue
        priority = 0.0 if gap <= tight_tolerance else 1.0
        sort_key = (
            priority,
            gap,
            -_branch_delta_self(parsed_response.base, branch),
            branch_index,
        )
        current = representatives.get(int(target))
        if current is None or sort_key < current[0]:
            representatives[int(target)] = (sort_key, branch_index, branch)
    return {
        target: (branch_index, branch)
        for target, (_sort_key, branch_index, branch) in representatives.items()
    }


def _self_average_metrics(
    base_branch: Sequence[Any],
    branches: Sequence[Sequence[Any]],
) -> tuple[float | None, float, float, float] | None:
    if not branches:
        return None
    score_values = [
        score_mv
        for score_mv in (_branch_score_mv(branch, 0) for branch in branches)
        if score_mv is not None
    ]
    return (
        fmean(score_values) if score_values else None,
        fmean(_branch_delta_self(base_branch, branch) for branch in branches),
        fmean(_branch_probability(branch, 0, "p1") for branch in branches),
        fmean(_branch_probability(branch, 0, "p2") for branch in branches),
    )


def _closest_self_tsumo_candidates(
    parsed_response: Any,
    expected_score_mvs: Sequence[float],
    *,
    tight_tolerance: float = 1.0,
    fallback_tolerance: float = 18.0,
    limit: int = 3,
) -> list[tuple[int, Sequence[Any], float]]:
    candidates: list[tuple[tuple[float, float, float, int], int, Sequence[Any], float]] = []
    for branch_index, branch in enumerate(parsed_response.tsumo_branches):
        actor = _branch_actor(branch)
        if actor != 0:
            continue
        score_mv = _branch_score_mv(branch, actor)
        if score_mv is None:
            continue
        gap = min(abs(float(score_mv) - float(expected)) for expected in expected_score_mvs)
        if gap > fallback_tolerance:
            continue
        priority = 0.0 if gap <= tight_tolerance else 1.0
        sort_key = (
            priority,
            gap,
            -_branch_delta_self(parsed_response.base, branch),
            branch_index,
        )
        candidates.append((sort_key, branch_index, branch, gap))
    candidates.sort(key=lambda entry: entry[0])
    return [
        (branch_index, branch, gap)
        for _sort_key, branch_index, branch, gap in candidates[: max(0, int(limit))]
    ]


def _build_fixed_format_sections(
    parsed_response: Any,
    state: NagaQueryState,
) -> NagaFixedFormatSections:
    summary_lines: list[str] = []
    ron_3900_lines: list[str] = []
    mangan_tsumo_lines: list[str] = []

    expected_3900 = _expected_3900_ron_score_mv(state)
    ron_by_target = _best_self_ron_representatives_by_target(
        parsed_response,
        state,
        expected_score_mv=expected_3900,
    )
    ron_3900_lines.append(f"[3900 Ron Average] expected actor mv {expected_3900:.1f}")
    if ron_by_target:
        average_metrics = _self_average_metrics(
            parsed_response.base,
            [branch for _branch_index, branch in ron_by_target.values()],
        )
        if average_metrics is not None:
            average_score_mv, average_delta, average_p1, average_p2 = average_metrics
            average_line = _format_self_metric_line(
                "AVG 3 targets",
                score_mv=average_score_mv,
                delta_ptev=average_delta,
                p1=average_p1,
                p2=average_p2,
            )
            summary_lines.append(f"3900 avg : {average_line}")
            ron_3900_lines.append(average_line)
        for target in (1, 2, 3):
            representative = ron_by_target.get(target)
            if representative is None:
                ron_3900_lines.append(f"{SEAT_LABELS[target]:<16} (no close branch)")
                continue
            branch_index, branch = representative
            ron_3900_lines.append(
                _format_self_metric_line(
                    f"{SEAT_LABELS[target]} RON{branch_index:02d}",
                    score_mv=_branch_score_mv(branch, 0),
                    delta_ptev=_branch_delta_self(parsed_response.base, branch),
                    p1=_branch_probability(branch, 0, "p1"),
                    p2=_branch_probability(branch, 0, "p2"),
                )
            )
    else:
        summary_lines.append(f"3900 avg : no close branch (expected mv {expected_3900:.1f})")
        ron_3900_lines.append("(no close ron branch found)")

    expected_mangan = _expected_mangan_tsumo_score_mvs(state)
    expected_mangan_text = ", ".join(f"{value:.1f}" for value in expected_mangan)
    mangan_tsumo_lines.append(f"[Mangan Tsumo Candidates] expected actor mv {expected_mangan_text}")
    tsumo_candidates = _closest_self_tsumo_candidates(
        parsed_response,
        expected_mangan,
    )
    if tsumo_candidates:
        first_branch_index, first_branch, first_gap = tsumo_candidates[0]
        summary_lines.append(
            "Mangan tsumo: "
            + _format_self_metric_line(
                f"TSM{first_branch_index:02d} gap {first_gap:.1f}",
                score_mv=_branch_score_mv(first_branch, 0),
                delta_ptev=_branch_delta_self(parsed_response.base, first_branch),
                p1=_branch_probability(first_branch, 0, "p1"),
                p2=_branch_probability(first_branch, 0, "p2"),
            )
        )
        for branch_index, branch, gap in tsumo_candidates:
            mangan_tsumo_lines.append(
                _format_self_metric_line(
                    f"TSM{branch_index:02d} gap {gap:.1f}",
                    score_mv=_branch_score_mv(branch, 0),
                    delta_ptev=_branch_delta_self(parsed_response.base, branch),
                    p1=_branch_probability(branch, 0, "p1"),
                    p2=_branch_probability(branch, 0, "p2"),
                )
            )
    else:
        summary_lines.append(f"Mangan tsumo: no close branch (expected mv {expected_mangan_text})")
        mangan_tsumo_lines.append("(no close tsumo branch found)")

    return NagaFixedFormatSections(
        summary_lines=tuple(summary_lines),
        ron_3900_lines=tuple(ron_3900_lines),
        mangan_tsumo_lines=tuple(mangan_tsumo_lines),
    )


def _format_branch_line(
    *,
    prefix: str,
    label: str,
    branch_index: int,
    branch: Sequence[Any],
    base_branch: Sequence[Any],
    self_seat: int = 0,
) -> str:
    self_summary = branch[self_seat]
    delta_self = _branch_delta_self(base_branch, branch, self_seat=self_seat)
    actor = _branch_actor(branch)
    target = _branch_target(branch)
    score_mv = _branch_score_mv(branch, actor)
    actor_text = SEAT_LABELS[actor] if actor is not None and 0 <= actor < 4 else "-"
    target_text = SEAT_LABELS[target] if target is not None and 0 <= target < 4 else "-"
    mv_text = f"{score_mv:.1f}" if score_mv is not None else "na"
    if prefix == "RON":
        context = f"{actor_text}->{target_text}"
    elif prefix == "TSM":
        context = actor_text
    else:
        context = label
    return (
        f"{prefix}{branch_index:02d} "
        f"{context:<18} "
        f"mv {mv_text:>5} "
        f"dEV {delta_self:+6.1f} "
        f"P1 {_format_probability(getattr(self_summary.rank_prob, 'p1', 0.0)):>6}"
    )


def _top_branch_lines(
    *,
    branches: Sequence[Sequence[Any]],
    base_branch: Sequence[Any],
    prefix: str,
    sort_desc: bool,
    label_builder: Callable[[int], str],
    predicate: Callable[[Sequence[Any]], bool] | None = None,
    limit: int = 3,
) -> list[str]:
    selected: list[tuple[int, Sequence[Any], float]] = []
    for branch_index, branch in enumerate(branches):
        if predicate is not None and not predicate(branch):
            continue
        selected.append((branch_index, branch, _branch_delta_self(base_branch, branch)))
    selected.sort(key=lambda entry: entry[2], reverse=sort_desc)
    lines: list[str] = []
    for branch_index, branch, _delta in selected[: max(0, int(limit))]:
        lines.append(
            _format_branch_line(
                prefix=prefix,
                label=label_builder(branch_index),
                branch_index=branch_index,
                branch=branch,
                base_branch=base_branch,
            )
        )
    return lines


def _graph_point_from_branch(
    *,
    category: str,
    label: str,
    branch: Sequence[Any],
    base_branch: Sequence[Any],
    self_seat: int = 0,
) -> NagaGraphPoint:
    self_summary = branch[self_seat]
    rank_prob = getattr(self_summary, "rank_prob")
    return NagaGraphPoint(
        category=category,
        label=label,
        ptev=float(getattr(self_summary, "ptev", 0.0)),
        p1=float(getattr(rank_prob, "p1", 0.0)),
        p2=float(getattr(rank_prob, "p2", 0.0)),
        p3=float(getattr(rank_prob, "p3", 0.0)),
        p4=float(getattr(rank_prob, "p4", 0.0)),
        delta_ptev=_branch_delta_self(base_branch, branch, self_seat=self_seat),
    )


def _build_graph_points(parsed_response: Any, *, self_seat: int = 0, per_group_limit: int = 12) -> tuple[NagaGraphPoint, ...]:
    base_branch = parsed_response.base
    points: list[NagaGraphPoint] = [
        _graph_point_from_branch(
            category="BASE",
            label="Now",
            branch=base_branch,
            base_branch=base_branch,
            self_seat=self_seat,
        )
    ]

    groups: tuple[tuple[str, Sequence[Sequence[Any]], bool, Callable[[int], str]], ...] = (
        ("RON+", parsed_response.ron_branches, True, lambda index: f"R{index:02d}"),
        ("TSM+", parsed_response.tsumo_branches, True, lambda index: f"T{index:02d}"),
        ("RON-", parsed_response.ron_branches, False, lambda index: f"H{index:02d}"),
        ("RYK", parsed_response.ryukyoku_branches, True, lambda index: f"Y{index:02d}"),
    )
    for category, branches, sort_desc, label_builder in groups:
        candidates: list[tuple[int, Sequence[Any], float]] = []
        for branch_index, branch in enumerate(branches):
            if category == "RON+" and _branch_actor(branch) != self_seat:
                continue
            if category == "TSM+" and _branch_actor(branch) != self_seat:
                continue
            if category == "RON-" and not (
                _branch_target(branch) == self_seat and _branch_actor(branch) not in {None, self_seat}
            ):
                continue
            candidates.append((branch_index, branch, _branch_delta_self(base_branch, branch, self_seat=self_seat)))
        candidates.sort(key=lambda entry: entry[2], reverse=sort_desc)
        for branch_index, branch, _delta in candidates[: max(0, int(per_group_limit))]:
            points.append(
                _graph_point_from_branch(
                    category=category,
                    label=label_builder(branch_index),
                    branch=branch,
                    base_branch=base_branch,
                    self_seat=self_seat,
                )
            )
    return tuple(points)


def _build_detail_text(
    parsed_response: Any,
    state: NagaQueryState,
    fixed_sections: NagaFixedFormatSections,
    probe_result: dict[str, Any],
    raw_artifact_path: Path | None,
) -> str:
    lines: list[str] = []
    if fixed_sections.ron_3900_lines:
        lines.extend(fixed_sections.ron_3900_lines)
        lines.append("")
    if fixed_sections.mangan_tsumo_lines:
        lines.extend(fixed_sections.mangan_tsumo_lines)
        lines.append("")
    lines.append(parsed_response.state.model_dump_json(indent=2))
    lines.append("")
    lines.append("[Baseline]")
    lines.extend(_seat_line(seat) for seat in parsed_response.base)
    lines.append("")
    lines.append("[Self Ron Best]")
    self_ron_lines = _top_branch_lines(
        branches=parsed_response.ron_branches,
        base_branch=parsed_response.base,
        prefix="RON",
        sort_desc=True,
        label_builder=lambda _branch_index: "",
        predicate=lambda branch: _branch_actor(branch) == 0,
    )
    lines.extend(self_ron_lines or ["(none)"])
    lines.append("")
    lines.append("[Self Tsumo Best]")
    self_tsumo_lines = _top_branch_lines(
        branches=parsed_response.tsumo_branches,
        base_branch=parsed_response.base,
        prefix="TSM",
        sort_desc=True,
        label_builder=lambda _branch_index: "",
        predicate=lambda branch: _branch_actor(branch) == 0,
    )
    lines.extend(self_tsumo_lines or ["(none)"])
    lines.append("")
    lines.append("[Houjuu Worst For YOU]")
    houjuu_lines = _top_branch_lines(
        branches=parsed_response.ron_branches,
        base_branch=parsed_response.base,
        prefix="RON",
        sort_desc=False,
        label_builder=lambda _branch_index: "",
        predicate=lambda branch: _branch_target(branch) == 0 and _branch_actor(branch) not in {None, 0},
    )
    lines.extend(houjuu_lines or ["(none)"])
    lines.append("")
    lines.append("[Ryukyoku Best For YOU]")
    ryukyoku_best_lines = _top_branch_lines(
        branches=parsed_response.ryukyoku_branches,
        base_branch=parsed_response.base,
        prefix="RYK",
        sort_desc=True,
        label_builder=_ryukyoku_label,
    )
    lines.extend(ryukyoku_best_lines or ["(none)"])
    lines.append("")
    lines.append("[Ryukyoku Worst For YOU]")
    ryukyoku_worst_lines = _top_branch_lines(
        branches=parsed_response.ryukyoku_branches,
        base_branch=parsed_response.base,
        prefix="RYK",
        sort_desc=False,
        label_builder=_ryukyoku_label,
    )
    lines.extend(ryukyoku_worst_lines or ["(none)"])
    lines.append("")
    lines.append("[Probe]")
    lines.append(f"Page URL: {probe_result.get('page_url') or '-'}")
    lines.append(f"Captured fetch calls: {len(probe_result.get('captured_calls') or ())}")
    if raw_artifact_path is not None:
        lines.append(f"Raw artifact: {raw_artifact_path}")
    return "\n".join(lines)


def _build_summary_lines(
    parsed_response: Any,
    fixed_sections: NagaFixedFormatSections,
) -> tuple[str, ...]:
    base = parsed_response.base
    self_base = base[0]
    summary_lines = [
        f"YOU  P1 {_format_probability(self_base.rank_prob.p1)}  P2 {_format_probability(self_base.rank_prob.p2)}  ptEV {float(self_base.ptev):+.1f}",
    ]
    summary_lines.extend(fixed_sections.summary_lines)
    ron_lines = _top_branch_lines(
        branches=parsed_response.ron_branches,
        base_branch=base,
        prefix="RON",
        sort_desc=True,
        label_builder=lambda _branch_index: "",
        predicate=lambda branch: _branch_actor(branch) == 0,
        limit=1,
    )
    if ron_lines:
        summary_lines.append(f"Best agari: {ron_lines[0]}")
    houjuu_lines = _top_branch_lines(
        branches=parsed_response.ron_branches,
        base_branch=base,
        prefix="RON",
        sort_desc=False,
        label_builder=lambda _branch_index: "",
        predicate=lambda branch: _branch_target(branch) == 0 and _branch_actor(branch) not in {None, 0},
        limit=1,
    )
    if houjuu_lines:
        summary_lines.append(f"Worst houjuu: {houjuu_lines[0]}")
    tsumo_lines = _top_branch_lines(
        branches=parsed_response.tsumo_branches,
        base_branch=base,
        prefix="TSM",
        sort_desc=True,
        label_builder=lambda _branch_index: "",
        predicate=lambda branch: _branch_actor(branch) == 0,
        limit=1,
    )
    if tsumo_lines:
        summary_lines.append(f"Best tsumo: {tsumo_lines[0]}")
    return tuple(summary_lines)


def analyze_naga_text(
    state: NagaQueryState,
    *,
    storage_state_path: str | Path | None = None,
    raw_output_dir: str | Path | None = None,
) -> NagaAnalysisText:
    imports = _ensure_naga_imports()
    kyoku_state = imports["KyokuState"](
        kyoku=int(state.kyoku),
        honba=int(state.honba),
        kyotaku=int(state.kyotaku),
        scores=list(state.scores),
    )

    async def _run() -> tuple[dict[str, Any], dict[str, Any], Path | None]:
        client = imports["NagaPtevClient"](
            raw_output_dir=(Path(raw_output_dir) if raw_output_dir is not None else resolve_raw_output_dir()),
        )
        try:
            await client.open_with_state(str(resolve_storage_state_path(storage_state_path)))
            probe_result = await client.probe_endpoint(kyoku_state)
            raw_response = await client.query(kyoku_state)
            return raw_response, probe_result, getattr(client, "last_raw_path", None)
        finally:
            await client.close()

    raw_response, probe_result, raw_artifact_path = asyncio.run(_run())
    parsed_response = imports["parse_analyzer_response"](raw_response, kyoku_state)
    fixed_sections = _build_fixed_format_sections(parsed_response, state)
    return NagaAnalysisText(
        query_state=state,
        summary_lines=_build_summary_lines(parsed_response, fixed_sections),
        detail_text=_build_detail_text(parsed_response, state, fixed_sections, probe_result, raw_artifact_path),
        graph_points=_build_graph_points(parsed_response),
        ron_3900_text="\n".join(fixed_sections.ron_3900_lines),
        mangan_tsumo_text="\n".join(fixed_sections.mangan_tsumo_lines),
        raw_artifact_path=raw_artifact_path,
        captured_call_count=len(probe_result.get("captured_calls") or ()),
    )
