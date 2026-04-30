from __future__ import annotations

import json
from pathlib import Path

from naga_ptev.models import KyokuState
from naga_ptev.parser import parse_analyzer_response


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_response_minimal.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_parse_sample_response_minimal() -> None:
    raw = _load_fixture()
    state = KyokuState(kyoku=2, honba=0, kyotaku=0, scores=[250, 250, 250, 250])
    parsed = parse_analyzer_response(raw, state)

    assert len(parsed.base) == 4
    assert len(parsed.ron_branches) == 1
    assert len(parsed.tsumo_branches) == 1
    assert len(parsed.ryukyoku_branches) == 1


def test_parse_normalizes_percent_probability_vectors_into_zero_to_one() -> None:
    raw = _load_fixture()
    state = KyokuState(kyoku=2, honba=0, kyotaku=0, scores=[250, 250, 250, 250])
    parsed = parse_analyzer_response(raw, state)

    assert parsed.base[0].rank_prob.p1 == 0.25
    assert parsed.base[0].rank_prob.p4 == 0.25
    assert parsed.ron_branches[0][0].rank_prob.p1 == 0.60


def test_parse_reads_actor_and_target_flags_from_branch_seat_arrays() -> None:
    raw = _load_fixture()
    state = KyokuState(kyoku=2, honba=0, kyotaku=0, scores=[250, 250, 250, 250])
    parsed = parse_analyzer_response(raw, state)

    ron_branch = parsed.ron_branches[0]
    assert ron_branch[0].is_actor is True
    assert ron_branch[1].is_target is True
    assert ron_branch[2].is_actor is False

