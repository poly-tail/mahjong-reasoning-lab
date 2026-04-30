from __future__ import annotations

from typing import Any, Callable

from app.tenhou_ui_bridge_protocol import (
    DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    TenhouUiBridgeStatus,
    VisibleHandState,
    resolve_hand_index_by_tile37,
    resolve_hand_index_by_tile136,
)
from app.tenhou_ui_bridge_server import TenhouUiBridgeServer


class TenhouUiBridgeClient:
    """Application-facing API for the Tenhou UI Bridge transport."""

    def __init__(
        self,
        server: TenhouUiBridgeServer,
        *,
        visible_hand_provider: Callable[[], VisibleHandState] | None = None,
    ) -> None:
        # Keep this client intentionally thin: it shapes local app requests, but it does not learn
        # how to inspect Tenhou by itself. That keeps packet-derived recognition and browser-side
        # execution separated.
        self._server = server
        self._visible_hand_provider = visible_hand_provider

    def snapshot_status(self) -> TenhouUiBridgeStatus:
        """Return the latest bridge status snapshot for diagnostics/debug UI."""

        # GUI/debug panels should read status through this method instead of touching transport
        # internals. That lets the server own thread-safety and status snapshot formatting.
        return self._server.snapshot_status()

    def set_visible_hand_provider(
        self,
        provider: Callable[[], VisibleHandState] | None,
    ) -> None:
        """Replace the app-side hand-order provider used by tile-to-index helpers."""

        self._visible_hand_provider = provider

    def send_ping(self, *, timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S) -> dict[str, Any]:
        """Check whether the extension transport loop is currently alive."""

        return self._server.request({"type": "ping"}, timeout_s=timeout_s)

    def request_ui_snapshot(
        self,
        *,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Ask the extension for the currently visible Tenhou UI controls."""

        return self._server.request({"type": "ui_snapshot"}, timeout_s=timeout_s)

    def request_table_snapshot(
        self,
        *,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Ask the extension for the current in-browser table state snapshot."""

        return self._server.request({"type": "table_snapshot"}, timeout_s=timeout_s)

    def send_discard_by_index(
        self,
        hand_index: int,
        *,
        require_actionable_visible_hand: bool = True,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Execute one discard click against the currently visible hand slot."""

        normalized_hand_index = int(hand_index)
        if not 0 <= normalized_hand_index <= 13:
            raise ValueError("hand_index must be in 0..13.")
        visible_hand_count = None
        if self._visible_hand_provider is not None:
            try:
                visible_hand_count = len(self._current_visible_hand().displayed_tiles_37)
            except Exception:
                visible_hand_count = None
        if visible_hand_count is not None and visible_hand_count > 0 and visible_hand_count % 3 != 2:
            if require_actionable_visible_hand:
                raise RuntimeError(
                    f"VISIBLE_HAND_NOT_ACTIONABLE: visible_hand_count={visible_hand_count}"
                )
            visible_hand_count = None
        # The wire protocol uses `handIndex` on purpose. The extension should only know which
        # visible slot to click, not how to infer tile identity from page state.
        payload = {
            "type": "discard_by_index",
            "handIndex": normalized_hand_index,
        }
        if visible_hand_count is not None and visible_hand_count > 0:
            payload["visibleHandCount"] = int(visible_hand_count)
        return self._server.request(payload, timeout_s=timeout_s)

    def send_click_control(
        self,
        control_id: int,
        *,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Execute one visible Tenhou candidate-button click by control id."""

        return self._server.request(
            {
                "type": "click_control",
                "controlId": int(control_id),
            },
            timeout_s=timeout_s,
        )

    def resolve_hand_index_by_tile37(
        self,
        tile_37: int,
        *,
        occurrence: int = 0,
    ) -> int | None:
        """Resolve one visible hand index from the local app's displayed tile order."""

        # The local app already owns visible hand ordering, so resolve here before crossing the
        # WebSocket boundary. This prevents recognition logic from leaking into the extension.
        return resolve_hand_index_by_tile37(
            self._current_visible_hand(),
            int(tile_37),
            occurrence=occurrence,
        )

    def resolve_hand_index_by_tile136(self, tile_136: int) -> int | None:
        """Resolve one visible hand index from an exact 136-id when the app can provide it."""

        return resolve_hand_index_by_tile136(
            self._current_visible_hand(),
            int(tile_136),
        )

    def send_discard_by_tile37(
        self,
        tile_37: int,
        *,
        occurrence: int = 0,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Future-facing hook that still converts into the protocol's hand-index command."""

        # This exists as an app-side convenience API only. The transport remains `discard_by_index`
        # so browser-side code stays ignorant of tile conversion rules.
        hand_index = self.resolve_hand_index_by_tile37(tile_37, occurrence=occurrence)
        if hand_index is None:
            raise LookupError(f"DISPLAYED_TILE37_NOT_FOUND: tile_37={tile_37} occurrence={occurrence}")
        return self.send_discard_by_index(hand_index, timeout_s=timeout_s)

    def send_discard_by_tile136(
        self,
        tile_136: int,
        *,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Future-facing hook that resolves the displayed hand index locally."""

        hand_index = self.resolve_hand_index_by_tile136(tile_136)
        if hand_index is None:
            raise LookupError(f"DISPLAYED_TILE136_NOT_FOUND: tile_136={tile_136}")
        return self.send_discard_by_index(hand_index, timeout_s=timeout_s)

    # The bridge design document used camelCase API names. Keep these aliases so existing notes and
    # ad-hoc local scripts can call the same client without translation.
    def sendPing(self, *, timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S) -> dict[str, Any]:
        return self.send_ping(timeout_s=timeout_s)

    def requestUiSnapshot(self, *, timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S) -> dict[str, Any]:
        return self.request_ui_snapshot(timeout_s=timeout_s)

    def requestTableSnapshot(
        self,
        *,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        return self.request_table_snapshot(timeout_s=timeout_s)

    def sendDiscardByIndex(
        self,
        hand_index: int,
        *,
        require_actionable_visible_hand: bool = True,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        return self.send_discard_by_index(
            hand_index,
            require_actionable_visible_hand=require_actionable_visible_hand,
            timeout_s=timeout_s,
        )

    def sendClickControl(
        self,
        control_id: int,
        *,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        return self.send_click_control(control_id, timeout_s=timeout_s)

    def _current_visible_hand(self) -> VisibleHandState:
        """Read the current visible hand order from the bound app-side provider."""

        provider = self._visible_hand_provider
        if provider is None:
            raise RuntimeError("VISIBLE_HAND_PROVIDER_NOT_CONFIGURED")
        visible_hand = provider()
        # Enforce one typed boundary here so downstream helpers can stay simple and deterministic.
        if not isinstance(visible_hand, VisibleHandState):
            raise TypeError("visible_hand_provider must return VisibleHandState.")
        return visible_hand
