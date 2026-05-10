from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request

NODOCCHI_TENHOU_LOG_BASE_URL = "https://nodocchi.moe/tenhoulog/#!&name="
NODOCCHI_PHOENIX_STATUS_API_URL = "https://nodocchi.moe/api/phoenix_status.php"
NODOCCHI_STATS_CACHE_TTL_SECONDS = 60 * 60

# The public search page keeps `name` in the URL fragment, so server-side
# fetching must use Nodocchi's JSON endpoint rather than the `#!&name=` page.


@dataclass(frozen=True)
class NodocchiMetric:
    label: str
    value: str | int | float | None
    percentile: str | int | float | None = None
    rank: str | int | float | None = None
    raw: str = ""


@dataclass(frozen=True)
class NodocchiStatsCategory:
    title: str
    metrics: tuple[NodocchiMetric, ...] = ()


@dataclass(frozen=True)
class NodocchiPlayerStats:
    playerName: str
    mode: str
    table: str
    sourceUrl: str
    fetchedAt: str
    categories: tuple[NodocchiStatsCategory, ...]
    summary: Mapping[str, str | int | float | None]


class NodocchiStatsError(RuntimeError):
    """Base error for Nodocchi status fetch/parse failures."""


class NodocchiStatsNotFound(NodocchiStatsError):
    """Raised when Nodocchi returns no Phoenix 4-player stats for the user."""


_stats_cache: dict[str, tuple[float, NodocchiPlayerStats]] = {}


# Labels are owned here instead of the renderer so the UI never needs to parse
# Nodocchi's raw metric keys or external HTML.
_METRIC_LABELS: dict[str, str] = {
    "totalrecord": "対局数",
    "totalgame": "局数",
    "order_Z": "平均順位",
    "order_top_Z": "1位率",
    "order_second_Z": "2位率",
    "order_third_Z": "3位率",
    "order_last_Z": "4位率",
    "exacta_Z": "連対率",
    "tobiZ": "飛び率",
    "stablerank_phoenix_X": "安定段位",
    "al_nyaku_up_Z": "AL順位上昇率",
    "al_nyaku_down_Z": "AL順位下降率",
    "agariC": "和了率",
    "agariVT": "和了平均得点",
    "agariVFT": "副露和了平均得点",
    "agariVJ": "和了巡目",
    "agariCT": "和了得点期待値",
    "tsumoV": "ツモ率",
    "damaV": "ダマ和了率",
    "kyoutakuVT": "和了時平均供託",
    "yakumanV": "役満率",
    "rinshan_V": "嶺上率",
    "riichC": "リーチ率",
    "riichsenV": "先制リーチ率",
    "riich_seikou_V": "リーチ成功率",
    "houjuu_after_riich_V": "放銃時リーチ率",
    "ippatsuV": "一発率",
    "uraV": "リーチ和了時平均裏ドラ",
    "houjuuC": "放銃率",
    "houjuuVT": "放銃平均点",
    "houjuuCT": "放銃失点期待値",
    "agari_minus_houjuu_C": "和了率 - 放銃率",
    "agari_minus_houjuu_CT": "和了期待値 - 放銃期待値",
    "fuuroC": "副露率",
    "fuuro_minus_houjuu_C": "副露率 - 放銃率",
    "kanC": "カン率",
    "someV": "染め手率",
    "sanshokuV": "三色率",
    "tanyaoV": "タンヤオ率",
    "chantaiV": "チャンタ系率",
    "toituV": "対子系率",
    "chiitoiV": "七対子率",
    "pinfuV": "平和率",
    "akaV": "和了時平均赤ドラ",
    "doraV": "和了時平均ドラ",
    "nagaretenpaiV": "流局時聴牌率",
    "nagareVT": "流局時平均得点",
    "shuushiCT": "局収支",
    "kaisenC": "切断率",
}

_PERCENT_KEYS = frozenset(
    {
        "agariC",
        "houjuuC",
        "riichC",
        "fuuroC",
        "tsumoV",
        "damaV",
        "kaisenC",
        "tobiZ",
        "nagaretenpaiV",
        "yakumanV",
        "ippatsuV",
        "kanC",
        "someV",
        "sanshokuV",
        "pinfuV",
        "tanyaoV",
        "chantaiV",
        "toituV",
        "chiitoiV",
        "riichsenV",
        "houjuu_after_riich_V",
        "riich_seikou_V",
        "al_nyaku_up_Z",
        "al_nyaku_down_Z",
        "rinshan_V",
        "order_top_Z",
        "order_second_Z",
        "order_third_Z",
        "order_last_Z",
        "exacta_Z",
        "fuuro_minus_houjuu_C",
        "agari_minus_houjuu_C",
    }
)

_COUNT_KEYS = frozenset({"totalrecord", "totalgame"})
_SCORE_KEYS = frozenset(
    {
        "agariVT",
        "agariVFT",
        "houjuuVT",
        "kyoutakuVT",
        "nagareVT",
        "agariCT",
        "houjuuCT",
        "agari_minus_houjuu_CT",
        "shuushiCT",
    }
)
_TWO_DECIMAL_KEYS = frozenset(
    {
        "order_Z",
        "stablerank_phoenix_X",
        "agariVJ",
        "akaV",
        "uraV",
        "doraV",
    }
)

_CATEGORY_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "概要",
        (
            "totalrecord",
            "totalgame",
            "order_Z",
            "agariC",
            "houjuuC",
            "fuuroC",
            "riichC",
            "nagaretenpaiV",
        ),
    ),
    (
        "順位",
        (
            "order_top_Z",
            "order_second_Z",
            "order_third_Z",
            "order_last_Z",
            "exacta_Z",
            "tobiZ",
            "stablerank_phoenix_X",
            "al_nyaku_up_Z",
            "al_nyaku_down_Z",
        ),
    ),
    (
        "アガリ",
        (
            "agariC",
            "agariVT",
            "agariVFT",
            "agariVJ",
            "agariCT",
            "tsumoV",
            "damaV",
            "kyoutakuVT",
            "yakumanV",
            "rinshan_V",
        ),
    ),
    (
        "リーチ",
        (
            "riichC",
            "riichsenV",
            "riich_seikou_V",
            "houjuu_after_riich_V",
            "ippatsuV",
            "uraV",
        ),
    ),
    (
        "放銃",
        (
            "houjuuC",
            "houjuuVT",
            "houjuuCT",
            "agari_minus_houjuu_C",
            "agari_minus_houjuu_CT",
        ),
    ),
    (
        "副露 / 仕掛け",
        (
            "fuuroC",
            "fuuro_minus_houjuu_C",
            "agariVFT",
            "kanC",
        ),
    ),
    (
        "役",
        (
            "someV",
            "sanshokuV",
            "tanyaoV",
            "chantaiV",
            "toituV",
            "chiitoiV",
            "pinfuV",
        ),
    ),
    (
        "ドラ",
        (
            "akaV",
            "doraV",
            "uraV",
        ),
    ),
    (
        "その他",
        (
            "nagaretenpaiV",
            "nagareVT",
            "shuushiCT",
            "kaisenC",
        ),
    ),
)


def build_nodocchi_search_url(player_name: str) -> str:
    normalized_name = str(player_name).strip()
    return NODOCCHI_TENHOU_LOG_BASE_URL + urllib.parse.quote(normalized_name, safe="")


def fetch_nodocchi_player_stats(
    player_name: str,
    *,
    timeout_s: float = 10.0,
    cache_ttl_s: float = NODOCCHI_STATS_CACHE_TTL_SECONDS,
) -> NodocchiPlayerStats:
    normalized_name = str(player_name).strip()
    if not normalized_name:
        raise NodocchiStatsError("プレイヤー名が空です。")
    now_monotonic = time.monotonic()
    cached_entry = _stats_cache.get(normalized_name)
    if cached_entry is not None:
        cached_at, cached_stats = cached_entry
        if now_monotonic - cached_at <= cache_ttl_s:
            return cached_stats

    # `all=1` returns the aggregate (`s4`) plus split records. The UI currently
    # displays the aggregate Phoenix 4-player record.
    query = urllib.parse.urlencode({"all": "1", "username": normalized_name})
    api_url = f"{NODOCCHI_PHOENIX_STATUS_API_URL}?{query}"
    payload = _fetch_json(api_url, timeout_s=timeout_s)
    stats = _parse_nodocchi_phoenix_status(normalized_name, payload)
    _stats_cache[normalized_name] = (now_monotonic, stats)
    return stats


def clear_nodocchi_stats_cache() -> None:
    _stats_cache.clear()


def _fetch_json(url: str, *, timeout_s: float) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "User-Agent": "TenhouHelper/1.0 (+https://nodocchi.moe/tenhoulog/)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise NodocchiStatsError(f"Nodocchi API HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise NodocchiStatsError(f"Nodocchi API に接続できません: {reason}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NodocchiStatsError("Nodocchi API の文字コードを解釈できません。") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise NodocchiStatsError("Nodocchi API のJSONを解釈できません。") from exc


def _parse_nodocchi_phoenix_status(
    player_name: str,
    payload: Any,
    *,
    fetched_at: str | None = None,
) -> NodocchiPlayerStats:
    if payload is False or payload is None:
        raise NodocchiStatsNotFound("このプレイヤーの鳳凰卓4人打ち成績が見つかりませんでした。")
    if isinstance(payload, list) and not payload:
        raise NodocchiStatsNotFound("このプレイヤーの鳳凰卓4人打ち成績が見つかりませんでした。")
    if not isinstance(payload, Mapping):
        raise NodocchiStatsError("Nodocchi API のレスポンス形式が想定外です。")
    s4_payload = payload.get("s4")
    if not isinstance(s4_payload, Mapping):
        raise NodocchiStatsNotFound("このプレイヤーの鳳凰卓4人打ち成績が見つかりませんでした。")

    derived_data = _with_derived_rank_rates(s4_payload)
    total_record = _as_float(derived_data.get("totalrecord"))
    if total_record is None or total_record <= 0:
        raise NodocchiStatsNotFound("このプレイヤーの鳳凰卓4人打ち成績が見つかりませんでした。")

    categories = _build_categories(derived_data)
    fetched_at_text = fetched_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    summary = {
        "games": _raw_count(derived_data.get("totalrecord")),
        "averageRank": _format_metric_value("order_Z", derived_data.get("order_Z")),
        "winRate": _format_metric_value("agariC", derived_data.get("agariC")),
        "dealInRate": _format_metric_value("houjuuC", derived_data.get("houjuuC")),
        "callRate": _format_metric_value("fuuroC", derived_data.get("fuuroC")),
        "riichiRate": _format_metric_value("riichC", derived_data.get("riichC")),
    }
    return NodocchiPlayerStats(
        playerName=str(player_name).strip(),
        mode="4man",
        table="phoenix",
        sourceUrl=build_nodocchi_search_url(player_name),
        fetchedAt=fetched_at_text,
        categories=categories,
        summary=summary,
    )


def _with_derived_rank_rates(data: Mapping[str, Any]) -> dict[str, Any]:
    derived = dict(data)
    top_rate = _as_float(derived.get("order_top_Z"))
    last_rate = _as_float(derived.get("order_last_Z"))
    exacta_rate = _as_float(derived.get("exacta_Z"))
    # Nodocchi exposes top, last, and exacta directly; 2nd/3rd rates are
    # derived so the status panel can show a complete rank-rate block.
    if top_rate is not None and exacta_rate is not None:
        derived["order_second_Z"] = _clamp_rate(exacta_rate - top_rate)
    if last_rate is not None and exacta_rate is not None:
        derived["order_third_Z"] = _clamp_rate(1.0 - exacta_rate - last_rate)
    return derived


def _build_categories(data: Mapping[str, Any]) -> tuple[NodocchiStatsCategory, ...]:
    categories: list[NodocchiStatsCategory] = []
    used_keys: set[str] = set()
    for title, keys in _CATEGORY_KEYS:
        metrics = tuple(
            metric
            for key in keys
            if (metric := _build_metric(key, data.get(key))) is not None
        )
        if not metrics:
            continue
        used_keys.update(metric.raw for metric in metrics if metric.raw)
        categories.append(NodocchiStatsCategory(title=title, metrics=metrics))

    ignored_keys = {"username", "starttime", "order"}
    extra_metrics = tuple(
        metric
        for key, value in sorted(data.items())
        if key not in used_keys and key not in ignored_keys and (metric := _build_metric(str(key), value)) is not None
    )
    if extra_metrics:
        categories.append(NodocchiStatsCategory(title="その他の取得指標", metrics=extra_metrics))
    return tuple(categories)


def _build_metric(key: str, value: Any) -> NodocchiMetric | None:
    if value is None:
        return None
    formatted_value = _format_metric_value(key, value)
    if formatted_value is None:
        return None
    return NodocchiMetric(
        label=_METRIC_LABELS.get(key, key),
        value=formatted_value,
        raw=key,
    )


def _format_metric_value(key: str, value: Any) -> str | int | float | None:
    numeric_value = _as_float(value)
    if numeric_value is None:
        if isinstance(value, str):
            return value
        return None
    if key in _COUNT_KEYS:
        return f"{int(round(numeric_value)):,}"
    if key in _PERCENT_KEYS:
        return f"{numeric_value * 100:.2f}%"
    if key in _SCORE_KEYS:
        return f"{numeric_value:,.0f}"
    if key in _TWO_DECIMAL_KEYS:
        return f"{numeric_value:.2f}"
    return f"{numeric_value:.4g}"


def _raw_count(value: Any) -> int | None:
    numeric_value = _as_float(value)
    if numeric_value is None:
        return None
    return int(round(numeric_value))


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_rate(value: float) -> float:
    return min(max(value, 0.0), 1.0)
