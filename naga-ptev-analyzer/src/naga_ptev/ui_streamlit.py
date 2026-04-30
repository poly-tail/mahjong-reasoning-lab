from __future__ import annotations

import asyncio
from io import StringIO
from pathlib import Path

from naga_ptev.analysis import branch_summaries_to_dataframe, compare_current_and_kyotaku_plus_one
from naga_ptev.client import NagaPtevClient
from naga_ptev.models import KyokuState, PointConfig
from naga_ptev.parser import parse_analyzer_response
from naga_ptev.scenarios import (
    aggregate_three_target_average,
    extract_ron_by_score_mv,
    summarize_baseline,
    summarize_ron_branches,
    summarize_ryukyoku_branches,
    summarize_tsumo_branches,
)

import pandas as pd
import plotly.express as px
import streamlit as st


async def _fetch_parsed_response(storage_path: str, state: KyokuState, point_config: PointConfig):
    client = NagaPtevClient()
    try:
        await client.open_with_state(storage_path)
        raw = await client.query(state)
        parsed = parse_analyzer_response(raw, state, point_config=point_config)
        return parsed, client.last_raw_path
    finally:
        await client.close()


def _chart_baseline(parsed_response):
    baseline_df = pd.DataFrame(
        [
            {
                "Seat": seat.seat,
                "ptEV": seat.ptev,
            }
            for seat in parsed_response.base
        ]
    )
    return px.bar(baseline_df, x="Seat", y="ptEV", title="Baseline ptEV by Seat")


def _chart_branch_delta(summary_df: pd.DataFrame):
    filtered = summary_df[summary_df["category"] != "base"]
    return px.bar(
        filtered,
        x="scenario_name",
        y="delta_ptev",
        color="seat",
        title="Branch delta ptEV by Scenario",
    )


def _chart_rank_stack(parsed_response):
    baseline_df = pd.DataFrame(
        [
            {"Seat": seat.seat, "Rank": "P1", "Probability": seat.rank_prob.p1}
            for seat in parsed_response.base
        ]
        + [
            {"Seat": seat.seat, "Rank": "P2", "Probability": seat.rank_prob.p2}
            for seat in parsed_response.base
        ]
        + [
            {"Seat": seat.seat, "Rank": "P3", "Probability": seat.rank_prob.p3}
            for seat in parsed_response.base
        ]
        + [
            {"Seat": seat.seat, "Rank": "P4", "Probability": seat.rank_prob.p4}
            for seat in parsed_response.base
        ]
    )
    return px.bar(
        baseline_df,
        x="Seat",
        y="Probability",
        color="Rank",
        title="Baseline Rank Probability Stack",
    )


def _branch_df_with_baseline(base_summaries, branch_summaries: list):
    branch_df = branch_summaries_to_dataframe(base_summaries, branch_summaries)
    if branch_df.empty:
        return branch_df
    return branch_df[branch_df["category"] != "base"].reset_index(drop=True)


def main() -> None:
    st.set_page_config(page_title="NAGA ptEV Analyzer", layout="wide")
    st.title("NAGA ptEV Analyzer")

    with st.sidebar:
        storage_state_path = st.text_input("Storage state path", value=".secrets/naga_state.json")
        kyoku = st.number_input("kyoku", min_value=0, step=1, value=2)
        honba = st.number_input("honba", min_value=0, step=1, value=0)
        kyotaku = st.number_input("kyotaku", min_value=0, step=1, value=0)
        score0 = st.number_input("score0", step=1, value=250)
        score1 = st.number_input("score1", step=1, value=250)
        score2 = st.number_input("score2", step=1, value=250)
        score3 = st.number_input("score3", step=1, value=250)
        st.subheader("Rank point config")
        rp1 = st.number_input("rank point 1", value=75.0)
        rp2 = st.number_input("rank point 2", value=30.0)
        rp3 = st.number_input("rank point 3", value=0.0)
        rp4 = st.number_input("rank point 4", value=-105.0)
        run = st.button("Run analysis")

    if not run:
        return

    state = KyokuState(
        kyoku=int(kyoku),
        honba=int(honba),
        kyotaku=int(kyotaku),
        scores=[int(score0), int(score1), int(score2), int(score3)],
    )
    point_config = PointConfig(rank_points=[float(rp1), float(rp2), float(rp3), float(rp4)])

    parsed_response, raw_path = asyncio.run(_fetch_parsed_response(storage_state_path, state, point_config))
    baseline = summarize_baseline(parsed_response)
    ron_summaries = summarize_ron_branches(parsed_response)
    tsumo_summaries = summarize_tsumo_branches(parsed_response)
    ryukyoku_summaries = summarize_ryukyoku_branches(parsed_response)
    summary_df = branch_summaries_to_dataframe(baseline, ron_summaries, tsumo_summaries, ryukyoku_summaries)

    st.caption(f"Raw artifact: {raw_path}")
    st.subheader("Current baseline")
    baseline_df = pd.DataFrame(
        [
            {
                "seat": seat.seat,
                "ptev": seat.ptev,
                "p1": seat.rank_prob.p1,
                "p2": seat.rank_prob.p2,
                "p3": seat.rank_prob.p3,
                "p4": seat.rank_prob.p4,
            }
            for seat in parsed_response.base
        ]
    )
    st.dataframe(baseline_df, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.plotly_chart(_chart_baseline(parsed_response), use_container_width=True)
    with col2:
        st.plotly_chart(_chart_branch_delta(summary_df), use_container_width=True)
    with col3:
        st.plotly_chart(_chart_rank_stack(parsed_response), use_container_width=True)

    st.subheader("Ron branches")
    st.dataframe(_branch_df_with_baseline(baseline, ron_summaries), use_container_width=True)

    st.subheader("Tsumo branches")
    st.dataframe(_branch_df_with_baseline(baseline, tsumo_summaries), use_container_width=True)

    st.subheader("Ryukyoku branches")
    st.dataframe(_branch_df_with_baseline(baseline, ryukyoku_summaries), use_container_width=True)

    st.subheader("3900 ron candidates")
    ron_actor = st.number_input("Ron actor", min_value=0, max_value=3, value=0, key="ron_actor")
    ron_target_raw = st.selectbox("Ron target", options=["Any", 0, 1, 2, 3], index=0)
    ron_target = None if ron_target_raw == "Any" else int(ron_target_raw)
    ron_score_mv = st.number_input("Ron score movement", value=39.0, key="ron_score")
    ron_tolerance = st.number_input("Ron tolerance", value=0.5, min_value=0.0, key="ron_tol")
    ron_candidates = extract_ron_by_score_mv(
        parsed_response,
        actor=int(ron_actor),
        target=ron_target,
        score_mv=float(ron_score_mv),
        tolerance=float(ron_tolerance),
    )
    st.dataframe(_branch_df_with_baseline(baseline, ron_candidates), use_container_width=True)
    if len(ron_candidates) == 3:
        st.caption("Three-target average")
        st.dataframe(
            _branch_df_with_baseline(baseline, [aggregate_three_target_average(ron_candidates)]),
            use_container_width=True,
        )

    st.subheader("Mangan tsumo candidates")
    tsumo_actor = st.number_input("Tsumo actor", min_value=0, max_value=3, value=0, key="tsumo_actor")
    tsumo_candidates = [summary for summary in tsumo_summaries if summary.actor == int(tsumo_actor)]
    st.dataframe(_branch_df_with_baseline(baseline, tsumo_candidates), use_container_width=True)

    st.subheader("Kyotaku +1 comparison")
    _, kyotaku_plus_state = compare_current_and_kyotaku_plus_one(state)
    kyotaku_plus_response, _ = asyncio.run(_fetch_parsed_response(storage_state_path, kyotaku_plus_state, point_config))
    kyotaku_compare_df = pd.DataFrame(
        [
            {
                "seat": current.seat,
                "current_ptev": current.ptev,
                "kyotaku_plus_ptev": plus.ptev,
                "delta_ptev": plus.ptev - current.ptev,
            }
            for current, plus in zip(parsed_response.base, kyotaku_plus_response.base, strict=True)
        ]
    )
    st.dataframe(kyotaku_compare_df, use_container_width=True)

    csv_buffer = StringIO()
    summary_df.to_csv(csv_buffer, index=False)
    st.download_button(
        "Download CSV",
        data=csv_buffer.getvalue(),
        file_name="naga_analysis.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
