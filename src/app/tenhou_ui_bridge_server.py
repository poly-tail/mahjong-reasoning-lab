from __future__ import annotations

import base64
import copy
import hashlib
import json
import queue
import socket
import struct
import threading
from typing import Any, Mapping
from uuid import uuid4

from app.tenhou_ui_bridge_protocol import (
    DEFAULT_TENHOU_UI_BRIDGE_HOST,
    DEFAULT_TENHOU_UI_BRIDGE_PORT,
    DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    TenhouUiBridgeStatus,
    build_tenhou_ui_bridge_ws_url,
    normalize_bridge_controls,
    normalize_bridge_toggle_controls,
)

_WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_MAX_HTTP_HEADER_BYTES = 32 * 1024
_TEXT_OPCODE = 0x1
_CLOSE_OPCODE = 0x8
_PING_OPCODE = 0x9
_PONG_OPCODE = 0xA
# A manual RFC6455 subset is enough here because we only need one localhost connection from the
# MV3 service worker. Keeping it in stdlib avoids adding a new runtime dependency just for bridge I/O.


class TenhouUiBridgeServer:
    """Threaded localhost WebSocket server used by the MV3 service worker.

    The local visualizer remains the source of truth for state recognition. This server only
    transports command/response payloads to the extension, so the extension can stay focused on
    UI execution.
    """

    def __init__(
        self,
        host: str = DEFAULT_TENHOU_UI_BRIDGE_HOST,
        port: int = DEFAULT_TENHOU_UI_BRIDGE_PORT,
    ) -> None:
        self.host = str(host).strip()
        self.port = int(port)
        self.ws_url = build_tenhou_ui_bridge_ws_url(self.host, self.port)
        # Status snapshots, socket writes, and request/reply bookkeeping are touched by different
        # threads. Keep the lock scopes narrow and purpose-specific so the bridge remains simple.
        self._status_lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._pending_lock = threading.RLock()
        # Each outbound request gets one queue keyed by requestId. When the extension replies, the
        # reader thread drops the payload into the matching queue and the caller unblocks.
        self._pending_replies: dict[str, queue.Queue[dict[str, Any]]] = {}
        self._stop_event = threading.Event()
        self._server_socket: socket.socket | None = None
        self._client_socket: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._client_thread: threading.Thread | None = None
        self._status = TenhouUiBridgeStatus(ws_url=self.ws_url)

    def start(self) -> None:
        """Start listening synchronously so bind errors surface to the caller."""

        if self._server_socket is not None:
            return
        if not self.host:
            raise ValueError("Tenhou UI Bridge host must not be empty.")
        if not 1 <= self.port <= 65535:
            raise ValueError("Tenhou UI Bridge port must be in 1..65535.")

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                # On Windows, SO_REUSEADDR allows a second process to bind the same port while the
                # first bridge server is still listening. That makes probe/manual troubleshooting
                # very confusing because the extension keeps talking to whichever listener won the
                # race. Use exclusive bind semantics there so "app is already using 8765" fails
                # fast.
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                # On POSIX we still want quick restart behavior after a clean shutdown.
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(1)
            server_socket.settimeout(0.5)
        except Exception:
            self._close_socket(server_socket)
            raise
        self._server_socket = server_socket
        self._set_status(listening=True, last_event="listening", last_error="")
        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            name="tenhou-ui-bridge-accept",
            daemon=True,
        )
        self._accept_thread.start()

    def close(self) -> None:
        """Stop the listening socket and tear down the active extension connection."""

        self._stop_event.set()
        client_socket = self._swap_client_socket(None)
        if client_socket is not None:
            self._close_socket(client_socket)
        server_socket = self._server_socket
        self._server_socket = None
        if server_socket is not None:
            self._close_socket(server_socket)
        with self._pending_lock:
            pending_replies = list(self._pending_replies.values())
            self._pending_replies.clear()
        for pending_queue in pending_replies:
            pending_queue.put(
                {
                    "type": "command_result",
                    "result": {"ok": False, "error": "BRIDGE_SERVER_CLOSED"},
                }
            )
        self._set_status(
            listening=False,
            connected=False,
            extension_ready=False,
            last_event="closed",
        )

    def snapshot_status(self) -> TenhouUiBridgeStatus:
        """Return a copy-safe status snapshot for the local app."""

        with self._status_lock:
            return copy.deepcopy(self._status)

    def request(
        self,
        payload: Mapping[str, Any],
        *,
        timeout_s: float = DEFAULT_TENHOU_UI_BRIDGE_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Send one JSON command to the extension and wait for the correlated response."""

        normalized_payload = dict(payload)
        request_id = str(normalized_payload.get("requestId") or uuid4().hex)
        normalized_payload["requestId"] = request_id
        # Keep one queue per request rather than one shared receive queue so different callers can
        # safely wait in parallel without re-implementing message demultiplexing on the app side.
        pending_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
        with self._pending_lock:
            self._pending_replies[request_id] = pending_queue
        try:
            self._send_text(json.dumps(normalized_payload, ensure_ascii=False))
        except Exception:
            with self._pending_lock:
                self._pending_replies.pop(request_id, None)
            raise
        self._set_status(last_sent_command=copy.deepcopy(normalized_payload), last_event="request_sent")
        try:
            reply = pending_queue.get(timeout=max(float(timeout_s), 0.01))
        except queue.Empty as exc:
            with self._pending_lock:
                self._pending_replies.pop(request_id, None)
            timeout_error = f"BRIDGE_REQUEST_TIMEOUT: {request_id}"
            self._set_status(last_error=timeout_error, last_event="request_timeout")
            raise TimeoutError(timeout_error) from exc
        return reply

    def _accept_loop(self) -> None:
        """Accept extension connections and replace the active client when Chrome reconnects."""

        while not self._stop_event.is_set():
            server_socket = self._server_socket
            if server_socket is None:
                return
            try:
                client_socket, _address = server_socket.accept()
            except socket.timeout:
                continue
            except OSError as exc:
                if not self._stop_event.is_set():
                    self._set_status(last_error=str(exc), last_event="accept_failed")
                return
            try:
                self._perform_websocket_handshake(client_socket)
            except Exception as exc:  # noqa: BLE001 - network boundary must stay resilient.
                self._close_socket(client_socket)
                self._set_status(last_error=str(exc), last_event="handshake_failed")
                continue
            # The service worker may reconnect when Chrome reloads the extension or when its worker
            # process is restarted. Always replace the old client so the local app keeps one active
            # browser executor without needing a full restart.
            previous_socket = self._swap_client_socket(client_socket)
            if previous_socket is not None:
                self._close_socket(previous_socket)
            self._set_status(
                connected=True,
                extension_ready=False,
                last_error="",
                last_event="client_connected",
            )
            self._client_thread = threading.Thread(
                target=self._client_loop,
                args=(client_socket,),
                name="tenhou-ui-bridge-client",
                daemon=True,
            )
            self._client_thread.start()

    def _client_loop(self, client_socket: socket.socket) -> None:
        """Read JSON frames from the extension until the socket closes."""

        try:
            while not self._stop_event.is_set():
                opcode, payload = self._read_frame(client_socket)
                if opcode == _TEXT_OPCODE:
                    self._handle_text_message(payload.decode("utf-8", errors="replace"))
                    continue
                if opcode == _PING_OPCODE:
                    # Browsers may ping independently of app traffic. Reflect it here so the
                    # transport remains healthy even when no commands are in flight.
                    self._send_frame(client_socket, _PONG_OPCODE, payload)
                    continue
                if opcode == _PONG_OPCODE:
                    continue
                if opcode == _CLOSE_OPCODE:
                    break
        except (ConnectionError, OSError):
            pass
        finally:
            if self._swap_client_socket(None, expected=client_socket) is not None:
                self._set_status(
                    connected=False,
                    extension_ready=False,
                    last_event="client_disconnected",
                )
            self._close_socket(client_socket)

    def _handle_text_message(self, raw_text: str) -> None:
        """Update bridge status and resolve pending requests from one extension message."""

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            self._set_status(last_error=f"INVALID_JSON_FROM_EXTENSION: {exc}", last_event="invalid_json")
            return
        if not isinstance(payload, dict):
            self._set_status(last_error="INVALID_EXTENSION_PAYLOAD", last_event="invalid_payload")
            return
        message_type = str(payload.get("type", "") or "")
        request_id = str(payload.get("requestId", "") or "")
        with self._status_lock:
            last_result = copy.deepcopy(payload)
            visible_controls = self._status.visible_controls
            toggle_controls = self._status.toggle_controls
            if message_type == "ui_snapshot_result":
                # The local app wants typed, normalized control entries for debug UIs and logs, so
                # convert the extension payload as soon as it arrives.
                visible_controls = normalize_bridge_controls(
                    payload.get("result", {}).get("controls")
                    if isinstance(payload.get("result"), dict)
                    else None
                )
                toggle_controls = normalize_bridge_toggle_controls(
                    payload.get("result", {}).get("toggleControls")
                    if isinstance(payload.get("result"), dict)
                    else None
                )
            self._status = TenhouUiBridgeStatus(
                ws_url=self._status.ws_url,
                listening=self._status.listening,
                connected=self._status.connected,
                extension_ready=(message_type == "extension_ready") or self._status.extension_ready,
                last_error="",
                last_event=message_type or "message",
                last_sent_command=self._status.last_sent_command,
                last_result=last_result,
                visible_controls=visible_controls,
                toggle_controls=toggle_controls,
            )
        if message_type == "extension_ready":
            return
        if message_type == "pong" and not request_id:
            # `ping` replies are allowed to be minimal. When requestId is omitted, recover the most
            # recent pending ping so probe scripts still unblock cleanly.
            request_id = self._most_recent_pending_request_id("ping")
        if not request_id:
            return
        with self._pending_lock:
            pending_queue = self._pending_replies.pop(request_id, None)
        if pending_queue is not None:
            pending_queue.put(payload)

    def _most_recent_pending_request_id(self, command_type: str) -> str:
        """Best-effort fallback for payloads that did not echo `requestId`."""

        with self._status_lock, self._pending_lock:
            last_sent_command = dict(self._status.last_sent_command or {})
            if str(last_sent_command.get("type", "")) != str(command_type):
                return ""
            request_id = str(last_sent_command.get("requestId", "") or "")
            if request_id and request_id in self._pending_replies:
                return request_id
        return ""

    def _perform_websocket_handshake(self, client_socket: socket.socket) -> None:
        """Accept one RFC6455 opening handshake from Chrome."""

        header_bytes = bytearray()
        while b"\r\n\r\n" not in header_bytes:
            chunk = client_socket.recv(4096)
            if not chunk:
                raise ConnectionError("Incomplete WebSocket handshake.")
            header_bytes.extend(chunk)
            if len(header_bytes) > _MAX_HTTP_HEADER_BYTES:
                raise ConnectionError("WebSocket handshake header is too large.")
        header_text = header_bytes.decode("utf-8", errors="replace")
        headers: dict[str, str] = {}
        for raw_line in header_text.split("\r\n")[1:]:
            if not raw_line or ":" not in raw_line:
                continue
            key, value = raw_line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
        websocket_key = headers.get("sec-websocket-key", "")
        if not websocket_key:
            raise ConnectionError("Missing Sec-WebSocket-Key header.")
        accept_value = base64.b64encode(
            hashlib.sha1(f"{websocket_key}{_WEBSOCKET_GUID}".encode("utf-8")).digest()
        ).decode("ascii")
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_value}\r\n\r\n"
        )
        client_socket.sendall(response.encode("ascii"))

    def _send_text(self, text: str) -> None:
        """Send one text frame to the currently connected extension client."""

        client_socket = self._client_socket
        if client_socket is None:
            raise RuntimeError("TENHOU_UI_BRIDGE_EXTENSION_NOT_CONNECTED")
        self._send_frame(client_socket, _TEXT_OPCODE, text.encode("utf-8"))

    def _send_frame(self, client_socket: socket.socket, opcode: int, payload: bytes) -> None:
        """Write one non-fragmented server-to-client WebSocket frame."""

        with self._write_lock:
            # Server-to-client frames are not masked in RFC6455. We also keep them unfragmented
            # because bridge messages are tiny JSON payloads.
            header = bytearray([0x80 | (opcode & 0x0F)])
            payload_length = len(payload)
            if payload_length < 126:
                header.append(payload_length)
            elif payload_length <= 0xFFFF:
                header.extend((126, *struct.pack("!H", payload_length)))
            else:
                header.extend((127, *struct.pack("!Q", payload_length)))
            client_socket.sendall(bytes(header) + payload)

    def _read_frame(self, client_socket: socket.socket) -> tuple[int, bytes]:
        """Read one client-to-server WebSocket frame."""

        first_two = self._recv_exact(client_socket, 2)
        first_byte, second_byte = first_two[0], first_two[1]
        opcode = first_byte & 0x0F
        masked = bool(second_byte & 0x80)
        payload_length = second_byte & 0x7F
        if payload_length == 126:
            payload_length = struct.unpack("!H", self._recv_exact(client_socket, 2))[0]
        elif payload_length == 127:
            payload_length = struct.unpack("!Q", self._recv_exact(client_socket, 8))[0]
        masking_key = self._recv_exact(client_socket, 4) if masked else b""
        payload = self._recv_exact(client_socket, payload_length)
        if masked:
            # Browser clients must mask frames. Unmask here before JSON decoding or ping handling.
            payload = bytes(
                byte ^ masking_key[index % 4]
                for index, byte in enumerate(payload)
            )
        return opcode, payload

    @staticmethod
    def _recv_exact(client_socket: socket.socket, size: int) -> bytes:
        """Read exactly `size` bytes or raise when the peer disconnects."""

        chunks = bytearray()
        while len(chunks) < size:
            chunk = client_socket.recv(size - len(chunks))
            if not chunk:
                raise ConnectionError("WebSocket peer disconnected.")
            chunks.extend(chunk)
        return bytes(chunks)

    def _swap_client_socket(
        self,
        next_socket: socket.socket | None,
        *,
        expected: socket.socket | None = None,
    ) -> socket.socket | None:
        """Atomically replace the active client socket.

        `expected` is used by the reader thread so it does not clear a newer connection.
        """

        with self._write_lock:
            current_socket = self._client_socket
            if expected is not None and current_socket is not expected:
                return None
            self._client_socket = next_socket
            return current_socket

    def _set_status(self, **changes: Any) -> None:
        """Replace the public status snapshot while preserving unspecified fields."""

        with self._status_lock:
            current = self._status
            self._status = TenhouUiBridgeStatus(
                ws_url=str(changes.get("ws_url", current.ws_url)),
                listening=bool(changes.get("listening", current.listening)),
                connected=bool(changes.get("connected", current.connected)),
                extension_ready=bool(changes.get("extension_ready", current.extension_ready)),
                last_error=str(changes.get("last_error", current.last_error)),
                last_event=str(changes.get("last_event", current.last_event)),
                last_sent_command=copy.deepcopy(changes.get("last_sent_command", current.last_sent_command)),
                last_result=copy.deepcopy(changes.get("last_result", current.last_result)),
                visible_controls=tuple(changes.get("visible_controls", current.visible_controls)),
                toggle_controls=tuple(changes.get("toggle_controls", current.toggle_controls)),
            )

    @staticmethod
    def _close_socket(target_socket: socket.socket) -> None:
        """Best-effort socket shutdown helper."""

        try:
            target_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            target_socket.close()
        except OSError:
            pass
