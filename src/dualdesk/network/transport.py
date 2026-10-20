from __future__ import annotations

import enum
import socket
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from dualdesk.protocol.models import (
    ButtonPayload,
    ErrorCode,
    KeyPayload,
    MessageEnvelope,
    MessageType,
    PointerPayload,
    ProtocolError,
)
from dualdesk.security.input_filter import InputFilter
from dualdesk.security.pairing import PairingManager, PairingSession
from dualdesk.storage.db import DualDeskDB

DEFAULT_CONTROL_PORT = 53892
MAX_ENVELOPE_BYTES = 65536


class ConnectionState(str, enum.Enum):
    NOT_CONNECTED = "Not connected"
    PAIRING = "Pairing"
    CONNECTING = "Connecting"
    STREAMING = "Streaming"
    RECOVERING = "Recovering"
    ERROR = "Error"
    DISCONNECTED = "Disconnected"


@dataclass
class SessionTelemetry:
    fps: float = 0.0
    latency_ms: float = 0.0
    bitrate_kbps: float = 0.0
    dropped_frames: int = 0


def _send_envelope(sock: socket.socket, envelope: MessageEnvelope) -> None:
    data = (envelope.serialize() + "\n").encode("utf-8")
    sock.sendall(data)


def _recv_envelope(sock: socket.socket, timeout: float = 5.0) -> MessageEnvelope | None:
    sock.settimeout(timeout)
    buffer = bytearray()
    while True:
        chunk = sock.recv(1024)
        if not chunk:
            break
        buffer.extend(chunk)
        if b"\n" in buffer or len(buffer) > MAX_ENVELOPE_BYTES:
            break
    if not buffer:
        return None
    line = buffer.split(b"\n")[0].decode("utf-8").strip()
    if not line:
        return None
    return MessageEnvelope.deserialize(line)


class ConnectionManager:
    """
    Manages peer-to-peer session state machine, authentication checks,
    TCP control channel, message framing, input forwarding, telemetry, and graceful disconnect release.
    """

    RECONNECT_MAX_ATTEMPTS = 5
    INITIAL_BACKOFF_SECONDS = 1.0

    def __init__(
        self,
        db: DualDeskDB,
        pairing_manager: PairingManager,
        role: str = "host",
        control_port: int = DEFAULT_CONTROL_PORT,
        on_state_changed: Callable[[ConnectionState, str], None] | None = None,
        on_telemetry_updated: Callable[[SessionTelemetry], None] | None = None,
    ) -> None:
        self.db = db
        self.pairing_manager = pairing_manager
        self.role = role
        self.control_port = control_port
        self.on_state_changed = on_state_changed
        self.on_telemetry_updated = on_telemetry_updated

        self.state = ConnectionState.NOT_CONNECTED
        self.active_session_id: str | None = None
        self.peer_device_id: str | None = None
        self.peer_fingerprint: str | None = None
        self.peer_address: str | None = None
        self.error_message: str = ""

        self.input_filter: InputFilter | None = None
        self.telemetry = SessionTelemetry()
        self._history_id: int | None = None
        self._sequence_counter = 0
        self._lock = threading.Lock()

        # Network control sockets and background threads
        self._server_sock: socket.socket | None = None
        self._server_thread: threading.Thread | None = None
        self._server_running = False
        self._active_client_sock: socket.socket | None = None
        self._client_sock: socket.socket | None = None
        self._client_reader_thread: threading.Thread | None = None

    def set_state(self, state: ConnectionState, detail: str = "") -> None:
        self.state = state
        self.error_message = detail if state == ConnectionState.ERROR else ""
        if self.on_state_changed:
            self.on_state_changed(state, detail)

    def start_pairing(
        self, peer_device_id: str, peer_name: str, peer_fingerprint: str
    ) -> PairingSession:
        """Initiates pairing by creating a secure challenge and returning the PairingSession."""
        self.set_state(ConnectionState.PAIRING, "Awaiting user confirmation of pairing code")
        return self.pairing_manager.create_challenge(
            peer_device_id=peer_device_id,
            peer_name=peer_name,
            peer_fingerprint=peer_fingerprint,
        )

    def confirm_pairing(self, challenge_id: str, code: str, peer_fingerprint: str) -> bool:
        """Verifies pairing code."""
        try:
            success = self.pairing_manager.verify_code(challenge_id, code, peer_fingerprint)
            if success:
                self.set_state(ConnectionState.NOT_CONNECTED, "Device successfully paired")
            return success
        except ProtocolError as e:
            self.set_state(ConnectionState.ERROR, e.message)
            raise

    # Host Control Server Lifecycle
    def start_control_server(self, host: str = "", port: int | None = None) -> None:
        """Starts the TCP control server on the host machine."""
        if self._server_running:
            return

        port = port or self.control_port
        self.control_port = port

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            sock.listen(5)
        except OSError as e:
            self.set_state(ConnectionState.ERROR, f"Control server bind failed on port {port}: {e}")
            return

        self._server_sock = sock
        self._server_running = True
        self._server_thread = threading.Thread(
            target=self._control_server_loop, daemon=True, name="ControlServer"
        )
        self._server_thread.start()

    def stop_control_server(self) -> None:
        """Stops the TCP control server and cleans up active connections."""
        self._server_running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None

    def _control_server_loop(self) -> None:
        if self._server_sock:
            self._server_sock.settimeout(1.0)

        while self._server_running and self._server_sock:
            try:
                client_sock, client_addr = self._server_sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break

            t = threading.Thread(
                target=self._handle_client_connection,
                args=(client_sock, client_addr),
                daemon=True,
                name=f"ControlClient-{client_addr[0]}",
            )
            t.start()

    def _handle_client_connection(
        self, client_sock: socket.socket, client_addr: tuple[str, int]
    ) -> None:
        client_sock.settimeout(60.0)
        buffer = bytearray()
        try:
            while self._server_running:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > MAX_ENVELOPE_BYTES:
                    break

                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    line = line_bytes.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        env = MessageEnvelope.deserialize(line)
                    except ProtocolError as pe:
                        err_env = MessageEnvelope(
                            type=MessageType.SESSION_ERROR.value,
                            payload={"code": pe.code.value, "message": pe.message},
                        )
                        _send_envelope(client_sock, err_env)
                        continue

                    self._dispatch_server_message(env, client_sock, client_addr)
        except OSError:
            pass
        finally:
            try:
                client_sock.close()
            except OSError:
                pass
            if client_sock == self._active_client_sock:
                self._active_client_sock = None
                if self.state == ConnectionState.STREAMING:
                    self.disconnect(reason="Client disconnected")

    def _dispatch_server_message(
        self, env: MessageEnvelope, sock: socket.socket, addr: tuple[str, int]
    ) -> None:
        msg_type = env.type

        if msg_type == MessageType.PAIRING_REQUEST.value:
            peer_id = env.payload.get("client_device_id", "")
            peer_name = env.payload.get("client_name", "Remote Client")
            peer_fp = env.payload.get("client_fingerprint", "")
            challenge = self.start_pairing(peer_id, peer_name, peer_fp)
            resp = MessageEnvelope(
                type=MessageType.PAIRING_CHALLENGE.value,
                session_id=challenge.challenge_id,
                payload={
                    "challenge_id": challenge.challenge_id,
                    "code": challenge.code,
                    "expires_at": challenge.expires_at,
                    "host_fingerprint": self.pairing_manager.local_fingerprint,
                },
            )
            _send_envelope(sock, resp)

        elif msg_type == MessageType.PAIRING_CONFIRM.value:
            cid = env.payload.get("challenge_id", "")
            code = env.payload.get("code", "")
            peer_fp = env.payload.get("client_fingerprint", "")
            try:
                ok = self.confirm_pairing(cid, code, peer_fp)
                if ok:
                    resp = MessageEnvelope(
                        type=MessageType.PAIRING_CONFIRM.value,
                        session_id=cid,
                        payload={
                            "status": "confirmed",
                            "host_fingerprint": self.pairing_manager.local_fingerprint,
                        },
                    )
                else:
                    resp = MessageEnvelope(
                        type=MessageType.PAIRING_REJECT.value,
                        session_id=cid,
                        payload={"challenge_id": cid, "reason": "Verification failed"},
                    )
            except ProtocolError as pe:
                resp = MessageEnvelope(
                    type=MessageType.PAIRING_REJECT.value,
                    session_id=cid,
                    payload={"challenge_id": cid, "reason": pe.message},
                )
            _send_envelope(sock, resp)

        elif msg_type == MessageType.SESSION_START.value:
            client_id = env.payload.get("client_device_id", "")
            client_fp = env.payload.get("client_fingerprint", "")
            width = int(env.payload.get("preferred_width", 1920))
            height = int(env.payload.get("preferred_height", 1080))
            success = self.connect(
                peer_device_id=client_id,
                peer_fingerprint=client_fp,
                peer_address=addr[0],
                display_width=width,
                display_height=height,
            )
            if success:
                self._active_client_sock = sock
                resp = MessageEnvelope(
                    type=MessageType.SESSION_ACCEPT.value,
                    session_id=self.active_session_id or "",
                    payload={
                        "session_id": self.active_session_id,
                        "assigned_width": width,
                        "assigned_height": height,
                        "assigned_fps": 60,
                        "media_port": 53893,
                        "is_virtual_display": False,
                    },
                )
            else:
                resp = MessageEnvelope(
                    type=MessageType.SESSION_ERROR.value,
                    payload={
                        "code": ErrorCode.PAIRING_REQUIRED.value,
                        "message": self.error_message or "Device not paired",
                    },
                )
            _send_envelope(sock, resp)

        elif msg_type == MessageType.INPUT_POINTER.value:
            payload = PointerPayload(
                x=float(env.payload["x"]),
                y=float(env.payload["y"]),
                normalized=bool(env.payload.get("normalized", False)),
            )
            self.handle_incoming_pointer(payload, env.sequence)

        elif msg_type == MessageType.INPUT_BUTTON.value:
            btn_payload = ButtonPayload(
                button=str(env.payload["button"]),
                pressed=bool(env.payload["pressed"]),
            )
            self.handle_incoming_button(btn_payload, env.sequence)

        elif msg_type == MessageType.INPUT_KEY.value:
            key_payload = KeyPayload(
                key_code=int(env.payload["key_code"]),
                key_name=str(env.payload["key_name"]),
                pressed=bool(env.payload["pressed"]),
            )
            self.handle_incoming_key(key_payload, env.sequence)

        elif msg_type == MessageType.INPUT_RELEASE_ALL.value:
            if self.input_filter:
                self.input_filter.release_all()

        elif msg_type == MessageType.SESSION_STOP.value:
            self.disconnect(reason="Remote peer disconnected")

    # Client-Side Network Helpers
    def pair_with_host(
        self,
        host_address: str,
        port: int,
        client_device_id: str,
        client_name: str,
        client_fingerprint: str,
        code: str | None = None,
    ) -> bool:
        """
        Connects to a remote host, requests a pairing challenge, and verifies the 6-digit PIN.
        On success, persists the host in the local client database.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((host_address, port))
            req = MessageEnvelope(
                type=MessageType.PAIRING_REQUEST.value,
                payload={
                    "client_device_id": client_device_id,
                    "client_name": client_name,
                    "client_fingerprint": client_fingerprint,
                },
            )
            _send_envelope(sock, req)

            resp = _recv_envelope(sock, timeout=5.0)
            if not resp or resp.type != MessageType.PAIRING_CHALLENGE.value:
                return False

            cid = resp.payload.get("challenge_id", "")
            submitted_code = code or resp.payload.get("code", "")
            host_fp = resp.payload.get("host_fingerprint", "")

            confirm = MessageEnvelope(
                type=MessageType.PAIRING_CONFIRM.value,
                session_id=cid,
                payload={
                    "challenge_id": cid,
                    "code": submitted_code,
                    "client_fingerprint": client_fingerprint,
                },
            )
            _send_envelope(sock, confirm)

            result = _recv_envelope(sock, timeout=5.0)
            if result and result.type == MessageType.PAIRING_CONFIRM.value:
                self.db.upsert_device(
                    device_id=f"host-{host_address}",
                    display_name=f"Host ({host_address})",
                    platform="Windows",
                    trust_status="paired",
                    public_key_fingerprint=host_fp,
                )
                return True
            return False
        except OSError:
            return False
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def connect_to_host(
        self,
        host_address: str,
        port: int,
        client_device_id: str,
        client_fingerprint: str,
        display_width: int = 1920,
        display_height: int = 1080,
    ) -> bool:
        """
        Connects client to host over TCP control channel and establishes an active streaming session.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((host_address, port))
            start_env = MessageEnvelope(
                type=MessageType.SESSION_START.value,
                payload={
                    "client_device_id": client_device_id,
                    "client_fingerprint": client_fingerprint,
                    "preferred_width": display_width,
                    "preferred_height": display_height,
                },
            )
            _send_envelope(sock, start_env)

            resp = _recv_envelope(sock, timeout=5.0)
            if resp and resp.type == MessageType.SESSION_ACCEPT.value:
                self._client_sock = sock
                self.active_session_id = resp.session_id or resp.payload.get("session_id")
                self.set_state(ConnectionState.STREAMING, "Session active")
                self._sequence_counter = 0

                self._client_reader_thread = threading.Thread(
                    target=self._client_socket_reader, daemon=True, name="ClientControlReader"
                )
                self._client_reader_thread.start()
                return True
            else:
                msg = resp.payload.get("message", "Session rejected") if resp else "No response"
                self.set_state(ConnectionState.ERROR, msg)
                return False
        except OSError as e:
            self.set_state(ConnectionState.ERROR, f"Failed to connect to host: {e}")
            try:
                sock.close()
            except OSError:
                pass
            return False

    def _client_socket_reader(self) -> None:
        if not self._client_sock:
            return
        buffer = bytearray()
        try:
            while self.state == ConnectionState.STREAMING and self._client_sock:
                chunk = self._client_sock.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    line = line_bytes.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        env = MessageEnvelope.deserialize(line)
                        if env.type == MessageType.SESSION_STOP.value:
                            self.disconnect(reason="Host disconnected")
                            return
                    except ProtocolError:
                        continue
        except OSError:
            pass
        finally:
            if self.state == ConnectionState.STREAMING:
                self.disconnect(reason="Host connection lost")

    def send_pointer(self, x: float, y: float, normalized: bool = False) -> None:
        """Sends pointer coordinates to the host."""
        if not self._client_sock or self.state != ConnectionState.STREAMING:
            return
        self._sequence_counter += 1
        env = MessageEnvelope(
            type=MessageType.INPUT_POINTER.value,
            session_id=self.active_session_id or "",
            sequence=self._sequence_counter,
            payload={"x": x, "y": y, "normalized": normalized},
        )
        try:
            _send_envelope(self._client_sock, env)
        except OSError:
            self.disconnect(reason="Send failed")

    def send_button(self, button: str, pressed: bool) -> None:
        """Sends button state to the host."""
        if not self._client_sock or self.state != ConnectionState.STREAMING:
            return
        self._sequence_counter += 1
        env = MessageEnvelope(
            type=MessageType.INPUT_BUTTON.value,
            session_id=self.active_session_id or "",
            sequence=self._sequence_counter,
            payload={"button": button, "pressed": pressed},
        )
        try:
            _send_envelope(self._client_sock, env)
        except OSError:
            self.disconnect(reason="Send failed")

    def send_key(self, key_code: int, key_name: str, pressed: bool) -> None:
        """Sends key state to the host."""
        if not self._client_sock or self.state != ConnectionState.STREAMING:
            return
        self._sequence_counter += 1
        env = MessageEnvelope(
            type=MessageType.INPUT_KEY.value,
            session_id=self.active_session_id or "",
            sequence=self._sequence_counter,
            payload={"key_code": key_code, "key_name": key_name, "pressed": pressed},
        )
        try:
            _send_envelope(self._client_sock, env)
        except OSError:
            self.disconnect(reason="Send failed")

    def send_release_all(self, reason: str = "client_reset") -> None:
        """Sends release-all command to the host."""
        if not self._client_sock or self.state != ConnectionState.STREAMING:
            return
        self._sequence_counter += 1
        env = MessageEnvelope(
            type=MessageType.INPUT_RELEASE_ALL.value,
            session_id=self.active_session_id or "",
            sequence=self._sequence_counter,
            payload={"reason": reason},
        )
        try:
            _send_envelope(self._client_sock, env)
        except OSError:
            pass

    # Session Management
    def connect(
        self,
        peer_device_id: str,
        peer_fingerprint: str,
        peer_address: str,
        display_width: int = 1920,
        display_height: int = 1080,
    ) -> bool:
        """
        Connects to a paired peer.
        Enforces that unauthenticated or revoked peers are rejected.
        """
        with self._lock:
            # Security verification
            if not self.pairing_manager.is_peer_paired(peer_device_id, peer_fingerprint):
                self.set_state(
                    ConnectionState.ERROR,
                    "Security check failed: Peer is not paired or has invalid fingerprint",
                )
                self.db.log_diagnostic_event(
                    level="ERROR",
                    component="transport",
                    event_code="UNPAIRED_CONNECT_ATTEMPT",
                    message_redacted=f"Rejected unauthenticated connection from device {peer_device_id[:8]}",
                )
                return False

            self.peer_device_id = peer_device_id
            self.peer_fingerprint = peer_fingerprint
            self.peer_address = peer_address
            self.set_state(ConnectionState.CONNECTING, f"Establishing session with {peer_address}...")

            # Generate session
            session_id = str(uuid.uuid4())
            self.active_session_id = session_id
            self.input_filter = InputFilter(
                session_id=session_id,
                display_width=display_width,
                display_height=display_height,
            )
            self._sequence_counter = 0

            # Record in connection history
            self._history_id = self.db.record_connection_start(peer_device_id)

            # Transition to streaming
            self.set_state(ConnectionState.STREAMING, "Session active")
            self.db.log_diagnostic_event(
                level="INFO",
                component="transport",
                event_code="SESSION_CONNECTED",
                message_redacted=f"Session established with peer {peer_device_id[:8]}",
                correlation_id=session_id,
            )
            return True

    def disconnect(self, reason: str = "User disconnect") -> None:
        """
        Gracefully tears down active session.
        MANDATORY SECURITY ACTION: releases any held inputs immediately.
        """
        with self._lock:
            if self._client_sock:
                try:
                    stop_env = MessageEnvelope(
                        type=MessageType.SESSION_STOP.value,
                        session_id=self.active_session_id or "",
                        payload={"reason": reason},
                    )
                    _send_envelope(self._client_sock, stop_env)
                    self._client_sock.close()
                except OSError:
                    pass
                self._client_sock = None

            if self._active_client_sock:
                try:
                    stop_env = MessageEnvelope(
                        type=MessageType.SESSION_STOP.value,
                        session_id=self.active_session_id or "",
                        payload={"reason": reason},
                    )
                    _send_envelope(self._active_client_sock, stop_env)
                    self._active_client_sock.close()
                except OSError:
                    pass
                self._active_client_sock = None

            if self.input_filter:
                release_info = self.input_filter.release_all()
                if release_info["released_keys"] or release_info["released_buttons"]:
                    self.db.log_diagnostic_event(
                        level="INFO",
                        component="input",
                        event_code="INPUT_RELEASE_ALL",
                        message_redacted="Released all held keys and mouse buttons upon session disconnect",
                    )
                self.input_filter = None

            if self._history_id:
                self.db.record_connection_end(
                    history_id=self._history_id,
                    result="completed" if reason == "User disconnect" else "interrupted",
                    failure_code=None if reason == "User disconnect" else reason,
                    avg_fps=self.telemetry.fps,
                    avg_latency_ms=self.telemetry.latency_ms,
                )
                self._history_id = None

            self.active_session_id = None
            self.peer_device_id = None
            self.peer_fingerprint = None
            self.set_state(ConnectionState.DISCONNECTED, reason)

    def handle_incoming_pointer(
        self, payload: PointerPayload, sequence: int
    ) -> tuple[float, float] | None:
        """Handles incoming pointer with authentication, sequence check, and coordinate clamping."""
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        return self.input_filter.process_pointer(payload, sequence)

    def handle_incoming_button(
        self, payload: ButtonPayload, sequence: int
    ) -> tuple[str, bool] | None:
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        return self.input_filter.process_button(payload, sequence)

    def handle_incoming_key(
        self, payload: KeyPayload, sequence: int
    ) -> tuple[int, str, bool] | None:
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        res = self.input_filter.process_key(payload, sequence)
        if self.input_filter.emergency_escape_triggered:
            self.disconnect(reason="Emergency escape shortcut triggered")
        return res

    def update_telemetry(
        self, fps: float, latency_ms: float, bitrate_kbps: float, dropped_frames: int
    ) -> None:
        self.telemetry.fps = fps
        self.telemetry.latency_ms = latency_ms
        self.telemetry.bitrate_kbps = bitrate_kbps
        self.telemetry.dropped_frames = dropped_frames
        if self.on_telemetry_updated:
            self.on_telemetry_updated(self.telemetry)
