from __future__ import annotations

import argparse
import unittest

from app.tenhou_ui_bridge_probe import _command_runner_from_args
from app.tenhou_ui_bridge_protocol import TenhouUiBridgeStatus


class _FakeProbeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def send_ping(self, *, timeout_s: float) -> dict[str, object]:
        self.calls.append(("ping", (), {"timeout_s": timeout_s}))
        return {"type": "pong"}

    def request_ui_snapshot(self, *, timeout_s: float) -> dict[str, object]:
        self.calls.append(("ui_snapshot", (), {"timeout_s": timeout_s}))
        return {"type": "ui_snapshot_result"}

    def send_discard_by_index(self, hand_index: int, *, timeout_s: float) -> dict[str, object]:
        self.calls.append(("discard_by_index", (hand_index,), {"timeout_s": timeout_s}))
        return {"type": "command_result"}

    def send_click_control(self, control_id: int, *, timeout_s: float) -> dict[str, object]:
        self.calls.append(("click_control", (control_id,), {"timeout_s": timeout_s}))
        return {"type": "command_result"}

    def snapshot_status(self) -> TenhouUiBridgeStatus:
        return TenhouUiBridgeStatus(ws_url="ws://127.0.0.1:8765")


class TenhouUiBridgeProbeTests(unittest.TestCase):
    def test_command_runner_ping_delegates_to_client(self) -> None:
        client = _FakeProbeClient()
        runner = _command_runner_from_args(
            argparse.Namespace(command="ping", timeout_s=1.5)
        )
        runner(client)
        self.assertEqual(client.calls, [("ping", (), {"timeout_s": 1.5})])

    def test_command_runner_discard_delegates_hand_index(self) -> None:
        client = _FakeProbeClient()
        runner = _command_runner_from_args(
            argparse.Namespace(command="discard_by_index", hand_index=7, timeout_s=2.0)
        )
        runner(client)
        self.assertEqual(
            client.calls,
            [("discard_by_index", (7,), {"timeout_s": 2.0})],
        )

    def test_command_runner_control_delegates_control_id(self) -> None:
        client = _FakeProbeClient()
        runner = _command_runner_from_args(
            argparse.Namespace(command="click_control", control_id=2360328, timeout_s=3.0)
        )
        runner(client)
        self.assertEqual(
            client.calls,
            [("click_control", (2360328,), {"timeout_s": 3.0})],
        )


if __name__ == "__main__":
    unittest.main()
