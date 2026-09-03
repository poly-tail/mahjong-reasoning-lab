import unittest
from unittest.mock import patch

from capture.state import CaptureState
from capture.tshark_capture import parse_tshark_output_line, resolve_tshark_interface


class TSharkInterfaceResolutionTest(unittest.TestCase):
    def test_resolve_prefers_wifi_over_loopback_default(self) -> None:
        with patch(
            "capture.tshark_capture._list_tshark_interfaces",
            return_value=[
                ("1", r"\Device\NPF_{A} (Bluetooth ネットワーク接続)"),
                ("2", r"\Device\NPF_{B} (Wi-Fi)"),
                ("5", r"\Device\NPF_Loopback (Adapter for loopback traffic capture)"),
            ],
        ):
            self.assertEqual(resolve_tshark_interface(), "2")

    def test_resolve_returns_explicit_override_unchanged(self) -> None:
        with patch("capture.tshark_capture._list_tshark_interfaces", return_value=[]):
            self.assertEqual(resolve_tshark_interface(r"\Device\NPF_{CUSTOM}"), r"\Device\NPF_{CUSTOM}")

    def test_resolve_uses_neutral_candidate_when_default_is_blocked(self) -> None:
        with patch(
            "capture.tshark_capture._list_tshark_interfaces",
            return_value=[
                ("3", r"\Device\NPF_{C} (Realtek Gaming 2.5GbE Family Controller)"),
                ("5", r"\Device\NPF_Loopback (Adapter for loopback traffic capture)"),
            ],
        ):
            self.assertEqual(resolve_tshark_interface(), "3")

    def test_resolve_uses_existing_neutral_candidate_when_default_is_missing(self) -> None:
        with patch(
            "capture.tshark_capture._list_tshark_interfaces",
            return_value=[
                ("3", r"\Device\NPF_{C} (Realtek Gaming 2.5GbE Family Controller)"),
            ],
        ):
            self.assertEqual(resolve_tshark_interface(), "3")

    def test_resolve_returns_existing_blocked_candidate_when_it_is_the_only_option(self) -> None:
        with patch(
            "capture.tshark_capture._list_tshark_interfaces",
            return_value=[
                ("7", r"\Device\NPF_Loopback (Adapter for loopback traffic capture)"),
            ],
        ):
            self.assertEqual(resolve_tshark_interface(), "7")

    def test_runtime_startup_message_is_info_not_warning(self) -> None:
        state = CaptureState()

        parsed = parse_tshark_output_line(state, None, "Capturing on 'Wi-Fi'\n")

        self.assertFalse(parsed)
        self.assertEqual(state.diagnostics[-1]["level"], "info")
        self.assertEqual(state.diagnostics[-1]["code"], "tshark_runtime_info")

    def test_runtime_failure_message_is_error(self) -> None:
        state = CaptureState()

        with patch("capture.tshark_capture._emit_live_capture_error") as emit_error:
            parsed = parse_tshark_output_line(
                state,
                None,
                "tshark: Invalid capture filter: syntax error\n",
            )

        self.assertFalse(parsed)
        self.assertEqual(state.diagnostics[-1]["level"], "error")
        self.assertEqual(state.diagnostics[-1]["code"], "tshark_runtime_error")
        emit_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
