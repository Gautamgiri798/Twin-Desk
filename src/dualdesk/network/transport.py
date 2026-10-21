from __future__ import annotations

import enum
import socket
import ssl
import struct
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dualdesk.audio.capture import AudioCaptureAdapter, AudioFrame, AudioPlayerAdapter
from dualdesk.display.adaptive import AdaptiveRateController
from dualdesk.display.clipboard import ClipboardAdapter
from dualdesk.display.driver import get_supported_modes, negotiate_target_mode
from dualdesk.display.input_injector import InputInjector
from dualdesk.protocol.models import (
    AudioFramePayload,
    ButtonPayload,
    ClipboardUpdatePayload,
    DisplayMode,
    ErrorCode,
    GesturePayload,
    KeyPayload,
    MessageEnvelope,
    MessageType,
    PointerPayload,
    ProtocolError,
    TouchPayload,
    TouchPoint,
)
from dualdesk.security.clipboard_guard import ClipboardGuard
from dualdesk.security.input_filter import InputFilter
from dualdesk.security.pairing import PairingManager, PairingSession
from dualdesk.security.tls import (
    create_tls_client_context,
    create_tls_server_context,
    verify_peer_certificate,
)
from dualdesk.storage.db import DualDeskDB

DEFAULT_CONTROL_PORT = 53892
DEFAULT_MEDIA_PORT = 53893
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
    TCP control channel, media streaming, host input injection, input forwarding,
    telemetry, and graceful disconnect release.
    """

    RECONNECT_MAX_ATTEMPTS = 5
    INITIAL_BACKOFF_SECONDS = 1.0

    def __init__(
        self,
        db: DualDeskDB,
        pairing_manager: PairingManager,
        role: str = "host",
        control_port: int = DEFAULT_CONTROL_PORT,
        media_port: int = DEFAULT_MEDIA_PORT,
        enable_input_injection: bool = True,
        enable_tls: bool = False,
        tls_cert_path: Path | None = None,
        tls_key_path: Path | None = None,
        tls_expected_fingerprint: str | None = None,
        adaptive_controller: AdaptiveRateController | None = None,
        audio_capture: AudioCaptureAdapter | None = None,
        audio_player: AudioPlayerAdapter | None = None,
        clipboard_guard: ClipboardGuard | None = None,
        clipboard_adapter: ClipboardAdapter | None = None,
        on_state_changed: Callable[[ConnectionState, str], None] | None = None,
        on_telemetry_updated: Callable[[SessionTelemetry], None] | None = None,
        on_frame_received: Callable[[bytes], None] | None = None,
        on_frame_sent: Callable[[float, int], None] | None = None,
        on_audio_received: Callable[[AudioFrame], None] | None = None,
        on_clipboard_received: Callable[[str], None] | None = None,
        on_display_mode_changed: Callable[[int, int, int], None] | None = None,
        on_display_mode_negotiated: Callable[[int, int, int], None] | None = None,
    ) -> None:
        self.db = db
        self.pairing_manager = pairing_manager
        self.role = role
        self.control_port = control_port
        self.media_port = media_port
        self.enable_input_injection = enable_input_injection
        self.enable_tls = enable_tls
        self.tls_cert_path = tls_cert_path
        self.tls_key_path = tls_key_path
        self.tls_expected_fingerprint = tls_expected_fingerprint
        self.adaptive_controller = adaptive_controller
        self.audio_capture = audio_capture
        self.audio_player = audio_player
        self.clipboard_guard = clipboard_guard or ClipboardGuard(enabled=True)
        self.clipboard_adapter = clipboard_adapter or ClipboardAdapter()
        self.clipboard_adapter.on_change = self._on_local_clipboard_changed
        self.on_state_changed = on_state_changed
        self.on_telemetry_updated = on_telemetry_updated
        self.on_frame_received = on_frame_received
        self.on_frame_sent = on_frame_sent
        self.on_audio_received = on_audio_received
        self.on_clipboard_received = on_clipboard_received
        self.on_display_mode_changed = on_display_mode_changed
        self.on_display_mode_negotiated = on_display_mode_negotiated
        self.current_display_mode = DisplayMode(1920, 1080, 60)

        self.last_send_latency_ms: float = 0.0
        self._tls_server_context: ssl.SSLContext | None = None
        self._tls_client_context: ssl.SSLContext | None = None

        self.state = ConnectionState.NOT_CONNECTED
        self.active_session_id: str | None = None
        self.peer_device_id: str | None = None
        self.peer_fingerprint: str | None = None
        self.peer_address: str | None = None
        self.error_message: str = ""

        self.input_filter: InputFilter | None = None
        self.input_injector: InputInjector | None = (
            InputInjector(enabled=enable_input_injection) if role == "host" else None
        )
        self.telemetry = SessionTelemetry()
        self._history_id: int | None = None
        self._sequence_counter = 0
        self._lock = threading.Lock()

        # Network control sockets and threads
        self._server_sock: socket.socket | None = None
        self._server_thread: threading.Thread | None = None
        self._server_running = False
        self._active_client_sock: socket.socket | None = None
        self._client_sock: socket.socket | None = None
        self._client_reader_thread: threading.Thread | None = None

        # Network media streaming sockets and threads
        self._media_server_sock: socket.socket | None = None
        self._media_server_thread: threading.Thread | None = None
        self._media_client_sock: socket.socket | None = None
        self._media_receiver_thread: threading.Thread | None = None

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
        """Starts the TCP control server and media server on the host machine."""
        if self._server_running:
            return

        port = port or self.control_port
        self.control_port = port

        if self.enable_tls and self.tls_cert_path and self.tls_key_path:
            self._tls_server_context = create_tls_server_context(
                self.tls_cert_path, self.tls_key_path
            )

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

        self.start_media_server(host=host, port=self.media_port)

    def stop_control_server(self) -> None:
        """Stops the TCP control server and media server."""
        self._server_running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None

        self.stop_media_server()

    def _control_server_loop(self) -> None:
        if self._server_sock:
            self._server_sock.settimeout(1.0)

        while self._server_running and self._server_sock:
            try:
                client_sock, client_addr = self._server_sock.accept()
                if self._tls_server_context:
                    client_sock = self._tls_server_context.wrap_socket(
                        client_sock, server_side=True
                    )
            except TimeoutError:
                continue
            except (ssl.SSLError, OSError):
                continue

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
                        "media_port": self.media_port,
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

        elif msg_type == MessageType.DISPLAY_MODE_REQUEST.value:
            req_w = int(env.payload.get("width", 1920))
            req_h = int(env.payload.get("height", 1080))
            req_fps = int(env.payload.get("refresh_rate", 60))

            if req_w < 320 or req_h < 180 or req_w > 7680 or req_h > 4320:
                reject_env = MessageEnvelope(
                    type=MessageType.DISPLAY_MODE_REJECT.value,
                    session_id=self.active_session_id or "",
                    sequence=self._sequence_counter,
                    payload={
                        "reason": f"Resolution {req_w}x{req_h} out of supported bounds",
                        "supported_modes": [asdict(m) for m in get_supported_modes()],
                    },
                )
                _send_envelope(sock, reject_env)
            else:
                mode = negotiate_target_mode(req_w, req_h, req_fps)
                self.current_display_mode = mode
                if self.input_injector:
                    self.input_injector.display_width = mode.width
                    self.input_injector.display_height = mode.height
                if self.on_display_mode_changed:
                    self.on_display_mode_changed(mode.width, mode.height, mode.refresh_rate)

                accept_env = MessageEnvelope(
                    type=MessageType.DISPLAY_MODE_ACCEPT.value,
                    session_id=self.active_session_id or "",
                    sequence=self._sequence_counter,
                    payload={
                        "width": mode.width,
                        "height": mode.height,
                        "refresh_rate": mode.refresh_rate,
                        "mode_name": mode.name,
                    },
                )
                _send_envelope(sock, accept_env)

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
                release_info = self.input_filter.release_all()
                if self.input_injector:
                    self.input_injector.release_all(
                        keys=release_info.get("released_keys"),
                        buttons=release_info.get("released_buttons"),
                        touches=release_info.get("released_touches"),
                    )

        elif msg_type == MessageType.INPUT_TOUCH.value:
            contacts_raw = env.payload.get("contacts", [])
            contacts = [
                TouchPoint(
                    id=int(c.get("id", 0)),
                    x=float(c.get("x", 0.0)),
                    y=float(c.get("y", 0.0)),
                    pressure=float(c.get("pressure", 1.0)),
                    normalized=bool(c.get("normalized", True)),
                )
                for c in contacts_raw
            ]
            touch_payload = TouchPayload(
                action=str(env.payload.get("action", "move")),
                contacts=contacts,
            )
            self.handle_incoming_touch(touch_payload, env.sequence)

        elif msg_type == MessageType.INPUT_GESTURE.value:
            gesture_payload = GesturePayload(
                gesture=str(env.payload.get("gesture", "pan")),
                x=float(env.payload.get("x", 0.0)),
                y=float(env.payload.get("y", 0.0)),
                delta_x=float(env.payload.get("delta_x", 0.0)),
                delta_y=float(env.payload.get("delta_y", 0.0)),
                scale=float(env.payload.get("scale", 1.0)),
                normalized=bool(env.payload.get("normalized", True)),
            )
            self.handle_incoming_gesture(gesture_payload, env.sequence)

        elif msg_type == MessageType.AUDIO_FRAME.value:
            self._handle_incoming_audio(env)

        elif msg_type == MessageType.CLIPBOARD_UPDATE.value:
            clip_payload = ClipboardUpdatePayload(
                text=str(env.payload.get("text", "")),
                format=str(env.payload.get("format", "text/plain")),
                sender_device_id=str(env.payload.get("sender_device_id", "")),
                timestamp_us=int(env.payload.get("timestamp_us", 0)),
            )
            self.handle_incoming_clipboard(clip_payload)

        elif msg_type == MessageType.SESSION_STOP.value:
            self.disconnect(reason="Remote peer disconnected")

    def _handle_incoming_audio(self, env: MessageEnvelope) -> None:
        try:
            payload = AudioFramePayload(
                sequence=int(env.payload.get("sequence", 0)),
                timestamp_us=int(env.payload.get("timestamp_us", 0)),
                data_b64=str(env.payload.get("data_b64", "")),
                sample_rate=int(env.payload.get("sample_rate", 48000)),
                channels=int(env.payload.get("channels", 2)),
                rms_volume=float(env.payload.get("rms_volume", 0.0)),
            )
            frame = AudioFrame.from_payload(payload)
            if self.audio_player:
                self.audio_player.enqueue_frame(frame)
            if self.on_audio_received:
                self.on_audio_received(frame)
        except (ValueError, KeyError):
            pass

    def broadcast_audio_frame(self, frame: AudioFrame) -> bool:
        """Streams an audio frame to the connected peer over the control channel."""
        sock = self._active_client_sock or self._client_sock
        if not sock:
            return False
        env = MessageEnvelope(
            type=MessageType.AUDIO_FRAME.value,
            session_id=self.active_session_id or "",
            sequence=frame.sequence,
            payload=asdict(frame.to_payload()),
        )
        try:
            _send_envelope(sock, env)
            return True
        except OSError:
            return False

    def broadcast_display_mode(self, mode: DisplayMode) -> bool:
        """Broadcasts active display mode to the connected peer over the control channel."""
        sock = self._active_client_sock or self._client_sock
        if not sock or self.state != ConnectionState.STREAMING:
            return False
        self._sequence_counter += 1
        env = MessageEnvelope(
            type=MessageType.DISPLAY_MODE_ACCEPT.value,
            session_id=self.active_session_id or "",
            sequence=self._sequence_counter,
            payload={
                "width": mode.width,
                "height": mode.height,
                "refresh_rate": mode.refresh_rate,
                "mode_name": mode.name,
            },
        )
        try:
            _send_envelope(sock, env)
            return True
        except OSError:
            return False

    # Host Media Streaming Server
    def start_media_server(self, host: str = "", port: int = DEFAULT_MEDIA_PORT) -> None:
        """Starts media streaming server on host to stream video frames."""
        self.media_port = port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            sock.listen(2)
        except OSError:
            return

        self._media_server_sock = sock
        self._media_server_thread = threading.Thread(
            target=self._media_server_loop, daemon=True, name="MediaServer"
        )
        self._media_server_thread.start()

    def stop_media_server(self) -> None:
        """Stops media streaming server."""
        if self._media_server_sock:
            try:
                self._media_server_sock.close()
            except OSError:
                pass
            self._media_server_sock = None
        if self._media_client_sock:
            try:
                self._media_client_sock.close()
            except OSError:
                pass
            self._media_client_sock = None

    def _media_server_loop(self) -> None:
        if self._media_server_sock:
            self._media_server_sock.settimeout(1.0)
        while self._server_running and self._media_server_sock:
            try:
                client, _ = self._media_server_sock.accept()
                if self._tls_server_context:
                    client = self._tls_server_context.wrap_socket(client, server_side=True)
                self._media_client_sock = client
            except TimeoutError:
                continue
            except (ssl.SSLError, OSError):
                continue

    def broadcast_frame(self, frame_bytes: bytes) -> bool:
        """Streams a single frame to the connected client over the media channel."""
        if not self._media_client_sock or not frame_bytes:
            return False
        header = struct.pack(">I", len(frame_bytes))
        send_start = time.perf_counter()
        try:
            self._media_client_sock.sendall(header + frame_bytes)
            send_duration_ms = (time.perf_counter() - send_start) * 1000.0
            self.last_send_latency_ms = send_duration_ms
            if self.adaptive_controller:
                self.adaptive_controller.record_send_latency(send_duration_ms, len(frame_bytes))
            if self.on_frame_sent:
                self.on_frame_sent(send_duration_ms, len(frame_bytes))
            return True
        except OSError:
            try:
                self._media_client_sock.close()
            except OSError:
                pass
            self._media_client_sock = None
            return False

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
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((host_address, port))
            if self.enable_tls:
                if not self._tls_client_context:
                    self._tls_client_context = create_tls_client_context()
                sock = self._tls_client_context.wrap_socket(
                    sock, server_hostname="dualdesk.local"
                )

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
        except (ssl.SSLError, OSError):
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
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((host_address, port))
            if self.enable_tls:
                if not self._tls_client_context:
                    self._tls_client_context = create_tls_client_context()
                sock = self._tls_client_context.wrap_socket(
                    sock, server_hostname="dualdesk.local"
                )
                if self.tls_expected_fingerprint and not verify_peer_certificate(
                    sock, self.tls_expected_fingerprint
                ):
                    self.set_state(
                        ConnectionState.ERROR, "TLS peer certificate fingerprint mismatch"
                    )
                    sock.close()
                    return False

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
                media_port = resp.payload.get("media_port", self.media_port)
                self.set_state(ConnectionState.STREAMING, "Session active")
                self._sequence_counter = 0

                self._client_reader_thread = threading.Thread(
                    target=self._client_socket_reader, daemon=True, name="ClientControlReader"
                )
                self._client_reader_thread.start()

                # Start media receiver
                self.start_media_receiver(host_address, media_port)
                return True
            else:
                msg = resp.payload.get("message", "Session rejected") if resp else "No response"
                self.set_state(ConnectionState.ERROR, msg)
                return False
        except (ssl.SSLError, OSError) as e:
            self.set_state(ConnectionState.ERROR, f"Failed to connect to host: {e}")
            try:
                sock.close()
            except OSError:
                pass
            return False

    def start_media_receiver(self, host_address: str, port: int) -> None:
        """Connects to host's media port and receives incoming video frames."""
        self._media_receiver_thread = threading.Thread(
            target=self._media_receiver_loop,
            args=(host_address, port),
            daemon=True,
            name="MediaReceiver",
        )
        self._media_receiver_thread.start()

    def _media_receiver_loop(self, host_address: str, port: int) -> None:
        media_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        media_sock.settimeout(5.0)
        try:
            media_sock.connect((host_address, port))
            if self.enable_tls:
                if not self._tls_client_context:
                    self._tls_client_context = create_tls_client_context()
                media_sock = self._tls_client_context.wrap_socket(
                    media_sock, server_hostname="dualdesk.local"
                )
            self._media_client_sock = media_sock
            while self.state == ConnectionState.STREAMING:
                # Read 4-byte length prefix
                header = media_sock.recv(4)
                if not header or len(header) < 4:
                    break
                (frame_len,) = struct.unpack(">I", header)
                if frame_len <= 0 or frame_len > 10 * 1024 * 1024:
                    break

                # Read frame payload
                frame_buf = bytearray()
                while len(frame_buf) < frame_len:
                    chunk = media_sock.recv(min(8192, frame_len - len(frame_buf)))
                    if not chunk:
                        break
                    frame_buf.extend(chunk)

                if len(frame_buf) == frame_len and self.on_frame_received:
                    self.on_frame_received(bytes(frame_buf))
        except OSError:
            pass
        finally:
            try:
                media_sock.close()
            except OSError:
                pass
            if self._media_client_sock == media_sock:
                self._media_client_sock = None

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
                        elif env.type == MessageType.AUDIO_FRAME.value:
                            self._handle_incoming_audio(env)
                        elif env.type == MessageType.DISPLAY_MODE_ACCEPT.value:
                            w = int(env.payload.get("width", 1920))
                            h = int(env.payload.get("height", 1080))
                            fps = int(env.payload.get("refresh_rate", 60))
                            name = str(env.payload.get("mode_name", f"{w}x{h} @ {fps}Hz"))
                            self.current_display_mode = DisplayMode(w, h, fps, name)
                            if self.on_display_mode_negotiated:
                                self.on_display_mode_negotiated(w, h, fps)
                        elif env.type == MessageType.DISPLAY_MODE_REJECT.value:
                            pass
                    except ProtocolError:
                        continue
        except OSError:
            pass
        finally:
            if self.state == ConnectionState.STREAMING:
                self.disconnect(reason="Host connection lost")

    def request_display_mode(self, width: int, height: int, refresh_rate: int = 60) -> bool:
        """Sends a display mode adaptation request to the host over the control channel."""
        sock = self._client_sock
        if not sock or self.state != ConnectionState.STREAMING:
            return False
        self._sequence_counter += 1
        env = MessageEnvelope(
            type=MessageType.DISPLAY_MODE_REQUEST.value,
            session_id=self.active_session_id or "",
            sequence=self._sequence_counter,
            payload={
                "width": width,
                "height": height,
                "refresh_rate": refresh_rate,
            },
        )
        try:
            _send_envelope(sock, env)
            return True
        except OSError:
            return False

    def send_pointer(self, x: float, y: float, normalized: bool = False) -> None:
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

    def send_touch(
        self,
        action: str,
        contacts: list[TouchPoint] | list[dict[str, Any]],
    ) -> None:
        if not self._client_sock or self.state != ConnectionState.STREAMING:
            return
        self._sequence_counter += 1
        contacts_data = [
            asdict(c) if isinstance(c, TouchPoint) else c for c in contacts
        ]
        env = MessageEnvelope(
            type=MessageType.INPUT_TOUCH.value,
            session_id=self.active_session_id or "",
            sequence=self._sequence_counter,
            payload={"action": action, "contacts": contacts_data},
        )
        try:
            _send_envelope(self._client_sock, env)
        except OSError:
            self.disconnect(reason="Send failed")

    def send_gesture(
        self,
        gesture: str,
        x: float,
        y: float,
        delta_x: float = 0.0,
        delta_y: float = 0.0,
        scale: float = 1.0,
        normalized: bool = True,
    ) -> None:
        if not self._client_sock or self.state != ConnectionState.STREAMING:
            return
        self._sequence_counter += 1
        env = MessageEnvelope(
            type=MessageType.INPUT_GESTURE.value,
            session_id=self.active_session_id or "",
            sequence=self._sequence_counter,
            payload={
                "gesture": gesture,
                "x": x,
                "y": y,
                "delta_x": delta_x,
                "delta_y": delta_y,
                "scale": scale,
                "normalized": normalized,
            },
        )
        try:
            _send_envelope(self._client_sock, env)
        except OSError:
            self.disconnect(reason="Send failed")

    # Session Management
    def connect(
        self,
        peer_device_id: str,
        peer_fingerprint: str,
        peer_address: str,
        display_width: int = 1920,
        display_height: int = 1080,
    ) -> bool:
        with self._lock:
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

            session_id = str(uuid.uuid4())
            self.active_session_id = session_id
            self.input_filter = InputFilter(
                session_id=session_id,
                display_width=display_width,
                display_height=display_height,
            )
            if self.input_injector:
                self.input_injector.update_bounds(display_width, display_height)

            self._sequence_counter = 0
            self._history_id = self.db.record_connection_start(peer_device_id)

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

            if self._media_client_sock:
                try:
                    self._media_client_sock.close()
                except OSError:
                    pass
                self._media_client_sock = None

            if self.input_filter:
                release_info = self.input_filter.release_all()
                if self.input_injector:
                    self.input_injector.release_all(
                        keys=release_info.get("released_keys"),
                        buttons=release_info.get("released_buttons"),
                    )

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
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        coords = self.input_filter.process_pointer(payload, sequence)
        if coords and self.input_injector:
            self.input_injector.inject_pointer(
                coords[0], coords[1], normalized=payload.normalized
            )
        return coords

    def handle_incoming_button(
        self, payload: ButtonPayload, sequence: int
    ) -> tuple[str, bool] | None:
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        res = self.input_filter.process_button(payload, sequence)
        if res and self.input_injector:
            self.input_injector.inject_button(res[0], res[1])
        return res

    def handle_incoming_key(
        self, payload: KeyPayload, sequence: int
    ) -> tuple[int, str, bool] | None:
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        res = self.input_filter.process_key(payload, sequence)
        if res and self.input_injector:
            self.input_injector.inject_key(res[0], res[2])
        if self.input_filter.emergency_escape_triggered:
            self.disconnect(reason="Emergency escape shortcut triggered")
        return res

    def handle_incoming_touch(
        self, payload: TouchPayload, sequence: int
    ) -> TouchPayload | None:
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        sanitized = self.input_filter.process_touch(payload, sequence)
        if sanitized and self.input_injector:
            self.input_injector.inject_touch(sanitized)
        return sanitized

    def handle_incoming_gesture(
        self, payload: GesturePayload, sequence: int
    ) -> GesturePayload | None:
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        sanitized = self.input_filter.process_gesture(payload, sequence)
        if sanitized and self.input_injector:
            self.input_injector.inject_gesture(sanitized)
        return sanitized

    def _on_local_clipboard_changed(self, text: str) -> None:
        if self.state == ConnectionState.STREAMING and self.clipboard_guard.enabled:
            self.send_clipboard_text(text)

    def send_clipboard_text(self, text: str) -> bool:
        """Sends sanitized text update to the peer over the TLS-encrypted control channel."""
        sock = self._active_client_sock or self._client_sock
        if not sock or self.state != ConnectionState.STREAMING:
            return False
        if not self.clipboard_guard.enabled:
            return False
        sanitized = self.clipboard_guard.sanitize_and_validate(text)
        self._sequence_counter += 1
        env = MessageEnvelope(
            type=MessageType.CLIPBOARD_UPDATE.value,
            session_id=self.active_session_id or "",
            sequence=self._sequence_counter,
            payload={
                "text": sanitized,
                "format": "text/plain",
                "sender_device_id": self.pairing_manager.device_id or "",
                "timestamp_us": int(time.time() * 1_000_000),
            },
        )
        try:
            _send_envelope(sock, env)
            return True
        except OSError:
            return False

    def handle_incoming_clipboard(self, payload: ClipboardUpdatePayload) -> str | None:
        """Processes and applies incoming clipboard text from authenticated peer."""
        if self.state != ConnectionState.STREAMING:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        sanitized = self.clipboard_guard.sanitize_and_validate(payload.text)
        if self.clipboard_adapter:
            self.clipboard_adapter.set_text(sanitized)
        if self.on_clipboard_received:
            self.on_clipboard_received(sanitized)
        return sanitized

    def update_telemetry(
        self, fps: float, latency_ms: float, bitrate_kbps: float, dropped_frames: int
    ) -> None:
        self.telemetry.fps = fps
        self.telemetry.latency_ms = latency_ms
        self.telemetry.bitrate_kbps = bitrate_kbps
        self.telemetry.dropped_frames = dropped_frames
        if self.on_telemetry_updated:
            self.on_telemetry_updated(self.telemetry)
