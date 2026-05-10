from __future__ import annotations

from pathlib import Path
import sys

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.nodocchi_stats import (
    NodocchiStatsNotFound,
    _parse_nodocchi_phoenix_status,
    build_nodocchi_search_url,
)


def test_build_nodocchi_search_url_encodes_fragment_name() -> None:
    assert build_nodocchi_search_url("ハマー") == (
        "https://nodocchi.moe/tenhoulog/#!&name=%E3%83%8F%E3%83%9E%E3%83%BC"
    )


def test_parse_phoenix_status_builds_summary_and_rank_rates() -> None:
    stats = _parse_nodocchi_phoenix_status(
        "player",
        {
            "s4": {
                "totalrecord": 100,
                "totalgame": 1200,
                "order_Z": 2.41,
                "order_top_Z": 0.28,
                "order_last_Z": 0.18,
                "exacta_Z": 0.55,
                "agariC": 0.2234,
                "houjuuC": 0.1123,
                "fuuroC": 0.3456,
                "riichC": 0.1987,
                "nagaretenpaiV": 0.44,
                "agariVT": 6345.6,
                "houjuuVT": 5123.4,
            }
        },
        fetched_at="2026-05-09T12:00:00+09:00",
    )

    assert stats.playerName == "player"
    assert stats.mode == "4man"
    assert stats.table == "phoenix"
    assert stats.summary["games"] == 100
    assert stats.summary["averageRank"] == "2.41"
    assert stats.summary["winRate"] == "22.34%"
    assert stats.summary["dealInRate"] == "11.23%"

    rank_metrics = {
        metric.label: metric.value
        for category in stats.categories
        if category.title == "順位"
        for metric in category.metrics
    }
    assert rank_metrics["1位率"] == "28.00%"
    assert rank_metrics["2位率"] == "27.00%"
    assert rank_metrics["3位率"] == "27.00%"
    assert rank_metrics["4位率"] == "18.00%"


@pytest.mark.parametrize("payload", [False, [], {}, {"s4": {"totalrecord": 0}}])
def test_parse_phoenix_status_raises_not_found_for_missing_s4(payload: object) -> None:
    with pytest.raises(NodocchiStatsNotFound):
        _parse_nodocchi_phoenix_status("missing", payload)
