from __future__ import annotations

from dataclasses import dataclass, field
import json
import threading
from typing import Any, Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.pystyle_simulator_protocol import (
    PystyleDisplayContext,
    PystyleWireResponse,
    SIMULATOR_FALLBACK_DISPLAY_TURN_INDEX,
    build_request_payload_from_hand_tiles37,
    request_payload_to_wire_dict,
    simulator_tile_to_tile37,
    tile37_to_compact_text,
    validate_response_body,
)

# SIMULATOR_POST_URL の定義。
SIMULATOR_POST_URL = "https://pystyle.info/apps/mahjong-cpp_0.9.1/post.py"
# SIMULATOR_USER_AGENT の定義。
SIMULATOR_USER_AGENT = "tenhou-hojo/1.0"
# SIMULATOR_TIMEOUT_S の定義。
SIMULATOR_TIMEOUT_S = 20.0


@dataclass(frozen=True)
class HandRecommendationEntry:
    """One ranked discard entry returned by the external simulator."""

    # rank を保持する。
    rank: int
    # tile_37 を保持する。
    tile_37: int
    # tile_text を保持する。
    tile_text: str
    # expected_value を保持する。
    expected_value: float
    # expected_value_text を保持する。
    expected_value_text: str
    # win_probability を保持する。
    win_probability: float | None = None
    # tenpai_probability を保持する。
    tenpai_probability: float | None = None


@dataclass(frozen=True)
class HandRecommendationSnapshot:
    """Thread-safe UI snapshot for the current POST-backed recommendation state."""
    items: tuple[HandRecommendationEntry, ...] = field(default_factory=tuple)
    subtitle_text: str = "pystyle.info へ現在手牌を POST します。"
    status_text: str = "AI TOP3 を押すと取得します。"
    is_loading: bool = False
    hand_key: tuple[int, ...] = field(default_factory=tuple)
    shanten: int | None = None
    turn_index: int = SIMULATOR_FALLBACK_DISPLAY_TURN_INDEX
    request_context_key: tuple[object, ...] = field(default_factory=tuple)
    round_token: str = ""

    # items の並びを保持する。
    items: tuple[HandRecommendationEntry, ...] = field(default_factory=tuple)
    # subtitle_text を保持する。
    subtitle_text: str = "pystyle.info へ現在手牌を POST します。"
    # status_text を保持する。
    status_text: str = "AI TOP3 を押すと取得します。"
    # is_loading を保持する。
    is_loading: bool = False
    # hand_key の並びを保持する。
    hand_key: tuple[int, ...] = field(default_factory=tuple)
    # turn_index を保持する。
    turn_index: int = SIMULATOR_FALLBACK_DISPLAY_TURN_INDEX
    # round_token を保持する。
    round_token: str = ""


def _display_context_meld_key(display_context: PystyleDisplayContext) -> tuple[object, ...]:
    """Serialize meld request entries into a stable equality key."""

    return tuple(
        (
            meld.type,
            tuple(int(tile) for tile in meld.tiles),
            int(meld.discarded_tile) if meld.discarded_tile is not None else None,
            int(meld.from_seat) if meld.from_seat is not None else None,
            tuple(sorted((str(key), str(value)) for key, value in meld.extras.items())),
        )
        for meld in display_context.melds
    )


def _effective_meld_tile_count(meld_type: int | str, physical_tile_count: int) -> int:
    """Return one meld's effective tile contribution for pre-discard sizing."""

    if meld_type in {0, 1, 2, 3, 4, "pon", "chi", "daiminkan", "ankan", "kakan"}:
        return 3
    return min(max(int(physical_tile_count), 0), 3)


def _display_context_effective_meld_tile_count(display_context: PystyleDisplayContext) -> int:
    """Return the hand-structure tile count represented by all current melds."""

    return sum(
        _effective_meld_tile_count(meld.type, len(meld.tiles))
        for meld in display_context.melds
    )


def _request_total_tile_count(
    hand_tiles_37: Sequence[int],
    display_context: PystyleDisplayContext,
) -> int:
    """Return the effective pre-discard hand size including meld structure."""

    return len(tuple(int(tile) for tile in hand_tiles_37)) + _display_context_effective_meld_tile_count(
        display_context
    )


def _display_context_request_key(display_context: PystyleDisplayContext) -> tuple[object, ...]:
    """Build the duplicate-suppression key for one request/display context."""

    return (
        int(display_context.turn_index),
        str(display_context.turn_source),
        display_context.wall_tiles_remaining,
        int(display_context.round_wind),
        int(display_context.seat_wind),
        tuple(int(tile) for tile in display_context.dora_indicator_tiles_37),
        _display_context_meld_key(display_context),
        tuple(int(count) for count in display_context.remaining_wall or ()),
        str(display_context.round_token),
    )


def _post_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """POST one validated request payload and decode the JSON response body."""

    request_body = json.dumps(payload).encode("utf-8")
    request = Request(
        SIMULATOR_POST_URL,
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": SIMULATOR_USER_AGENT,
        },
        method="POST",
    )
    with urlopen(request, timeout=SIMULATOR_TIMEOUT_S) as response:
        response_body = response.read().decode("utf-8", errors="replace")
    return json.loads(response_body)


def _value_at_turn(values: Sequence[float], turn_index: int) -> float:
    """Read one turn-indexed metric while clamping to the available response range."""

    if not values:
        return 0.0
    clamped_turn_index = max(0, min(turn_index, len(values) - 1))
    return float(values[clamped_turn_index])


def _build_success_snapshot(
    *,
    hand_key: tuple[int, ...],
    parsed_response: PystyleWireResponse,
    display_context: PystyleDisplayContext,
) -> HandRecommendationSnapshot:
    """Convert a validated success response into the compact top-3 UI snapshot."""
    request_context_key = _display_context_request_key(display_context)
    round_token = str(display_context.round_token)

    response_payload = parsed_response.response
    if response_payload is None:
        return HandRecommendationSnapshot(
            hand_key=hand_key,
            turn_index=display_context.turn_index,
            request_context_key=request_context_key,
            round_token=round_token,
            subtitle_text="pystyle.info の response が空です。",
            status_text="response.success=true ですが response 本体がありません。",
        )
    if not response_payload.config.calc_stats:
        return HandRecommendationSnapshot(
            hand_key=hand_key,
            shanten=int(response_payload.shanten.all),
            turn_index=display_context.turn_index,
            request_context_key=request_context_key,
            round_token=round_token,
            subtitle_text="pystyle.info / 4向聴以上は期待値順位を返しません。",
            status_text="この手牌では期待値ランキングを出せません。",
        )

    ranked_entries: list[HandRecommendationEntry] = []
    for stat in response_payload.stats:
        tile_37 = simulator_tile_to_tile37(stat.tile)
        if tile_37 is None:
            continue
        expected_value = _value_at_turn(stat.exp_score, display_context.turn_index)
        ranked_entries.append(
            HandRecommendationEntry(
                rank=0,
                tile_37=tile_37,
                tile_text=tile37_to_compact_text(tile_37),
                expected_value=expected_value,
                expected_value_text=f"{round(expected_value):.0f}pt",
                win_probability=_value_at_turn(stat.win_prob, display_context.turn_index),
                tenpai_probability=_value_at_turn(stat.tenpai_prob, display_context.turn_index),
            )
        )
    ranked_entries.sort(key=lambda entry: entry.expected_value, reverse=True)

    top_entries = tuple(
        HandRecommendationEntry(
            rank=index,
            tile_37=entry.tile_37,
            tile_text=entry.tile_text,
            expected_value=entry.expected_value,
            expected_value_text=entry.expected_value_text,
            win_probability=entry.win_probability,
            tenpai_probability=entry.tenpai_probability,
        )
        for index, entry in enumerate(ranked_entries[:3], start=1)
    )
    if not top_entries:
        return HandRecommendationSnapshot(
            hand_key=hand_key,
            shanten=int(response_payload.shanten.all),
            turn_index=display_context.turn_index,
            request_context_key=request_context_key,
            round_token=round_token,
            subtitle_text="pystyle.info から候補牌が返りませんでした。",
            status_text="response.stats に打牌候補がありません。",
        )

    return HandRecommendationSnapshot(
        items=top_entries,
        hand_key=hand_key,
        shanten=int(response_payload.shanten.all),
        turn_index=display_context.turn_index,
        request_context_key=request_context_key,
        round_token=round_token,
        subtitle_text="",
        status_text="",
    )


def fetch_recommendations_for_hand(
    hand_tiles_37: Sequence[int],
    *,
    display_context: PystyleDisplayContext | None = None,
) -> HandRecommendationSnapshot:
    """Synchronously fetch a POST-backed top-3 ranking for one current self hand."""

    hand_key = tuple(int(tile) for tile in hand_tiles_37)
    if display_context is None:
        display_context = PystyleDisplayContext(
            turn_index=SIMULATOR_FALLBACK_DISPLAY_TURN_INDEX,
            turn_source="frontend_fallback",
        )
    request_context_key = _display_context_request_key(display_context)
    total_tile_count = _request_total_tile_count(hand_key, display_context)
    effective_meld_tile_count = _display_context_effective_meld_tile_count(display_context)
    if total_tile_count != 14:
        return HandRecommendationSnapshot(
            hand_key=hand_key,
            turn_index=display_context.turn_index,
            request_context_key=request_context_key,
            round_token=str(display_context.round_token),
            subtitle_text="AI TOP3 は打牌前の 14 枚状態でのみ取得します。",
            status_text=f"concealed={len(hand_key)} meld={effective_meld_tile_count} total={total_tile_count}",
        )

    try:
        # Keep protocol validation and transport errors separated so the UI can distinguish
        # "simulator returned an unexpected body" from simple network failure.
        request_payload = build_request_payload_from_hand_tiles37(
            hand_key,
            round_wind=display_context.round_wind,
            seat_wind=display_context.seat_wind,
            dora_indicator_tiles_37=display_context.dora_indicator_tiles_37,
            melds=display_context.melds,
            remaining_wall=display_context.remaining_wall,
        )
        raw_response = _post_request_payload(request_payload_to_wire_dict(request_payload))
        parsed_response = validate_response_body(raw_response)
    except ValueError as exc:
        return HandRecommendationSnapshot(
            hand_key=hand_key,
            turn_index=display_context.turn_index,
            request_context_key=request_context_key,
            round_token=str(display_context.round_token),
            subtitle_text="request/response のバリデーションに失敗しました。",
            status_text=str(exc),
        )
    except HTTPError as exc:
        return HandRecommendationSnapshot(
            hand_key=hand_key,
            turn_index=display_context.turn_index,
            request_context_key=request_context_key,
            round_token=str(display_context.round_token),
            subtitle_text="pystyle.info への POST が HTTP エラーで失敗しました。",
            status_text=f"HTTP {exc.code}: {exc.reason}",
        )
    except URLError as exc:
        return HandRecommendationSnapshot(
            hand_key=hand_key,
            turn_index=display_context.turn_index,
            request_context_key=request_context_key,
            round_token=str(display_context.round_token),
            subtitle_text="pystyle.info との通信に失敗しました。",
            status_text=str(exc.reason),
        )
    except Exception as exc:
        return HandRecommendationSnapshot(
            hand_key=hand_key,
            turn_index=display_context.turn_index,
            request_context_key=request_context_key,
            round_token=str(display_context.round_token),
            subtitle_text="AI TOP3 の取得中に予期しない例外が発生しました。",
            status_text=str(exc),
        )

    if not parsed_response.success:
        return HandRecommendationSnapshot(
            hand_key=hand_key,
            turn_index=display_context.turn_index,
            request_context_key=request_context_key,
            round_token=str(display_context.round_token),
            subtitle_text="pystyle.info からエラー応答が返りました。",
            status_text=str(parsed_response.err_msg or "response.success=false"),
        )
    return _build_success_snapshot(
        hand_key=hand_key,
        parsed_response=parsed_response,
        display_context=display_context,
    )


class HandRecommendationService:
    """Own the background POST workflow and expose immutable UI snapshots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_token = 0
        self._update_sequence = 0
        self._snapshot = HandRecommendationSnapshot()
        self._thread_start_callback: Callable[[str], None] | None = None
        self._thread_finish_callback: Callable[[str], None] | None = None

    @property
    def update_sequence(self) -> int:
        """Return the monotonically increasing UI refresh token for this service."""

        with self._lock:
            return self._update_sequence

    def snapshot(self) -> HandRecommendationSnapshot:
        """Return the newest immutable panel snapshot."""

        with self._lock:
            return self._snapshot

    def reset(self) -> None:
        """Drop the current snapshot and invalidate any in-flight background request."""

        with self._lock:
            self._request_token += 1
            self._snapshot = HandRecommendationSnapshot()
            self._update_sequence += 1

    def set_thread_start_callback(
        self,
        callback: Callable[[str], None] | None,
    ) -> None:
        """Register one optional callback invoked when a background fetch thread starts."""

        with self._lock:
            self._thread_start_callback = callback

    def set_thread_activity_callbacks(
        self,
        *,
        start_callback: Callable[[str], None] | None = None,
        finish_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Register optional callbacks for background fetch lifecycle transitions."""

        with self._lock:
            self._thread_start_callback = start_callback
            self._thread_finish_callback = finish_callback

    def request(
        self,
        hand_tiles_37: Sequence[int],
        *,
        display_context: PystyleDisplayContext | None = None,
    ) -> None:
        """Queue one background fetch for the provided current hand."""

        hand_key = tuple(int(tile) for tile in hand_tiles_37)
        effective_display_context = (
            display_context
            if display_context is not None
            else PystyleDisplayContext(
                turn_index=SIMULATOR_FALLBACK_DISPLAY_TURN_INDEX,
                turn_source="frontend_fallback",
            )
        )
        request_context_key = _display_context_request_key(effective_display_context)
        total_tile_count = _request_total_tile_count(hand_key, effective_display_context)
        effective_meld_tile_count = _display_context_effective_meld_tile_count(
            effective_display_context
        )
        with self._lock:
            # Repeated redraws during the same visible hand should not spam duplicate POSTs.
            if hand_key == self._snapshot.hand_key and (
                self._snapshot.is_loading or self._snapshot.items
            ) and self._snapshot.request_context_key == request_context_key:
                return

            if total_tile_count != 14:
                self._snapshot = HandRecommendationSnapshot(
                    hand_key=hand_key,
                    turn_index=effective_display_context.turn_index,
                    request_context_key=request_context_key,
                    round_token=str(effective_display_context.round_token),
                    subtitle_text="AI TOP3 は打牌前の 14 枚状態でのみ取得します。",
                    status_text=f"concealed={len(hand_key)} meld={effective_meld_tile_count} total={total_tile_count}",
                )
                self._update_sequence += 1
                return

            self._request_token += 1
            request_token = self._request_token
            self._snapshot = HandRecommendationSnapshot(
                hand_key=hand_key,
                turn_index=effective_display_context.turn_index,
                request_context_key=request_context_key,
                round_token=str(effective_display_context.round_token),
                subtitle_text="pystyle.info へ現在手牌を POST しています。",
                status_text="計算中...",
                is_loading=True,
            )
            self._update_sequence += 1

        start_callback = self._thread_start_callback
        if callable(start_callback):
            start_callback("pystyle fetch")
        threading.Thread(
            target=self._request_worker,
            args=(request_token, hand_key, effective_display_context),
            name="hand-recommendation-fetch",
            daemon=True,
        ).start()

    def _request_worker(
        self,
        request_token: int,
        hand_key: tuple[int, ...],
        display_context: PystyleDisplayContext,
    ) -> None:
        """Fetch one response in the background and publish it if still current."""

        try:
            snapshot = fetch_recommendations_for_hand(
                hand_key,
                display_context=display_context,
            )
            with self._lock:
                # Ignore late responses from an older hand so the panel never snaps back after the user
                # has already drawn or discarded and requested a newer recommendation.
                if request_token != self._request_token:
                    return
                self._snapshot = snapshot
                self._update_sequence += 1
        finally:
            finish_callback = self._thread_finish_callback
            if callable(finish_callback):
                finish_callback("pystyle fetch")
