from __future__ import annotations

import argparse
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import urlsplit

DEFAULT_TENHOU_UI_BRIDGE_MOCK_HOST = "127.0.0.1"
DEFAULT_TENHOU_UI_BRIDGE_MOCK_PORT = 18080
TENHOU_UI_BRIDGE_MOCK_PAGE_NAME = "tenhou_ui_bridge_mock.html"
TENHOU_UI_BRIDGE_MOCK_TRACE_PATH = "/__bridge_trace__"
TENHOU_UI_BRIDGE_TRACE_STDOUT_PREFIX = "TENHOU_UI_BRIDGE_TRACE"
# The mock page is intentionally static and stdlib-served so anyone can validate the extension
# without standing up Tenhou itself or adding extra web tooling to this repository.


def resolve_mock_web_root() -> Path:
    """Return the repo-local web root that contains the bridge mock page."""

    return Path(__file__).resolve().parents[2] / "tmp_web"


def build_mock_page_url(
    host: str = DEFAULT_TENHOU_UI_BRIDGE_MOCK_HOST,
    port: int = DEFAULT_TENHOU_UI_BRIDGE_MOCK_PORT,
) -> str:
    """Return the full URL of the local mock page used for end-to-end bridge checks."""

    return f"http://{str(host).strip()}:{int(port)}/{TENHOU_UI_BRIDGE_MOCK_PAGE_NAME}"


def build_trace_stdout_line(payload: Any) -> str:
    """Format one browser-side trace record for stdout inspection during mock runs."""

    # Keep the trace on one JSON line so it is easy to grep, redirect, or diff while manually
    # driving the extension. The mock server exists for end-to-end visibility, not pretty logging.
    return (
        f"{TENHOU_UI_BRIDGE_TRACE_STDOUT_PREFIX} "
        f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )


def _parse_trace_payload(raw_body: bytes) -> dict[str, Any]:
    """Decode one mock trace POST body into a JSON object."""

    if not raw_body:
        raise ValueError("TRACE_BODY_EMPTY")
    try:
        decoded_body = raw_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("TRACE_BODY_NOT_UTF8") from exc
    try:
        payload = json.loads(decoded_body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"TRACE_BODY_INVALID_JSON: {exc.msg}") from exc
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


class TenhouUiBridgeMockRequestHandler(SimpleHTTPRequestHandler):
    """Serve mock assets and accept browser-side bridge traces on a dedicated POST route."""

    def __init__(
        self,
        *args: Any,
        directory: str,
        trace_stdout: TextIO | None = None,
        **kwargs: Any,
    ) -> None:
        # The trace stream is injectable so tests can capture browser-side requests without having
        # to monkeypatch process-wide stdout.
        self._trace_stdout = trace_stdout if trace_stdout is not None else sys.stdout
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        """Silence default HTTP request logs so stdout stays focused on bridge traces."""

        return

    def do_POST(self) -> None:  # noqa: N802
        """Accept trace POSTs from the mock-only MAIN-world bridge hook."""

        if urlsplit(self.path).path != TENHOU_UI_BRIDGE_MOCK_TRACE_PATH:
            self.send_error(404, "Trace endpoint not found.")
            return

        raw_body = self.rfile.read(max(int(self.headers.get("Content-Length", "0")), 0))
        try:
            payload = _parse_trace_payload(raw_body)
        except ValueError as exc:
            body = json.dumps(
                {"ok": False, "error": str(exc)},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        print(build_trace_stdout_line(payload), file=self._trace_stdout, flush=True)
        self.send_response(204)
        self.end_headers()


def run_mock_server(
    host: str = DEFAULT_TENHOU_UI_BRIDGE_MOCK_HOST,
    port: int = DEFAULT_TENHOU_UI_BRIDGE_MOCK_PORT,
) -> None:
    """Serve `tmp_web/` so the extension can inject into the mock Tenhou-like page."""

    web_root = resolve_mock_web_root()
    if not web_root.exists():
        raise FileNotFoundError(f"Mock web root not found: {web_root}")
    if not (web_root / TENHOU_UI_BRIDGE_MOCK_PAGE_NAME).exists():
        raise FileNotFoundError(
            f"Mock page not found: {web_root / TENHOU_UI_BRIDGE_MOCK_PAGE_NAME}"
        )

    handler = partial(
        TenhouUiBridgeMockRequestHandler,
        directory=str(web_root),
        trace_stdout=sys.stdout,
    )
    # ThreadingHTTPServer keeps the page responsive even when the browser requests multiple assets
    # in parallel or the user refreshes while another request is still open.
    server = ThreadingHTTPServer((str(host).strip(), int(port)), handler)
    mock_page_url = build_mock_page_url(host, port)
    print(f"Tenhou UI Bridge mock page: {mock_page_url}")
    print(f"Mock bridge trace endpoint: {TENHOU_UI_BRIDGE_MOCK_TRACE_PATH}")
    print("Browser-side bridge requests and results will be printed to stdout.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    """Parse CLI args and run the local mock page server."""

    parser = argparse.ArgumentParser(
        description="Serve a local Tenhou UI Bridge mock page for end-to-end extension checks.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_TENHOU_UI_BRIDGE_MOCK_HOST,
        metavar="HOST",
        help="HTTP bind host. Default: %(default)s.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_TENHOU_UI_BRIDGE_MOCK_PORT,
        metavar="PORT",
        help="HTTP bind port. Default: %(default)s.",
    )
    args = parser.parse_args()

    if not str(args.host).strip():
        parser.error("--host must not be empty.")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in 1..65535.")
    run_mock_server(args.host, args.port)


if __name__ == "__main__":
    main()
