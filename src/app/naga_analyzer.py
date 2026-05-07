from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Callable, Sequence

from runtime_paths import WORKSPACE_ROOT

SEAT_LABELS = ("自家", "下家", "対面", "上家")
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
        wind_labels = ("東", "南", "西", "北")
        wind_index = max(0, int(self.kyoku)) // 4
        hand_index = int(self.kyoku) % 4 + 1
        wind_label = wind_labels[wind_index] if 0 <= wind_index < len(wind_labels) else "局"
        return f"{wind_label}{hand_index}局 {int(self.honba)}本場 供託{int(self.kyotaku)}本"

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


def _format_probability_delta(probability_delta: float) -> str:
    return f"{float(probability_delta) * 100.0:+.1f}pt"


def _format_score_mv_as_points(score_mv: float | None) -> str:
    if score_mv is None:
        return "不明"
    return f"{float(score_mv) * 100.0:+.0f}点相当"


def _format_rank_probability_with_delta(
    probability: float,
    base_probability: float | None,
) -> str:
    text = _format_probability(probability)
    if base_probability is None:
        return text
    return f"{text}({_format_probability_delta(float(probability) - float(base_probability))})"


def _format_self_baseline_line(seat_prediction: Any) -> str:
    rank_prob = getattr(seat_prediction, "rank_prob")
    p1 = float(getattr(rank_prob, "p1", 0.0))
    p2 = float(getattr(rank_prob, "p2", 0.0))
    p4 = float(getattr(rank_prob, "p4", 0.0))
    return (
        f"現在: 自家ptEV {float(getattr(seat_prediction, 'ptev', 0.0)):+.1f} / "
        f"1着率 {_format_probability(p1)} / "
        f"連対率 {_format_probability(p1 + p2)} / "
        f"4着率 {_format_probability(p4)}"
    )


def _seat_line(seat_prediction: Any) -> str:
    seat_label = SEAT_LABELS[int(getattr(seat_prediction, "seat", 0))]
    rank_prob = getattr(seat_prediction, "rank_prob")
    return (
        f"{seat_label}: "
        f"段位ptEV {float(getattr(seat_prediction, 'ptev', 0.0)):+.1f} / "
        f"1着率 {_format_probability(rank_prob.p1)} / "
        f"2着率 {_format_probability(rank_prob.p2)} / "
        f"3着率 {_format_probability(rank_prob.p3)} / "
        f"4着率 {_format_probability(rank_prob.p4)}"
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
        return "全員ノーテン"
    labels = "・".join(SEAT_LABELS[seat] for seat in seats)
    return f"聴牌: {labels}"


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
    p4: float,
    base_p1: float | None = None,
    base_p2: float | None = None,
    base_p4: float | None = None,
) -> str:
    rentai = float(p1) + float(p2)
    base_rentai = (
        float(base_p1) + float(base_p2)
        if base_p1 is not None and base_p2 is not None
        else None
    )
    return (
        f"{label}: "
        f"和了素点 {_format_score_mv_as_points(score_mv)} / "
        f"自家ptEV {delta_ptev:+.1f} / "
        f"1着率 {_format_rank_probability_with_delta(p1, base_p1)} / "
        f"連対率 {_format_rank_probability_with_delta(rentai, base_rentai)} / "
        f"4着率 {_format_rank_probability_with_delta(p4, base_p4)}"
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
) -> tuple[float | None, float, float, float, float] | None:
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
        fmean(_branch_probability(branch, 0, "p4") for branch in branches),
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
    base_p1 = _branch_probability(parsed_response.base, 0, "p1")
    base_p2 = _branch_probability(parsed_response.base, 0, "p2")
    base_p4 = _branch_probability(parsed_response.base, 0, "p4")
    ron_3900_lines.append(
        f"【3900直撃平均】想定和了素点 {_format_score_mv_as_points(expected_3900)}"
    )
    if ron_by_target:
        average_metrics = _self_average_metrics(
            parsed_response.base,
            [branch for _branch_index, branch in ron_by_target.values()],
        )
        if average_metrics is not None:
            average_score_mv, average_delta, average_p1, average_p2, average_p4 = average_metrics
            average_line = _format_self_metric_line(
                f"直撃候補平均({len(ron_by_target)}人)",
                score_mv=average_score_mv,
                delta_ptev=average_delta,
                p1=average_p1,
                p2=average_p2,
                p4=average_p4,
                base_p1=base_p1,
                base_p2=base_p2,
                base_p4=base_p4,
            )
            summary_lines.append(average_line.replace("直撃候補平均", "3900直撃平均", 1))
            ron_3900_lines.append(average_line)
        for target in (1, 2, 3):
            representative = ron_by_target.get(target)
            if representative is None:
                ron_3900_lines.append(f"{SEAT_LABELS[target]}からロン: 近い分岐なし")
                continue
            branch_index, branch = representative
            ron_3900_lines.append(
                _format_self_metric_line(
                    f"{SEAT_LABELS[target]}からロン R{branch_index:02d}",
                    score_mv=_branch_score_mv(branch, 0),
                    delta_ptev=_branch_delta_self(parsed_response.base, branch),
                    p1=_branch_probability(branch, 0, "p1"),
                    p2=_branch_probability(branch, 0, "p2"),
                    p4=_branch_probability(branch, 0, "p4"),
                    base_p1=base_p1,
                    base_p2=base_p2,
                    base_p4=base_p4,
                )
            )
    else:
        summary_lines.append(
            f"3900直撃平均: 近い分岐なし(想定和了素点 {_format_score_mv_as_points(expected_3900)})"
        )
        ron_3900_lines.append("近いロン分岐が見つかりませんでした。")

    expected_mangan = _expected_mangan_tsumo_score_mvs(state)
    expected_mangan_text = " / ".join(_format_score_mv_as_points(value) for value in expected_mangan)
    mangan_tsumo_lines.append(f"【満貫ツモ候補】想定和了素点 {expected_mangan_text}")
    tsumo_candidates = _closest_self_tsumo_candidates(
        parsed_response,
        expected_mangan,
    )
    if tsumo_candidates:
        first_branch_index, first_branch, first_gap = tsumo_candidates[0]
        summary_lines.append(
            _format_self_metric_line(
                f"満貫ツモ候補 ツモ{first_branch_index:02d}",
                score_mv=_branch_score_mv(first_branch, 0),
                delta_ptev=_branch_delta_self(parsed_response.base, first_branch),
                p1=_branch_probability(first_branch, 0, "p1"),
                p2=_branch_probability(first_branch, 0, "p2"),
                p4=_branch_probability(first_branch, 0, "p4"),
                base_p1=base_p1,
                base_p2=base_p2,
                base_p4=base_p4,
            )
        )
        for branch_index, branch, gap in tsumo_candidates:
            mangan_tsumo_lines.append(
                _format_self_metric_line(
                    f"ツモ候補 {branch_index:02d}(想定差 {gap * 100.0:.0f}点)",
                    score_mv=_branch_score_mv(branch, 0),
                    delta_ptev=_branch_delta_self(parsed_response.base, branch),
                    p1=_branch_probability(branch, 0, "p1"),
                    p2=_branch_probability(branch, 0, "p2"),
                    p4=_branch_probability(branch, 0, "p4"),
                    base_p1=base_p1,
                    base_p2=base_p2,
                    base_p4=base_p4,
                )
            )
    else:
        summary_lines.append(f"満貫ツモ候補: 近い分岐なし(想定和了素点 {expected_mangan_text})")
        mangan_tsumo_lines.append("近いツモ分岐が見つかりませんでした。")

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
    base_summary = base_branch[self_seat]
    self_rank_prob = getattr(self_summary, "rank_prob")
    base_rank_prob = getattr(base_summary, "rank_prob")
    delta_self = _branch_delta_self(base_branch, branch, self_seat=self_seat)
    actor = _branch_actor(branch)
    target = _branch_target(branch)
    score_mv = _branch_score_mv(branch, actor)
    actor_text = SEAT_LABELS[actor] if actor is not None and 0 <= actor < 4 else "-"
    target_text = SEAT_LABELS[target] if target is not None and 0 <= target < 4 else "-"
    if prefix == "RON":
        branch_label = "ロン"
        if actor == self_seat and target is not None:
            context = f"{target_text}からロン"
        elif target == self_seat and actor is not None:
            context = f"{actor_text}へ放銃"
        else:
            context = f"{actor_text}が{target_text}からロン"
    elif prefix == "TSM":
        branch_label = "ツモ"
        context = f"{actor_text}ツモ"
    else:
        branch_label = "流局"
        context = label
    p1 = float(getattr(self_rank_prob, "p1", 0.0))
    p2 = float(getattr(self_rank_prob, "p2", 0.0))
    p4 = float(getattr(self_rank_prob, "p4", 0.0))
    base_p1 = float(getattr(base_rank_prob, "p1", 0.0))
    base_p2 = float(getattr(base_rank_prob, "p2", 0.0))
    base_p4 = float(getattr(base_rank_prob, "p4", 0.0))
    parts = [f"{branch_label}{branch_index:02d} {context}"]
    if score_mv is not None:
        parts.append(f"和了素点 {_format_score_mv_as_points(score_mv)}")
    parts.extend(
        [
            f"自家ptEV {delta_self:+.1f}",
            f"1着率 {_format_rank_probability_with_delta(p1, base_p1)}",
            f"連対率 {_format_rank_probability_with_delta(p1 + p2, base_p1 + base_p2)}",
            f"4着率 {_format_rank_probability_with_delta(p4, base_p4)}",
        ]
    )
    return " / ".join(parts)


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
            label="現状",
            branch=base_branch,
            base_branch=base_branch,
            self_seat=self_seat,
        )
    ]

    groups: tuple[tuple[str, Sequence[Sequence[Any]], bool, Callable[[int], str]], ...] = (
        ("RON+", parsed_response.ron_branches, True, lambda index: f"ロン{index:02d}"),
        ("TSM+", parsed_response.tsumo_branches, True, lambda index: f"ツモ{index:02d}"),
        ("RON-", parsed_response.ron_branches, False, lambda index: f"放銃{index:02d}"),
        ("RYK", parsed_response.ryukyoku_branches, True, lambda index: f"流局{index:02d}"),
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
    lines.append("【現在の全員評価】")
    lines.extend(_seat_line(seat) for seat in parsed_response.base)
    lines.append("")
    lines.append("【自家ロン和了で良い動き】")
    self_ron_lines = _top_branch_lines(
        branches=parsed_response.ron_branches,
        base_branch=parsed_response.base,
        prefix="RON",
        sort_desc=True,
        label_builder=lambda _branch_index: "",
        predicate=lambda branch: _branch_actor(branch) == 0,
    )
    lines.extend(self_ron_lines or ["該当分岐なし"])
    lines.append("")
    lines.append("【自家ツモ和了で良い動き】")
    self_tsumo_lines = _top_branch_lines(
        branches=parsed_response.tsumo_branches,
        base_branch=parsed_response.base,
        prefix="TSM",
        sort_desc=True,
        label_builder=lambda _branch_index: "",
        predicate=lambda branch: _branch_actor(branch) == 0,
    )
    lines.extend(self_tsumo_lines or ["該当分岐なし"])
    lines.append("")
    lines.append("【自家放銃で悪い動き】")
    houjuu_lines = _top_branch_lines(
        branches=parsed_response.ron_branches,
        base_branch=parsed_response.base,
        prefix="RON",
        sort_desc=False,
        label_builder=lambda _branch_index: "",
        predicate=lambda branch: _branch_target(branch) == 0 and _branch_actor(branch) not in {None, 0},
    )
    lines.extend(houjuu_lines or ["該当分岐なし"])
    lines.append("")
    lines.append("【流局で良い動き】")
    ryukyoku_best_lines = _top_branch_lines(
        branches=parsed_response.ryukyoku_branches,
        base_branch=parsed_response.base,
        prefix="RYK",
        sort_desc=True,
        label_builder=_ryukyoku_label,
    )
    lines.extend(ryukyoku_best_lines or ["該当分岐なし"])
    lines.append("")
    lines.append("【流局で悪い動き】")
    ryukyoku_worst_lines = _top_branch_lines(
        branches=parsed_response.ryukyoku_branches,
        base_branch=parsed_response.base,
        prefix="RYK",
        sort_desc=False,
        label_builder=_ryukyoku_label,
    )
    lines.extend(ryukyoku_worst_lines or ["該当分岐なし"])
    lines.append("")
    lines.append("【NAGA照会状態(JSON)】")
    lines.append(parsed_response.state.model_dump_json(indent=2))
    lines.append("")
    lines.append("【取得情報】")
    lines.append(f"ページURL: {probe_result.get('page_url') or '-'}")
    lines.append(f"取得fetch数: {len(probe_result.get('captured_calls') or ())}")
    if raw_artifact_path is not None:
        lines.append(f"生レスポンス: {raw_artifact_path}")
    return "\n".join(lines)


def _build_summary_lines(
    parsed_response: Any,
    fixed_sections: NagaFixedFormatSections,
) -> tuple[str, ...]:
    base = parsed_response.base
    self_base = base[0]
    summary_lines = [
        _format_self_baseline_line(self_base),
        "主な変化（自家目線）:",
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
        summary_lines.append(f"最大ロン和了: {ron_lines[0]}")
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
        summary_lines.append(f"最大放銃悪化: {houjuu_lines[0]}")
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
        summary_lines.append(f"最大ツモ和了: {tsumo_lines[0]}")
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
