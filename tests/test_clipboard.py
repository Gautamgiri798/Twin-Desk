from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dualdesk.display.clipboard import ClipboardAdapter
from dualdesk.network.transport import ConnectionManager, ConnectionState
from dualdesk.protocol.models import (
    ClipboardUpdatePayload,
    ErrorCode,
    MessageEnvelope,
    MessageType,
    ProtocolError,
)
from dualdesk.security.clipboard_guard import ClipboardGuard
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB


def test_clipboard_payload_serialization() -> None:
    payload = ClipboardUpdatePayload(
        text="Twin Desk Clipboard Sync",
        format="text/plain",
        sender_device_id="host-001",
        timestamp_us=123456789,
    )
    assert payload.text == "Twin Desk Clipboard Sync"
    assert payload.format == "text/plain"

    env = MessageEnvelope(
        type=MessageType.CLIPBOARD_UPDATE.value,
        session_id="test_sess",
        sequence=1,
        payload={
            "text": payload.text,
            "format": payload.format,
            "sender_device_id": payload.sender_device_id,
            "timestamp_us": payload.timestamp_us,
        },
    )
    raw = env.serialize()
    deserialized = MessageEnvelope.deserialize(raw)
    assert deserialized.type == MessageType.CLIPBOARD_UPDATE.value
    assert deserialized.payload["text"] == "Twin Desk Clipboard Sync"
    assert deserialized.payload["sender_device_id"] == "host-001"


def test_clipboard_guard_sanitization_and_bounds() -> None:
    guard = ClipboardGuard(enabled=True)

    # 1. Null byte stripping
    dirty = "Line 1\x00Line 2\x00End"
    cleaned = guard.sanitize_and_validate(dirty)
    assert "\x00" not in cleaned
    assert cleaned == "Line 1Line 2End"

    # 2. Length clamping (1MB max)
    huge_text = "A" * (guard.MAX_PAYLOAD_BYTES + 500)
    clamped = guard.sanitize_and_validate(huge_text)
    assert len(clamped.encode("utf-8")) == guard.MAX_PAYLOAD_BYTES

    # 3. Hash computation
    h1 = guard.hash_text("test string")
    h2 = guard.hash_text("test string")
    assert h1 == h2
    assert len(h1) == 64

    # 4. Opt-in privacy disable check
    guard.enabled = False
    with pytest.raises(ProtocolError) as exc_info:
        guard.sanitize_and_validate("Disallowed copy")
    assert exc_info.value.code == ErrorCode.INPUT_REJECTED

    # 5. Rate limit check (max 5/sec)
    guard_rate = ClipboardGuard(enabled=True)
    for _ in range(guard_rate.MAX_UPDATES_PER_SECOND):
        guard_rate.sanitize_and_validate("OK")

    with pytest.raises(ProtocolError) as exc_rate:
        guard_rate.sanitize_and_validate("Flood")
    assert exc_rate.value.code == ErrorCode.INPUT_REJECTED


def test_clipboard_adapter_echo_suppression() -> None:
    adapter = ClipboardAdapter()

    # 1. Setting remote text records received hash
    adapter.set_text("Remote incoming text")
    assert adapter.get_text() == "Remote incoming text"

    # 2. check_for_updates should NOT trigger for remote text (suppresses feedback echo loop)
    assert adapter.check_for_updates() is None

    # 3. New local modification
    adapter._in_memory_text = "Fresh local copy"
    # When check_for_updates runs on fresh content, it returns the text
    update = adapter.check_for_updates()
    assert update == "Fresh local copy"

    # 4. Immediate second check should return None (already sent)
    assert adapter.check_for_updates() is None


def test_connection_manager_clipboard_sync_wire() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db = DualDeskDB(Path(tmp_dir) / "cm_clip.db")
        pm = PairingManager(db, local_fingerprint="SHA256:LOCAL")
        cm = ConnectionManager(db=db, pairing_manager=pm, role="host")

        # Must reject incoming clipboard when not in STREAMING state
        with pytest.raises(ProtocolError):
            cm.handle_incoming_clipboard(ClipboardUpdatePayload(text="Not streaming"))

        assert cm.send_clipboard_text("Not streaming") is False

        # Transition to STREAMING state
        cm.set_state(ConnectionState.STREAMING)

        # Track on_clipboard_received callback
        received_texts: list[str] = []
        cm.on_clipboard_received = lambda txt: received_texts.append(txt)

        # Handle incoming clipboard
        res = cm.handle_incoming_clipboard(
            ClipboardUpdatePayload(text="Hello from remote peer")
        )
        assert res == "Hello from remote peer"
        assert len(received_texts) == 1
        assert received_texts[0] == "Hello from remote peer"

        # Verify adapter received text and suppressed loop
        assert cm.clipboard_adapter.get_text() == "Hello from remote peer"
        assert cm.clipboard_adapter.check_for_updates() is None

        # Verify disabled policy rejection
        cm.clipboard_guard.enabled = False
        with pytest.raises(ProtocolError):
            cm.handle_incoming_clipboard(ClipboardUpdatePayload(text="Blocked"))

        assert cm.send_clipboard_text("Blocked") is False

        db.close()
