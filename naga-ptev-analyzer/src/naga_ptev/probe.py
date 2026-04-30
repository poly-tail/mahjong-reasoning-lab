from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urljoin

from naga_ptev.models import KyokuState

NAGA_BASE_URL = "https://naga.dmv.nico"
NAGA_ANALYZER_PATH = "/naga_report/kyoku_bop/"
EXPECTED_FORM_FIELDS = (
    "kyoku",
    "honba",
    "kyotaku",
    "score0",
    "score1",
    "score2",
    "score3",
    "csrfmiddlewaretoken",
)


def build_kyoku_info(state: KyokuState) -> str:
    score_values = ",".join(str(int(score)) for score in state.scores)
    return f"{int(state.kyoku)},{int(state.honba)},{int(state.kyotaku)},0,{score_values}"


def build_target_url(state: KyokuState) -> str:
    return f"{NAGA_BASE_URL}{NAGA_ANALYZER_PATH}?kyoku_info={build_kyoku_info(state)}"


def resolve_endpoint_url(page_url: str, endpoint: str | None) -> str | None:
    if endpoint is None:
        return None
    return urljoin(page_url, endpoint)


def sanitize_fetch_calls(calls: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for raw_call in calls or ():
        body_fields: list[list[str]] = []
        for raw_pair in raw_call.get("bodyFields", []) or []:
            if not isinstance(raw_pair, Sequence) or len(raw_pair) != 2:
                continue
            key = str(raw_pair[0])
            value = "[redacted]" if key == "csrfmiddlewaretoken" else str(raw_pair[1])
            body_fields.append([key, value])
        sanitized.append(
            {
                "url": raw_call.get("url"),
                "method": raw_call.get("method"),
                "status": raw_call.get("status"),
                "bodyFields": body_fields,
                "json": raw_call.get("json"),
            }
        )
    return sanitized


def find_analyzer_result_call(calls: Sequence[Mapping[str, Any]] | None) -> tuple[str | None, dict[str, Any] | None]:
    for call in calls or ():
        raw_json = call.get("json")
        if isinstance(raw_json, Mapping) and "status" in raw_json and "result" in raw_json:
            return str(call.get("url") or ""), dict(raw_json)
    return None, None
