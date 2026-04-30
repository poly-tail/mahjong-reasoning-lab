from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from naga_ptev.evaluation import evaluate_model
from naga_ptev.featurize import build_dataset_from_collector, rows_from_raw_artifact
from naga_ptev.modeling import load_model, train_model
from naga_ptev.models import KyokuState
from naga_ptev.sampler import boundary_sampler, sample_states, read_samples_csv, write_samples_csv
from naga_ptev.state_hash import state_hash


def _raw_artifact(state: KyokuState) -> dict:
    return {
        "state": state.model_dump(),
        "response": {
            "status": 200,
            "result": [
                [
                    [40, 30, 20, 10, 0, 0, 0],
                    [30, 30, 25, 15, 0, 0, 0],
                    [20, 25, 30, 25, 0, 0, 0],
                    [10, 15, 25, 50, 0, 0, 0],
                ],
                [
                    [
                        [50, 25, 15, 10, 39, 1, 0],
                        [25, 35, 25, 15, -39, 0, 1],
                        [15, 25, 35, 25, 0, 0, 0],
                        [10, 15, 25, 50, 0, 0, 0],
                    ]
                ],
                [
                    [
                        [55, 20, 15, 10, 80, 1, 0],
                        [20, 35, 30, 15, -30, 0, 0],
                        [15, 25, 35, 25, -30, 0, 0],
                        [10, 20, 20, 50, -20, 0, 0],
                    ]
                ],
                [
                    [
                        [35, 30, 20, 15, 0, 0, 0],
                        [25, 35, 25, 15, 0, 0, 0],
                        [20, 25, 30, 25, 0, 0, 0],
                        [20, 10, 25, 45, 0, 0, 0],
                    ]
                ],
            ],
        },
    }


def test_state_hash_preserves_score_order() -> None:
    a = KyokuState(kyoku=0, honba=0, kyotaku=0, scores=[300, 250, 250, 200])
    b = KyokuState(kyoku=0, honba=0, kyotaku=0, scores=[250, 300, 250, 200])

    assert state_hash(a) != state_hash(b)
    assert state_hash(a) == state_hash(a.model_dump())


def test_sampler_csv_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "samples.csv"
    states = boundary_sampler(limit=12)

    write_samples_csv(states, path)
    loaded = read_samples_csv(path)

    assert len(loaded) == 12
    assert [state_hash(state) for state in loaded] == [state_hash(state) for state in states]


def test_limited_boundary_samplers_do_not_collapse_to_one_kyoku() -> None:
    grid_kyoku = {state.kyoku for state in sample_states("grid", limit=50)}
    random_kyoku = {state.kyoku for state in sample_states("random", limit=100)}
    boundary_kyoku = {state.kyoku for state in sample_states("boundary", limit=100)}
    south_kyoku = {state.kyoku for state in sample_states("south_round_boundary", limit=100)}
    kyotaku_kyoku = {state.kyoku for state in sample_states("kyotaku_comparison", limit=100)}

    assert grid_kyoku == set(range(7))
    assert 7 not in random_kyoku
    assert boundary_kyoku == set(range(7))
    assert south_kyoku == {4, 5, 6}
    assert len(kyotaku_kyoku) >= 4
    assert 7 not in kyotaku_kyoku


def test_rows_from_raw_artifact_builds_base_and_branch_rows() -> None:
    state = KyokuState(kyoku=7, honba=1, kyotaku=2, scores=[300, 260, 240, 200])

    base_rows, branch_rows = rows_from_raw_artifact(_raw_artifact(state))

    assert len(base_rows) == 4
    assert len(branch_rows) == 12
    assert {"gap_to_1st", "gap_to_4th", "p1", "ptev_default"}.issubset(base_rows[0])
    assert base_rows[0]["is_oorasu"] == 1


def test_build_dataset_train_and_evaluate_minimal_pipeline(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    db_path = tmp_path / "collector.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE states (
            state_hash TEXT PRIMARY KEY,
            kyoku INTEGER,
            honba INTEGER,
            kyotaku INTEGER,
            score0 INTEGER,
            score1 INTEGER,
            score2 INTEGER,
            score3 INTEGER,
            status TEXT,
            raw_path TEXT,
            error_message TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    for index in range(8):
        state = KyokuState(
            kyoku=index % 8,
            honba=index % 2,
            kyotaku=index % 3,
            scores=[300 + index, 260, 240, 200 - index],
        )
        digest = state_hash(state)
        raw_path = raw_dir / f"{digest}.json"
        raw_path.write_text(json.dumps(_raw_artifact(state)), encoding="utf-8")
        conn.execute(
            """
            INSERT INTO states VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'success', ?, '', '', '')
            """,
            (digest, state.kyoku, state.honba, state.kyotaku, *state.scores, str(raw_path)),
        )
    conn.commit()
    conn.close()

    base_csv, branch_csv = build_dataset_from_collector(
        db=db_path,
        out=tmp_path / "dataset" / "base_predictions.csv",
    )
    assert base_csv.exists()
    assert branch_csv.exists()
    assert len(pd.read_csv(base_csv)) == 32

    model = train_model(dataset=base_csv, model_name="ridge", out=tmp_path / "models")
    assert (tmp_path / "models" / "model.pkl").exists()
    assert load_model(tmp_path / "models" / "model.pkl").feature_columns == model.feature_columns

    metrics_path, errors_path = evaluate_model(
        dataset=base_csv,
        model=tmp_path / "models" / "model.pkl",
        out=tmp_path / "eval",
    )
    assert metrics_path.exists()
    assert errors_path.exists()
