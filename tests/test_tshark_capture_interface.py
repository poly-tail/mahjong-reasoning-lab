import unittest
from unittest.mock import patch

from capture.tshark_capture import resolve_tshark_interface


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


if __name__ == "__main__":
    unittest.main()
