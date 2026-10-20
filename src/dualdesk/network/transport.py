from __future__ import annotations

import enum
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from dualdesk.protocol.models import (
    ButtonPayload,
    ErrorCode,
    KeyPayload,
    PointerPayload,
    ProtocolError,
)
from dualdesk.security.input_filter import InputFilter
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB


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


class ConnectionManager:
    """
    Manages peer-to-peer session state machine, authentication checks,
    message framing, input forwarding, telemetry, and graceful disconnect release.
    """

    RECONNECT_MAX_ATTEMPTS = 5
    INITIAL_BACKOFF_SECONDS = 1.0

    def __init__(
        self,
        db: DualDeskDB,
        pairing_manager: PairingManager,
        role: str = "host",
        on_state_changed: Callable[[ConnectionState, str], None] | None = None,
        on_telemetry_updated: Callable[[SessionTelemetry], None] | None = None,
    ) -> None:
        self.db = db
        self.pairing_manager = pairing_manager
        self.role = role
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

    def set_state(self, state: ConnectionState, detail: str = "") -> None:
        self.state = state
        self.error_message = detail if state == ConnectionState.ERROR else ""
        if self.on_state_changed:
            self.on_state_changed(state, detail)

    def start_pairing(self, peer_device_id: str, peer_name: str, peer_fingerprint: str) -> str:
        """Initiates pairing by creating a secure challenge and returning the 6-digit confirmation code."""
        self.set_state(ConnectionState.PAIRING, "Awaiting user confirmation of pairing code")
        challenge = self.pairing_manager.create_challenge(
            peer_device_id=peer_device_id,
            peer_name=peer_name,
            peer_fingerprint=peer_fingerprint,
        )
        return challenge.code

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

    def handle_incoming_pointer(self, payload: PointerPayload, sequence: int) -> tuple[float, float] | None:
        """Handles incoming pointer with authentication, sequence check, and coordinate clamping."""
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        return self.input_filter.process_pointer(payload, sequence)

    def handle_incoming_button(self, payload: ButtonPayload, sequence: int) -> tuple[str, bool] | None:
        if self.state != ConnectionState.STREAMING or not self.input_filter:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, "Session is not active")
        return self.input_filter.process_button(payload, sequence)

    def handle_incoming_key(self, payload: KeyPayload, sequence: int) -> tuple[int, str, bool] | None:
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
