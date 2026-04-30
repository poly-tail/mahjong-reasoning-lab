from __future__ import annotations

import csv
import random
from collections.abc import Iterable, Sequence
from pathlib import Path

from naga_ptev.models import KyokuState
from naga_ptev.state_hash import state_hash


DEFAULT_KYOKU_VALUES = tuple(range(7))
DEFAULT_HONBA_VALUES = (0, 1, 2, 3)
DEFAULT_KYOTAKU_VALUES = (0, 1, 2, 3)
BOUNDARY_DIFFS = (-80, -60, -40, -20, -10, 0, 10, 20, 40, 60, 80)
POINT_SWING_DIFFS = (-123, -93, -80, -77, -42, -39, -30, 0, 30, 39, 42, 77, 80, 93, 123)


def normalize_scores_to_1000(scores: Sequence[int]) -> tuple[int, int, int, int]:
    if len(scores) != 4:
        raise ValueError("scores must contain 4 values")
    values = [int(score) for score in scores]
    delta = 1000 - sum(values)
    values[0] += delta
    return tuple(values)  # type: ignore[return-value]


def _state(kyoku: int, honba: int, kyotaku: int, scores: Sequence[int]) -> KyokuState:
    return KyokuState(
        kyoku=int(kyoku),
        honba=int(honba),
        kyotaku=int(kyotaku),
        scores=list(normalize_scores_to_1000(scores)),
    )


def dedupe_states(states: Iterable[KyokuState], *, limit: int | None = None) -> list[KyokuState]:
    deduped: list[KyokuState] = []
    seen: set[str] = set()
    for state in states:
        digest = state_hash(state)
        if digest in seen:
            continue
        seen.add(digest)
        deduped.append(state)
        if limit is not None and len(deduped) >= int(limit):
            break
    return deduped


def _interleave_by_kyoku(states: Iterable[KyokuState], *, limit: int | None = None) -> list[KyokuState]:
    """Deduplicate and round-robin states by kyoku before applying a limit."""

    buckets: dict[int, list[KyokuState]] = {}
    for state in dedupe_states(states):
        buckets.setdefault(int(state.kyoku), []).append(state)
    ordered: list[KyokuState] = []
    kyoku_order = sorted(buckets)
    while kyoku_order:
        next_order: list[int] = []
        for kyoku in kyoku_order:
            bucket = buckets.get(kyoku, [])
            if not bucket:
                continue
            ordered.append(bucket.pop(0))
            if limit is not None and len(ordered) >= int(limit):
                return ordered
            if bucket:
                next_order.append(kyoku)
        kyoku_order = next_order
    return ordered


def grid_sampler(*, limit: int | None = None) -> list[KyokuState]:
    base_patterns = (
        (250, 250, 250, 250),
        (300, 260, 230, 210),
        (340, 280, 210, 170),
        (400, 260, 200, 140),
        (280, 280, 220, 220),
        (330, 250, 250, 170),
    )
    states = (
        _state(kyoku, honba, kyotaku, scores)
        for kyoku in DEFAULT_KYOKU_VALUES
        for honba in DEFAULT_HONBA_VALUES
        for kyotaku in DEFAULT_KYOTAKU_VALUES
        for scores in base_patterns
    )
    return _interleave_by_kyoku(states, limit=limit)


def random_sampler(*, limit: int = 1000, seed: int = 1) -> list[KyokuState]:
    rng = random.Random(seed)
    states: list[KyokuState] = []
    while len(states) < max(1, int(limit)) * 3:
        kyoku = rng.choices(DEFAULT_KYOKU_VALUES, weights=[1, 1, 1, 1, 1, 2, 3], k=1)[0]
        honba = rng.choice(DEFAULT_HONBA_VALUES)
        kyotaku = rng.choice(DEFAULT_KYOTAKU_VALUES)
        cuts = sorted(rng.sample(range(120, 880), 3))
        raw = [cuts[0], cuts[1] - cuts[0], cuts[2] - cuts[1], 1000 - cuts[2]]
        rng.shuffle(raw)
        states.append(_state(kyoku, honba, kyotaku, raw))
    return dedupe_states(states, limit=limit)


def boundary_sampler(*, limit: int | None = None) -> list[KyokuState]:
    states: list[KyokuState] = []
    kyoku_values = (*DEFAULT_KYOKU_VALUES, 5, 6, 6)
    anchors = (250, 280, 300, 320)
    for kyoku in kyoku_values:
        for honba in DEFAULT_HONBA_VALUES:
            for kyotaku in DEFAULT_KYOTAKU_VALUES:
                for anchor in anchors:
                    for diff in (*BOUNDARY_DIFFS, *POINT_SWING_DIFFS):
                        # 1st/2nd boundary: seat0 and seat1 close near the top.
                        s0 = anchor + diff // 2
                        s1 = anchor - diff // 2
                        states.append(_state(kyoku, honba, kyotaku, (s0, s1, 250, 1000 - s0 - s1 - 250)))
                        # 3rd/4th boundary: seat2 and seat3 close near the bottom.
                        s2 = anchor + diff // 2 - 70
                        s3 = anchor - diff // 2 - 70
                        states.append(_state(kyoku, honba, kyotaku, (360, 1000 - 360 - s2 - s3, s2, s3)))
    return _interleave_by_kyoku(states, limit=limit)


def south_round_boundary_sampler(*, limit: int | None = None) -> list[KyokuState]:
    states: list[KyokuState] = []
    for state in boundary_sampler(limit=None):
        if int(state.kyoku) in {4, 5, 6}:
            states.append(state)
    # Extra South 2 / South 3 clusters around small and mangan/ron-relevant gaps.
    for honba in DEFAULT_HONBA_VALUES:
        for kyotaku in DEFAULT_KYOTAKU_VALUES:
            for diff in POINT_SWING_DIFFS:
                states.append(_state(6, honba, kyotaku, (270, 260 + diff, 240, 230 - diff)))
    return _interleave_by_kyoku(states, limit=limit)


def kyotaku_comparison_sampler(*, limit: int | None = None) -> list[KyokuState]:
    states: list[KyokuState] = []
    seeds = boundary_sampler(limit=None)[: max(500, int(limit or 500))]
    for seed in seeds:
        for kyotaku in (0, 1, 2, 3):
            states.append(seed.model_copy(update={"kyotaku": kyotaku}))
    return _interleave_by_kyoku(states, limit=limit)


def sample_states(method: str, *, limit: int | None = None, seed: int = 1) -> list[KyokuState]:
    normalized = str(method or "boundary").strip().lower().replace("-", "_")
    if normalized == "grid":
        return grid_sampler(limit=limit)
    if normalized == "random":
        return random_sampler(limit=limit or 1000, seed=seed)
    if normalized == "boundary":
        return boundary_sampler(limit=limit)
    if normalized in {"south_round_boundary", "south"}:
        return south_round_boundary_sampler(limit=limit)
    if normalized in {"kyotaku_comparison", "kyotaku"}:
        return kyotaku_comparison_sampler(limit=limit)
    raise ValueError(f"Unknown sampler method: {method}")


def write_samples_csv(states: Sequence[KyokuState], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["state_hash", "kyoku", "honba", "kyotaku", "score0", "score1", "score2", "score3"])
        writer.writeheader()
        for state in states:
            writer.writerow(
                {
                    "state_hash": state_hash(state),
                    "kyoku": int(state.kyoku),
                    "honba": int(state.honba),
                    "kyotaku": int(state.kyotaku),
                    "score0": int(state.scores[0]),
                    "score1": int(state.scores[1]),
                    "score2": int(state.scores[2]),
                    "score3": int(state.scores[3]),
                }
            )
    return target


def read_samples_csv(path: str | Path) -> list[KyokuState]:
    states: list[KyokuState] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if "scores" in row and row["scores"]:
                scores = [int(part.strip()) for part in row["scores"].split(",")]
            else:
                scores = [int(row[f"score{index}"]) for index in range(4)]
            states.append(_state(int(row["kyoku"]), int(row["honba"]), int(row["kyotaku"]), scores))
    return dedupe_states(states)
