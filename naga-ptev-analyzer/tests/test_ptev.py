from __future__ import annotations

from naga_ptev.analysis import compute_ptev
from naga_ptev.models import PointConfig, RankProb


def test_compute_ptev_returns_top_rank_points_for_certain_first() -> None:
    point_config = PointConfig(rank_points=[75, 30, 0, -105])
    rank_prob = RankProb(p1=1.0, p2=0.0, p3=0.0, p4=0.0)
    assert compute_ptev(rank_prob, point_config) == 75


def test_compute_ptev_returns_fourth_rank_points_for_certain_fourth() -> None:
    point_config = PointConfig(rank_points=[75, 30, 0, -105])
    rank_prob = RankProb(p1=0.0, p2=0.0, p3=0.0, p4=1.0)
    assert compute_ptev(rank_prob, point_config) == -105


def test_compute_ptev_returns_zero_for_uniform_distribution() -> None:
    point_config = PointConfig(rank_points=[75, 30, 0, -105])
    rank_prob = RankProb(p1=0.25, p2=0.25, p3=0.25, p4=0.25)
    assert compute_ptev(rank_prob, point_config) == 0

