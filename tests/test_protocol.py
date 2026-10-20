from __future__ import annotations

import pytest

from dualdesk.protocol.models import (
    DisplayMode,
    ErrorCode,
    MessageEnvelope,
    MessageType,
    PointerPayload,
    ProtocolError,
    ProtocolVersion,
    TelemetryStatsPayload,
)


def test_envelope_valid_serialization():
    env = MessageEnvelope(
        type=MessageType.DISCOVERY_ANNOUNCE.value,
        session_id="test-session",
        sequence=1,
        payload={"device_id": "dev-123"},
    )
    raw = env.serialize()
    assert "test-session" in raw
    assert "discovery.announce" in raw

    restored = MessageEnvelope.deserialize(raw)
    assert restored.version == ProtocolVersion.CURRENT
    assert restored.session_id == "test-session"
    assert restored.sequence == 1
    assert restored.payload["device_id"] == "dev-123"


def test_envelope_invalid_version():
    env = MessageEnvelope(
        version=99,
        type="test",
    )
    with pytest.raises(ProtocolError) as exc_info:
        env.validate()
    assert exc_info.value.code == ErrorCode.UNSUPPORTED_PROTOCOL


def test_envelope_negative_sequence():
    env = MessageEnvelope(
        type="test",
        sequence=-5,
    )
    with pytest.raises(ProtocolError) as exc_info:
        env.validate()
    assert exc_info.value.code == ErrorCode.INPUT_REJECTED


def test_envelope_invalid_json():
    with pytest.raises(ProtocolError) as exc_info:
        MessageEnvelope.deserialize("NOT_VALID_JSON{")
    assert exc_info.value.code == ErrorCode.UNSUPPORTED_PROTOCOL


def test_display_mode_helper():
    mode = DisplayMode(1920, 1080, 60)
    assert mode.name == "1920x1080 @ 60Hz"


def test_pointer_payload():
    ptr = PointerPayload(x=100.5, y=200.0, normalized=False)
    assert ptr.x == 100.5
    assert ptr.y == 200.0
    assert not ptr.normalized


def test_telemetry_payload():
    stats = TelemetryStatsPayload(
        fps=59.8,
        latency_ms=14.2,
        bitrate_kbps=5200.0,
        dropped_frames=0,
    )
    assert stats.fps == 59.8
    assert stats.latency_ms == 14.2
