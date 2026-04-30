from __future__ import annotations

import socket
import unittest

from app.tenhou_ui_bridge_client import TenhouUiBridgeClient
from app.tenhou_ui_bridge_protocol import (
    TenhouUiBridgeStatus,
    VisibleHandState,
    build_tenhou_ui_bridge_ws_url,
    build_visible_hand_state,
    control_id_to_label,
    normalize_bridge_controls,
    normalize_bridge_toggle_controls,
    resolve_hand_index_by_tile37,
    resolve_hand_index_by_tile136,
    toggle_control_id_to_label,
)
from app.tenhou_ui_bridge_server import TenhouUiBridgeServer


class _FakeBridgeServer:
    def __init__(self) -> None:
        self.requests: list[tuple[dict[str, object], float]] = []
        self.status = TenhouUiBridgeStatus(ws_url=build_tenhou_ui_bridge_ws_url())

    def request(self, payload: dict[str, object], *, timeout_s: float) -> dict[str, object]:
        self.requests.append((dict(payload), timeout_s))
        return {"type": "command_result", "result": {"ok": True}, "requestId": "r1"}

    def snapshot_status(self) -> TenhouUiBridgeStatus:
        return self.status


class TenhouUiBridgeProtocolTests(unittest.TestCase):
    def test_build_visible_hand_state_appends_draw_tile_order(self) -> None:
        visible_hand = build_visible_hand_state(
            [1, 2, 3],
            4,
            hand_tiles_136=[0, 4, 8],
            hand_draw_tile_136=12,
        )
        self.assertEqual(visible_hand.displayed_tiles_37, (1, 2, 3, 4))
        self.assertEqual(visible_hand.displayed_tiles_136, (0, 4, 8, 12))

    def test_resolve_hand_index_by_tile37_uses_occurrence(self) -> None:
        visible_hand = VisibleHandState(displayed_tiles_37=(1, 5, 5, 9, 5))
        self.assertEqual(resolve_hand_index_by_tile37(visible_hand, 5), 1)
        self.assertEqual(resolve_hand_index_by_tile37(visible_hand, 5, occurrence=1), 2)
        self.assertEqual(resolve_hand_index_by_tile37(visible_hand, 5, occurrence=2), 4)
        self.assertIsNone(resolve_hand_index_by_tile37(visible_hand, 5, occurrence=3))

    def test_resolve_hand_index_by_tile37_falls_back_between_normal_and_red_fives(self) -> None:
        visible_hand = VisibleHandState(displayed_tiles_37=(1, 10, 11, 20, 21, 30))
        self.assertEqual(resolve_hand_index_by_tile37(visible_hand, 5), 1)
        self.assertEqual(resolve_hand_index_by_tile37(visible_hand, 15), 3)
        self.assertEqual(resolve_hand_index_by_tile37(visible_hand, 25), 5)
        self.assertEqual(resolve_hand_index_by_tile37(visible_hand, 10), 1)
        self.assertEqual(resolve_hand_index_by_tile37(visible_hand, 20), 3)
        self.assertEqual(resolve_hand_index_by_tile37(visible_hand, 30), 5)

    def test_resolve_hand_index_by_tile136_prefers_exact_identity(self) -> None:
        visible_hand = VisibleHandState(
            displayed_tiles_37=(5, 10, 10, 15),
            displayed_tiles_136=(16, 17, 18, 52),
        )
        self.assertEqual(resolve_hand_index_by_tile136(visible_hand, 18), 2)
        self.assertEqual(resolve_hand_index_by_tile136(visible_hand, 52), 3)

    def test_normalize_bridge_controls_uses_dom_text_when_present(self) -> None:
        controls = normalize_bridge_controls(
            [
                {"controlId": 2360328, "visible": True, "text": "スキップ"},
                {"controlId": 401412, "visible": True, "text": ""},
            ]
        )
        self.assertEqual(controls[0].label, "スキップ")
        self.assertEqual(controls[1].label, control_id_to_label(401412))

    def test_normalize_bridge_controls_excludes_persistent_toggle_controls(self) -> None:
        controls = normalize_bridge_controls(
            [
                {"controlId": 1183750, "visible": True, "text": "自動理牌"},
                {"controlId": 2360328, "visible": True, "text": "スキップ"},
            ]
        )
        self.assertEqual([control.control_id for control in controls], [2360328])

    def test_normalize_bridge_toggle_controls_keeps_fixed_order_and_flags(self) -> None:
        toggle_controls = normalize_bridge_toggle_controls(
            [
                {"controlId": 1183749, "visible": False, "available": True, "active": True, "text": ""},
                {"controlId": 1183753, "visible": True, "available": True, "active": False, "text": "ツモ切り"},
            ]
        )
        self.assertEqual(
            [toggle.control_id for toggle in toggle_controls],
            [1183750, 1183752, 1183753, 1183749],
        )
        self.assertEqual(toggle_controls[0].label, toggle_control_id_to_label(1183750))
        self.assertFalse(toggle_controls[0].available)
        self.assertEqual(toggle_controls[2].label, "ツモ切り")
        self.assertFalse(toggle_controls[2].active)
        self.assertTrue(toggle_controls[3].available)
        self.assertTrue(toggle_controls[3].active)

class TenhouUiBridgeClientTests(unittest.TestCase):
    def test_send_discard_by_index_formats_command(self) -> None:
        fake_server = _FakeBridgeServer()
        client = TenhouUiBridgeClient(
            fake_server,
            visible_hand_provider=lambda: VisibleHandState(displayed_tiles_37=(1, 2, 3, 4, 5)),
        )
        client.send_discard_by_index(4, timeout_s=1.25)
        self.assertEqual(
            fake_server.requests,
            [
                (
                    {"type": "discard_by_index", "handIndex": 4, "visibleHandCount": 5},
                    1.25,
                )
            ],
        )

    def test_request_table_snapshot_formats_command(self) -> None:
        fake_server = _FakeBridgeServer()
        client = TenhouUiBridgeClient(fake_server)
        client.request_table_snapshot(timeout_s=2.5)
        self.assertEqual(
            fake_server.requests,
            [
                (
                    {"type": "table_snapshot"},
                    2.5,
                )
            ],
        )

    def test_send_discard_by_tile136_resolves_local_hand_index(self) -> None:
        fake_server = _FakeBridgeServer()
        client = TenhouUiBridgeClient(
            fake_server,
            visible_hand_provider=lambda: VisibleHandState(
                displayed_tiles_37=(1, 5, 10, 15, 31),
                displayed_tiles_136=(0, 16, 17, 52, 108),
            ),
        )
        client.send_discard_by_tile136(17)
        self.assertEqual(
            fake_server.requests[0][0],
            {"type": "discard_by_index", "handIndex": 2, "visibleHandCount": 5},
        )

    def test_send_discard_by_tile37_accepts_normal_five_for_displayed_red_five(self) -> None:
        fake_server = _FakeBridgeServer()
        client = TenhouUiBridgeClient(
            fake_server,
            visible_hand_provider=lambda: VisibleHandState(displayed_tiles_37=(1, 10, 11, 21, 31)),
        )
        client.send_discard_by_tile37(5)
        self.assertEqual(
            fake_server.requests[0][0],
            {"type": "discard_by_index", "handIndex": 1, "visibleHandCount": 5},
        )

    def test_send_discard_by_index_rejects_non_actionable_visible_hand(self) -> None:
        fake_server = _FakeBridgeServer()
        client = TenhouUiBridgeClient(
            fake_server,
            visible_hand_provider=lambda: VisibleHandState(displayed_tiles_37=(1, 2, 3, 4)),
        )
        with self.assertRaisesRegex(RuntimeError, "VISIBLE_HAND_NOT_ACTIONABLE"):
            client.send_discard_by_index(2)
        self.assertEqual(fake_server.requests, [])

    def test_send_discard_by_index_manual_override_omits_non_actionable_visible_hand_count(self) -> None:
        fake_server = _FakeBridgeServer()
        client = TenhouUiBridgeClient(
            fake_server,
            visible_hand_provider=lambda: VisibleHandState(displayed_tiles_37=(1, 2, 3, 4)),
        )
        client.send_discard_by_index(2, require_actionable_visible_hand=False)
        self.assertEqual(
            fake_server.requests[0][0],
            {"type": "discard_by_index", "handIndex": 2},
        )

    def test_send_discard_by_index_allows_empty_visible_hand_probe_mode(self) -> None:
        fake_server = _FakeBridgeServer()
        client = TenhouUiBridgeClient(
            fake_server,
            visible_hand_provider=lambda: VisibleHandState(displayed_tiles_37=()),
        )
        client.send_discard_by_index(2)
        self.assertEqual(
            fake_server.requests[0][0],
            {"type": "discard_by_index", "handIndex": 2},
        )

    def test_camel_case_aliases_delegate_to_same_requests(self) -> None:
        fake_server = _FakeBridgeServer()
        client = TenhouUiBridgeClient(
            fake_server,
            visible_hand_provider=lambda: VisibleHandState(displayed_tiles_37=(1, 2, 3)),
        )
        client.sendPing()
        client.requestUiSnapshot()
        client.requestTableSnapshot()
        client.sendClickControl(2360328)
        self.assertEqual(
            [payload["type"] for payload, _timeout_s in fake_server.requests],
            ["ping", "ui_snapshot", "table_snapshot", "click_control"],
        )


class TenhouUiBridgeServerTests(unittest.TestCase):
    def test_second_server_on_same_port_raises_bind_error(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temp_socket:
            temp_socket.bind(("127.0.0.1", 0))
            host, port = temp_socket.getsockname()
        first_server = TenhouUiBridgeServer(host=host, port=port)
        first_server.start()
        try:
            second_server = TenhouUiBridgeServer(host=host, port=port)
            with self.assertRaises(OSError):
                second_server.start()
        finally:
            first_server.close()


if __name__ == "__main__":
    unittest.main()
