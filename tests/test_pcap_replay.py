from __future__ import annotations

import unittest
from unittest.mock import patch

from capture.pcap_replay import run_test_capture
from capture.state import CaptureState
from capture.tshark_capture import parse_tshark_output_line


class _FakePopen:
    def __init__(self, lines: list[str]) -> None:
        self.stdout = iter(lines)
        self.terminated = False

    def __enter__(self) -> "_FakePopen":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        return None

    def poll(self) -> int:
        return 0

    def terminate(self) -> None:
        self.terminated = True

    def wait(self) -> int:
        return 0


class PcapReplayTest(unittest.TestCase):
    def test_run_test_capture_sends_each_stdout_line_to_shared_parser_once(self) -> None:
        lines = [
            '1.0\t<INIT seed="0,0,0,0,0,1" ten="250,250,250,250" oya="0" hai="1,2,3"/>\n',
            "Capturing on 'Wi-Fi'\n",
            "2.0\tD60\n",
        ]
        parser_returns = [True, False, True]

        with (
            patch("capture.pcap_replay.build_pcap_tshark_command", return_value=["tshark"]),
            patch("capture.pcap_replay.initialize_db", return_value=None),
            patch("capture.pcap_replay.subprocess.Popen", return_value=_FakePopen(lines)),
            patch(
                "capture.pcap_replay.parse_tshark_output_line",
                side_effect=parser_returns,
            ) as parse_line,
            patch("capture.pcap_replay.time.sleep") as sleep,
        ):
            state = run_test_capture("sample.pcapng", interval_ms=10)

        self.assertIsInstance(state, CaptureState)
        self.assertEqual(parse_line.call_count, 3)
        self.assertEqual(
            [call.args[2] for call in parse_line.call_args_list],
            lines,
        )
        self.assertEqual(sleep.call_count, 2)

    def test_parse_tshark_output_line_reports_whether_a_payload_was_processed(self) -> None:
        state = CaptureState()

        self.assertFalse(parse_tshark_output_line(state, None, "Capturing on 'Wi-Fi'\n"))
        self.assertTrue(parse_tshark_output_line(state, None, "1.0\tD60\n"))


if __name__ == "__main__":
    unittest.main()
