import unittest
from unittest.mock import patch

import app.main as app_main
from capture.state import CaptureState, mark_runtime_thread_progress, snapshot_runtime_thread_progress


class LiveRuntimeWatchdogTest(unittest.TestCase):
    def test_build_stale_runtime_thread_reports_returns_only_expired_threads(self) -> None:
        state = CaptureState()

        with patch("capture.state.time.monotonic", return_value=100.0):
            mark_runtime_thread_progress(
                state,
                "capture",
                "parse_fragment",
                detail="fragment=<D34/>",
                blocked_hint="inside fragment parser",
                stale_after_s=2.0,
                repeat_after_s=7.0,
            )
            mark_runtime_thread_progress(
                state,
                "ui",
                "mainloop_heartbeat",
                detail="tk after heartbeat",
                blocked_hint="Tk mainloop heartbeat stopped",
                stale_after_s=10.0,
                repeat_after_s=20.0,
            )

        reports = app_main._build_stale_runtime_thread_reports(
            snapshot_runtime_thread_progress(state),
            now_monotonic=103.5,
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["thread_name"], "capture")
        self.assertEqual(reports[0]["stage"], "parse_fragment")
        self.assertAlmostEqual(reports[0]["age_s"], 3.5)
        self.assertEqual(reports[0]["repeat_after_s"], 7.0)

    def test_format_stale_runtime_thread_report_includes_stage_reason_and_detail(self) -> None:
        message = app_main._format_stale_runtime_thread_report(
            {
                "thread_name": "capture",
                "stage": "persist_event",
                "blocked_hint": "inside capture.storage.persist_event",
                "detail": "event=agari",
                "age_s": 4.2,
            }
        )

        self.assertIn("[watchdog]", message)
        self.assertIn("thread=capture", message)
        self.assertIn("stage=persist_event", message)
        self.assertIn("reason=inside capture.storage.persist_event", message)
        self.assertIn("detail=event=agari", message)


if __name__ == "__main__":
    unittest.main()
