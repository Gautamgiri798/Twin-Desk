from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ProtocolVersion:
    CURRENT = 1


class ErrorCode(str, Enum):
    PAIRING_REQUIRED = "PAIRING_REQUIRED"
    PAIRING_REJECTED = "PAIRING_REJECTED"
    UNSUPPORTED_PROTOCOL = "UNSUPPORTED_PROTOCOL"
    DRIVER_NOT_INSTALLED = "DRIVER_NOT_INSTALLED"
    DISPLAY_MODE_UNSUPPORTED = "DISPLAY_MODE_UNSUPPORTED"
    CAPTURE_UNAVAILABLE = "CAPTURE_UNAVAILABLE"
    ENCODER_UNAVAILABLE = "ENCODER_UNAVAILABLE"
    NETWORK_UNREACHABLE = "NETWORK_UNREACHABLE"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    INPUT_REJECTED = "INPUT_REJECTED"


class MessageType(str, Enum):
    # Discovery
    DISCOVERY_ANNOUNCE = "discovery.announce"
    DISCOVERY_QUERY = "discovery.query"
    DISCOVERY_RESPONSE = "discovery.response"

    # Pairing
    PAIRING_REQUEST = "pairing.request"
    PAIRING_CHALLENGE = "pairing.challenge"
    PAIRING_CONFIRM = "pairing.confirm"
    PAIRING_REJECT = "pairing.reject"

    # Session
    SESSION_START = "session.start"
    SESSION_ACCEPT = "session.accept"
    SESSION_STOP = "session.stop"
    SESSION_ERROR = "session.error"

    # Display capabilities and modes
    DISPLAY_CAPABILITIES = "display.capabilities"
    DISPLAY_MODE_REQUEST = "display.mode.request"
    DISPLAY_MODE_ACCEPT = "display.mode.accept"
    DISPLAY_MODE_REJECT = "display.mode.reject"
    DISPLAY_STATE = "display.state"

    # Input events
    INPUT_POINTER = "input.pointer"
    INPUT_BUTTON = "input.button"
    INPUT_KEY = "input.key"
    INPUT_RELEASE_ALL = "input.release_all"

    # Telemetry
    TELEMETRY_STATS = "telemetry.stats"
    TELEMETRY_WARNING = "telemetry.warning"
    TELEMETRY_ERROR = "telemetry.error"


class ProtocolError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(f"[{code.value}] {message}")
        self.code = code
        self.message = message


@dataclass
class AnnouncePayload:
    device_id: str
    display_name: str
    platform: str
    role: str  # "host" or "client"
    port: int
    fingerprint: str
    has_virtual_driver: bool = False


@dataclass
class QueryPayload:
    sender_device_id: str
    target_role: str | None = None


@dataclass
class ResponsePayload:
    device_id: str
    display_name: str
    platform: str
    role: str
    port: int
    fingerprint: str
    has_virtual_driver: bool = False


@dataclass
class PairingRequestPayload:
    client_device_id: str
    client_name: str
    client_fingerprint: str


@dataclass
class PairingChallengePayload:
    challenge_id: str
    code: str  # 6-digit confirmation code
    expires_at: str  # ISO-8601 UTC
    host_fingerprint: str


@dataclass
class PairingConfirmPayload:
    challenge_id: str
    code: str
    client_fingerprint: str


@dataclass
class PairingRejectPayload:
    challenge_id: str
    reason: str


@dataclass
class SessionStartPayload:
    session_token: str
    preferred_width: int = 1920
    preferred_height: int = 1080
    preferred_fps: int = 60


@dataclass
class SessionAcceptPayload:
    session_id: str
    assigned_width: int
    assigned_height: int
    assigned_fps: int
    media_port: int
    is_virtual_display: bool


@dataclass
class SessionStopPayload:
    session_id: str
    reason: str = "user_disconnect"


@dataclass
class SessionErrorPayload:
    code: str
    message: str


@dataclass
class DisplayMode:
    width: int
    height: int
    refresh_rate: int
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"{self.width}x{self.height} @ {self.refresh_rate}Hz"


@dataclass
class DisplayCapabilitiesPayload:
    modes: list[DisplayMode]
    driver_available: bool
    is_virtual_monitor: bool
    current_mode: DisplayMode | None = None


@dataclass
class DisplayModeRequestPayload:
    width: int
    height: int
    refresh_rate: int


@dataclass
class DisplayStatePayload:
    is_active: bool
    mode: DisplayMode
    monitor_name: str = "DualDesk Virtual Display"


@dataclass
class PointerPayload:
    x: float
    y: float
    normalized: bool = False  # If True, 0.0 to 1.0; else absolute pixel coordinates


@dataclass
class ButtonPayload:
    button: str  # "left", "right", "middle"
    pressed: bool


@dataclass
class KeyPayload:
    key_code: int
    key_name: str
    pressed: bool


@dataclass
class ReleaseAllPayload:
    reason: str = "session_reset"


@dataclass
class TelemetryStatsPayload:
    fps: float
    latency_ms: float
    bitrate_kbps: float
    dropped_frames: int
    cpu_percent: float = 0.0
    gpu_percent: float = 0.0


@dataclass
class TelemetryWarningPayload:
    warning_code: str
    description: str


@dataclass
class TelemetryErrorPayload:
    error_code: str
    description: str


@dataclass
class MessageEnvelope:
    version: int = ProtocolVersion.CURRENT
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    sequence: int = 0
    type: str = ""
    sent_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    payload: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Enforces schema rules according to docs/api.md."""
        if self.version != ProtocolVersion.CURRENT:
            raise ProtocolError(
                ErrorCode.UNSUPPORTED_PROTOCOL,
                f"Unsupported protocol version: {self.version}",
            )
        if not self.message_id:
            raise ProtocolError(
                ErrorCode.UNSUPPORTED_PROTOCOL, "Missing message_id"
            )
        if not self.type:
            raise ProtocolError(
                ErrorCode.UNSUPPORTED_PROTOCOL, "Missing message type"
            )
        if self.sequence < 0:
            raise ProtocolError(
                ErrorCode.INPUT_REJECTED, "Invalid negative sequence number"
            )

    def serialize(self) -> str:
        self.validate()
        data = asdict(self)
        return json.dumps(data)

    @classmethod
    def deserialize(cls, json_str: str) -> MessageEnvelope:
        try:
            raw = json.loads(json_str)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise ProtocolError(
                ErrorCode.UNSUPPORTED_PROTOCOL, f"Invalid JSON payload: {e}"
            ) from e
        if not isinstance(raw, dict):
            raise ProtocolError(
                ErrorCode.UNSUPPORTED_PROTOCOL, "Envelope must be a JSON object"
            )

        envelope = cls(
            version=raw.get("version", 0),
            message_id=raw.get("message_id", ""),
            session_id=raw.get("session_id", ""),
            sequence=raw.get("sequence", 0),
            type=raw.get("type", ""),
            sent_at=raw.get("sent_at", ""),
            payload=raw.get("payload", {}) or {},
        )
        envelope.validate()
        return envelope
