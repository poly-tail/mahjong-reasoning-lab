from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from naga_ptev.models import KyokuState


def normalize_state_payload(state: KyokuState | Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable hash payload while preserving seat score order."""

    if isinstance(state, KyokuState):
        kyoku = state.kyoku
        honba = state.honba
        kyotaku = state.kyotaku
        scores = state.scores
    else:
        kyoku = state.get("kyoku")
        honba = state.get("honba")
        kyotaku = state.get("kyotaku")
        scores = state.get("scores")
    if not isinstance(scores, Sequence) or isinstance(scores, (str, bytes, bytearray)) or len(scores) != 4:
        raise ValueError("KyokuState scores must contain exactly 4 seat-ordered values")
    return {
        "kyoku": int(kyoku),
        "honba": int(honba),
        "kyotaku": int(kyotaku),
        "scores": [int(score) for score in scores],
    }


def state_hash(state: KyokuState | Mapping[str, Any]) -> str:
    payload = normalize_state_payload(state)
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

