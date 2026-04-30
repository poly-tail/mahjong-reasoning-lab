from __future__ import annotations

import argparse
import json
import time
from typing import Any, Callable

from app.tenhou_ui_bridge_client import TenhouUiBridgeClient
from app.tenhou_ui_bridge_protocol import (
    DEFAULT_TENHOU_UI_BRIDGE_HOST,
    DEFAULT_TENHOU_UI_BRIDGE_PORT,
    build_visible_hand_state,
)
from app.tenhou_ui_bridge_server import TenhouUiBridgeServer


def _wait_for_extension_connection(
    client: TenhouUiBridgeClient,
    *,
    timeout_s: float,
) -> bool:
    """Poll the bridge status until the service worker connection appears."""

    # The probe CLI starts its own temporary bridge server. Give the extension a short window to
    # reconnect so one-shot manual checks do not need careful timing.
    deadline = time.monotonic() + max(timeout_s, 0.0)
    while time.monotonic() <= deadline:
        status = client.snapshot_status()
        if status.connected:
            return True
        time.sleep(0.1)
    return False


def _command_runner_from_args(args: argparse.Namespace) -> Callable[[TenhouUiBridgeClient], dict[str, Any]]:
    """Map one parsed subcommand into the matching bridge client call."""

    # Keep command mapping explicit instead of dynamic getattr so the probe stays small, readable,
    # and aligned with the officially supported wire commands.
    if args.command == "ping":
        return lambda client: client.send_ping(timeout_s=args.timeout_s)
    if args.command == "ui_snapshot":
        return lambda client: client.request_ui_snapshot(timeout_s=args.timeout_s)
    if args.command == "discard_by_index":
        return lambda client: client.send_discard_by_index(
            args.hand_index,
            timeout_s=args.timeout_s,
        )
    if args.command == "click_control":
        return lambda client: client.send_click_control(
            args.control_id,
            timeout_s=args.timeout_s,
        )
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> None:
    """Start a temporary local bridge server and issue one test command."""

    parser = argparse.ArgumentParser(
        description="Temporary probe CLI for end-to-end Tenhou UI Bridge checks.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_TENHOU_UI_BRIDGE_HOST,
        metavar="HOST",
        help="Bridge bind host. Default: %(default)s.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_TENHOU_UI_BRIDGE_PORT,
        metavar="PORT",
        help="Bridge bind port. Default: %(default)s.",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=2.5,
        metavar="SECONDS",
        help="Command response timeout. Default: %(default)s.",
    )
    parser.add_argument(
        "--connect-timeout-s",
        type=float,
        default=10.0,
        metavar="SECONDS",
        help="How long to wait for the extension service worker to connect. Default: %(default)s.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ping")
    subparsers.add_parser("ui_snapshot")

    discard_parser = subparsers.add_parser("discard_by_index")
    discard_parser.add_argument("hand_index", type=int)

    control_parser = subparsers.add_parser("click_control")
    control_parser.add_argument("control_id", type=int)

    args = parser.parse_args()

    if not str(args.host).strip():
        parser.error("--host must not be empty.")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in 1..65535.")
    if args.timeout_s <= 0:
        parser.error("--timeout-s must be > 0.")
    if args.connect_timeout_s < 0:
        parser.error("--connect-timeout-s must be >= 0.")
    if args.command == "discard_by_index" and not 0 <= args.hand_index <= 13:
        parser.error("discard_by_index hand_index must be in 0..13.")

    server = TenhouUiBridgeServer(host=args.host, port=args.port)
    client = TenhouUiBridgeClient(
        server,
        # The probe CLI does not own live game state. Provide an empty visible-hand provider so the
        # client shape stays valid while probe commands are limited to direct protocol checks.
        visible_hand_provider=lambda: build_visible_hand_state(()),
    )
    try:
        server.start()
    except OSError as exc:
        raise SystemExit(
            "Failed to bind the temporary bridge server. "
            "If the main visualizer app is already running, stop it before using "
            "app.tenhou_ui_bridge_probe because the extension connects to only one bridge "
            f"server at a time. Original error: {exc}"
        ) from exc
    try:
        if not _wait_for_extension_connection(client, timeout_s=args.connect_timeout_s):
            raise TimeoutError(
                "Extension did not connect within the requested timeout. "
                "If the main visualizer app is already running, stop it before using "
                "app.tenhou_ui_bridge_probe. The probe is a standalone temporary bridge server."
            )
        result = _command_runner_from_args(args)(client)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        server.close()


if __name__ == "__main__":
    main()
