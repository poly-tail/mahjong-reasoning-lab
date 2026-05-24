from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app import main as app_main
from app import naga_analyzer


def _seat(
    seat: int,
    *,
    p1: float = 0.25,
    p2: float = 0.25,
    p3: float = 0.25,
    p4: float = 0.25,
    ptev: float = 0.0,
    score_mv: float | None = None,
    is_actor: bool = False,
    is_target: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        seat=seat,
        rank_prob=SimpleNamespace(p1=p1, p2=p2, p3=p3, p4=p4),
        ptev=ptev,
        score_mv=score_mv,
        is_actor=is_actor,
        is_target=is_target,
    )


def test_normalize_scores_for_naga_from_full_points() -> None:
    assert naga_analyzer.normalize_scores_for_naga([25000, 32100, 18700, 24200]) == (
        250,
        321,
        187,
        242,
    )


def test_normalize_scores_for_naga_preserves_hundreds_scale() -> None:
    assert naga_analyzer.normalize_scores_for_naga([250, 250, 250, 250]) == (
        250,
        250,
        250,
        250,
    )


def test_build_query_state_from_round_state() -> None:
    round_state = SimpleNamespace(
        kyoku_index=2,
        honba=1,
        kyotaku=2,
        oya_rel=0,
        scores=[32100, 28900, 25000, 14000],
    )

    query_state = naga_analyzer.build_query_state_from_round_state(round_state)

    assert query_state is not None
    assert query_state.kyoku == 2
    assert query_state.honba == 1
    assert query_state.kyotaku == 2
    assert query_state.scores == (321, 289, 250, 140)
    assert query_state.oya_seat == 0
    assert query_state.self_is_dealer is True


def test_resolve_storage_state_path_prefers_env(monkeypatch, tmp_path: Path) -> None:
    expected_path = tmp_path / "naga_state.json"
    monkeypatch.setenv(naga_analyzer.DEFAULT_NAGA_STORAGE_ENV, str(expected_path))

    assert naga_analyzer.resolve_storage_state_path() == expected_path


def test_expected_mangan_tsumo_score_mvs_follow_dealer_state() -> None:
    dealer_state = naga_analyzer.NagaQueryState(kyoku=0, honba=1, kyotaku=1, scores=(250, 250, 250, 250), oya_seat=0)
    child_state = naga_analyzer.NagaQueryState(kyoku=0, honba=1, kyotaku=1, scores=(250, 250, 250, 250), oya_seat=1)
    unknown_state = naga_analyzer.NagaQueryState(kyoku=0, honba=1, kyotaku=1, scores=(250, 250, 250, 250))

    assert naga_analyzer._expected_mangan_tsumo_score_mvs(dealer_state) == (133.0,)
    assert naga_analyzer._expected_mangan_tsumo_score_mvs(child_state) == (93.0,)
    assert naga_analyzer._expected_mangan_tsumo_score_mvs(unknown_state) == (93.0, 133.0)


def test_best_self_ron_representatives_by_target_selects_3900_lines() -> None:
    query_state = naga_analyzer.NagaQueryState(
        kyoku=0,
        honba=1,
        kyotaku=0,
        scores=(250, 250, 250, 250),
    )
    base_branch = [
        _seat(0, p1=0.20, p2=0.30, p3=0.30, p4=0.20, ptev=12.0),
        _seat(1, ptev=0.0),
        _seat(2, ptev=0.0),
        _seat(3, ptev=0.0),
    ]
    ron_branches = [
        [_seat(0, p1=0.31, p2=0.29, p3=0.24, p4=0.16, ptev=20.0, score_mv=42.0, is_actor=True), _seat(1, is_target=True), _seat(2), _seat(3)],
        [_seat(0, p1=0.33, p2=0.28, p3=0.23, p4=0.16, ptev=21.0, score_mv=42.0, is_actor=True), _seat(1), _seat(2, is_target=True), _seat(3)],
        [_seat(0, p1=0.35, p2=0.27, p3=0.22, p4=0.16, ptev=22.0, score_mv=42.0, is_actor=True), _seat(1), _seat(2), _seat(3, is_target=True)],
        [_seat(0, p1=0.50, p2=0.20, p3=0.20, p4=0.10, ptev=40.0, score_mv=52.0, is_actor=True), _seat(1, is_target=True), _seat(2), _seat(3)],
    ]
    parsed_response = SimpleNamespace(base=base_branch, ron_branches=ron_branches)

    representatives = naga_analyzer._best_self_ron_representatives_by_target(
        parsed_response,
        query_state,
        expected_score_mv=naga_analyzer._expected_3900_ron_score_mv(query_state),
    )

    assert set(representatives) == {1, 2, 3}
    assert representatives[1][0] == 0
    assert representatives[2][0] == 1
    assert representatives[3][0] == 2


def test_build_fixed_format_sections_splits_3900_and_mangan_text() -> None:
    query_state = naga_analyzer.NagaQueryState(
        kyoku=0,
        honba=1,
        kyotaku=0,
        scores=(250, 250, 250, 250),
        oya_seat=0,
    )
    parsed_response = SimpleNamespace(
        base=[
            _seat(0, p1=0.20, p2=0.30, p3=0.30, p4=0.20, ptev=12.0),
            _seat(1, ptev=0.0),
            _seat(2, ptev=0.0),
            _seat(3, ptev=0.0),
        ],
        ron_branches=[
            [_seat(0, p1=0.31, p2=0.29, p3=0.24, p4=0.16, ptev=20.0, score_mv=42.0, is_actor=True), _seat(1, is_target=True), _seat(2), _seat(3)],
            [_seat(0, p1=0.33, p2=0.28, p3=0.23, p4=0.16, ptev=21.0, score_mv=42.0, is_actor=True), _seat(1), _seat(2, is_target=True), _seat(3)],
            [_seat(0, p1=0.35, p2=0.27, p3=0.22, p4=0.16, ptev=22.0, score_mv=42.0, is_actor=True), _seat(1), _seat(2), _seat(3, is_target=True)],
        ],
        tsumo_branches=[
            [_seat(0, p1=0.42, p2=0.25, p3=0.20, p4=0.13, ptev=28.0, score_mv=123.0, is_actor=True), _seat(1), _seat(2), _seat(3)],
            [_seat(0, p1=0.38, p2=0.27, p3=0.22, p4=0.13, ptev=24.0, score_mv=133.0, is_actor=True), _seat(1), _seat(2), _seat(3)],
        ],
    )

    sections = naga_analyzer._build_fixed_format_sections(parsed_response, query_state)

    assert any("3900直撃平均" in line for line in sections.summary_lines)
    assert any("満貫ツモ候補" in line for line in sections.summary_lines)
    assert any("自家ptEV +9.0" in line for line in sections.summary_lines)
    assert any("1着率 33.0%(+13.0pt)" in line for line in sections.summary_lines)
    assert sections.ron_3900_lines[0].startswith("【3900直撃平均】")
    assert sections.mangan_tsumo_lines[0].startswith("【満貫ツモ候補】")


def test_build_graph_points_includes_baseline_and_transition_groups() -> None:
    base_branch = [
        _seat(0, p1=0.20, p2=0.30, p3=0.30, p4=0.20, ptev=12.0),
        _seat(1, ptev=0.0),
        _seat(2, ptev=0.0),
        _seat(3, ptev=0.0),
    ]
    parsed_response = SimpleNamespace(
        base=base_branch,
        ron_branches=[
            [_seat(0, p1=0.31, p2=0.29, p3=0.24, p4=0.16, ptev=20.0, is_actor=True), _seat(1, is_target=True), _seat(2), _seat(3)],
            [_seat(0, p1=0.12, p2=0.25, p3=0.30, p4=0.33, ptev=-8.0, is_target=True), _seat(1, is_actor=True), _seat(2), _seat(3)],
        ],
        tsumo_branches=[
            [_seat(0, p1=0.42, p2=0.25, p3=0.20, p4=0.13, ptev=28.0, is_actor=True), _seat(1), _seat(2), _seat(3)],
        ],
        ryukyoku_branches=[
            [_seat(0, p1=0.24, p2=0.31, p3=0.27, p4=0.18, ptev=14.0), _seat(1), _seat(2), _seat(3)],
        ],
    )

    points = naga_analyzer._build_graph_points(parsed_response)

    assert points[0].category == "BASE"
    assert points[0].label == "現状"
    assert {point.category for point in points} == {"BASE", "RON+", "TSM+", "RON-", "RYK"}
    assert any(point.delta_ptev == 16.0 for point in points)


def test_build_naga_auto_panel_data_summarizes_major_outcomes(tmp_path) -> None:
    query_state = naga_analyzer.NagaQueryState(
        kyoku=5,
        honba=0,
        kyotaku=0,
        scores=(250, 250, 250, 250),
        oya_seat=0,
    )
    result = naga_analyzer.NagaAnalysisText(
        query_state=query_state,
        summary_lines=(),
        detail_text="",
        graph_points=(
            naga_analyzer.NagaGraphPoint("BASE", "現状", 4.0, 0.25, 0.25, 0.25, 0.25, 0.0),
            naga_analyzer.NagaGraphPoint("RON+", "ロン01", 18.0, 0.35, 0.25, 0.2, 0.2, 14.0),
            naga_analyzer.NagaGraphPoint("TSM+", "ツモ00", 22.0, 0.4, 0.25, 0.2, 0.15, 18.0),
            naga_analyzer.NagaGraphPoint("RON-", "放銃02", -12.0, 0.15, 0.25, 0.25, 0.35, -16.0),
            naga_analyzer.NagaGraphPoint("RYK", "流局00", 7.0, 0.28, 0.27, 0.25, 0.2, 3.0),
            naga_analyzer.NagaGraphPoint("RYK", "流局01", 2.0, 0.23, 0.27, 0.27, 0.23, -2.0),
        ),
    )
    ui_state = app_main.NagaAnalyzerUiState(
        storage_state_path=tmp_path / "naga_state.json",
        raw_output_dir=tmp_path,
        query_state_provider=lambda: query_state,
    )
    ui_state.auto_result = result
    ui_state.auto_last_result_key = app_main._naga_query_key(query_state)

    panel = app_main._build_naga_auto_panel_data(ui_state)

    assert panel.visible is True
    assert panel.status_kind == "ready"
    assert "NAGA pt" in panel.title_text
    assert "和了" in panel.lines[0]
    assert "放銃" in panel.lines[0]
    assert "流局" in panel.lines[0]
    assert "+18.0pt" in panel.lines[0]
    assert "-16.0pt" in panel.lines[0]


def test_build_naga_auto_panel_data_hidden_before_south_2(tmp_path) -> None:
    query_state = naga_analyzer.NagaQueryState(
        kyoku=4,
        honba=0,
        kyotaku=0,
        scores=(250, 250, 250, 250),
    )
    ui_state = app_main.NagaAnalyzerUiState(
        storage_state_path=tmp_path / "naga_state.json",
        raw_output_dir=tmp_path,
        query_state_provider=lambda: query_state,
    )

    assert app_main._build_naga_auto_panel_data(ui_state).visible is False
