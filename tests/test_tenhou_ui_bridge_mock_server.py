from __future__ import annotations

import io
import json
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest
from urllib.request import Request, urlopen

from app.tenhou_ui_bridge_mock_server import (
    TENHOU_UI_BRIDGE_MOCK_PAGE_NAME,
    TENHOU_UI_BRIDGE_MOCK_TRACE_PATH,
    TENHOU_UI_BRIDGE_TRACE_STDOUT_PREFIX,
    TenhouUiBridgeMockRequestHandler,
    build_mock_page_url,
    build_trace_stdout_line,
    resolve_mock_web_root,
)


class TenhouUiBridgeMockServerTests(unittest.TestCase):
    def test_build_trace_stdout_line_prefixes_json_payload(self) -> None:
        line = build_trace_stdout_line({"eventType": "execute_request", "requestId": "x1"})
        self.assertTrue(line.startswith(f"{TENHOU_UI_BRIDGE_TRACE_STDOUT_PREFIX} "))
        self.assertIn('"eventType": "execute_request"', line)
        self.assertIn('"requestId": "x1"', line)

    def test_build_mock_page_url_uses_requested_host_and_port(self) -> None:
        self.assertEqual(
            build_mock_page_url("127.0.0.1", 18080),
            "http://127.0.0.1:18080/tenhou_ui_bridge_mock.html",
        )

    def test_mock_web_root_contains_expected_assets(self) -> None:
        web_root = resolve_mock_web_root()
        self.assertTrue(web_root.exists())
        self.assertTrue((web_root / TENHOU_UI_BRIDGE_MOCK_PAGE_NAME).exists())
        self.assertTrue((web_root / "tenhou_ui_bridge_mock.js").exists())

    def test_mock_page_mentions_bridge_globals(self) -> None:
        script_text = (resolve_mock_web_root() / "tenhou_ui_bridge_mock.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("window.U", script_text)
        self.assertIn("window.W", script_text)
        self.assertIn("window.Q", script_text)
        self.assertIn("window.kc", script_text)
        self.assertIn("traceUrl", script_text)

    def test_trace_endpoint_accepts_json_and_writes_stdout_line(self) -> None:
        trace_stdout = io.StringIO()
        web_root = resolve_mock_web_root()
        handler = partial(
            TenhouUiBridgeMockRequestHandler,
            directory=str(web_root),
            trace_stdout=trace_stdout,
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            request = Request(
                f"http://{host}:{port}{TENHOU_UI_BRIDGE_MOCK_TRACE_PATH}",
                data=json.dumps(
                    {
                        "eventType": "execute_request",
                        "requestId": "req-1",
                        "detail": {"command": {"type": "discard_by_index", "handIndex": 13}},
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                self.assertEqual(response.status, 204)
                self.assertEqual(response.read(), b"")
        finally:
            server.shutdown()
            thread.join(timeout=5.0)
            server.server_close()

        trace_line = trace_stdout.getvalue().strip()
        self.assertIn(TENHOU_UI_BRIDGE_TRACE_STDOUT_PREFIX, trace_line)
        self.assertIn('"eventType": "execute_request"', trace_line)
        self.assertIn('"handIndex": 13', trace_line)


if __name__ == "__main__":
    unittest.main()
