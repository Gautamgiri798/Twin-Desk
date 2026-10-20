from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dualdesk.protocol.models import (
    ButtonPayload,
    ErrorCode,
    KeyPayload,
    PointerPayload,
    ProtocolError,
)
from dualdesk.security.identity import get_or_create_device_identity
from dualdesk.security.input_filter import InputFilter
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB


def test_device_identity_generation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db = DualDeskDB(Path(tmp_dir) / "test.db")
        ident1 = get_or_create_device_identity(db)
        assert ident1.device_id
        assert ident1.fingerprint.startswith("SHA256:")

        # Calling again returns same identity
        ident2 = get_or_create_device_identity(db)
        assert ident1.device_id == ident2.device_id
        assert ident1.fingerprint == ident2.fingerprint
        db.close()


def test_pairing_challenge_success_and_rate_limiting():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db = DualDeskDB(Path(tmp_dir) / "test.db")
        pm = PairingManager(db, local_fingerprint="SHA256:LOCAL-FP")

        # Create challenge
        session = pm.create_challenge(
            peer_device_id="peer-100",
            peer_name="Peer Laptop",
            peer_fingerprint="SHA256:PEER-FP",
        )
        assert len(session.code) == 6
        assert session.code.isdigit()

        # Wrong code attempt 1
        with pytest.raises(ProtocolError):
            pm.verify_code(session.challenge_id, "000000", "WRONG-FP")

        # Wrong code attempt 2
        verified = pm.verify_code(session.challenge_id, "999999", "SHA256:PEER-FP")
        assert not verified

        # Correct code verifies successfully
        success = pm.verify_code(session.challenge_id, session.code, "SHA256:PEER-FP")
        assert success

        # Confirm peer is now paired
        assert pm.is_peer_paired("peer-100", "SHA256:PEER-FP")

        # Peer is rejected if fingerprint is spoofed
        assert not pm.is_peer_paired("peer-100", "SHA256:SPOOFED-FP")

        # Revocation
        assert pm.revoke_peer("peer-100")
        assert not pm.is_peer_paired("peer-100", "SHA256:PEER-FP")
        db.close()


def test_input_filter_bounds_and_sequence():
    filter_ = InputFilter(session_id="session-1", display_width=1920, display_height=1080)

    # Valid in-bounds pointer
    x, y = filter_.process_pointer(PointerPayload(x=500, y=600), sequence=1)
    assert x == 500
    assert y == 600

    # Clamping out-of-bounds pointer (negative and exceeding max)
    x, y = filter_.process_pointer(PointerPayload(x=-50, y=2000), sequence=2)
    assert x == 0.0
    assert y == 1080.0

    # Normalized pointer
    x, y = filter_.process_pointer(PointerPayload(x=0.5, y=0.5, normalized=True), sequence=3)
    assert x == 960.0
    assert y == 540.0

    # Sequence regression / replay rejected
    with pytest.raises(ProtocolError) as exc_info:
        filter_.process_pointer(PointerPayload(x=100, y=100), sequence=3)
    assert exc_info.value.code == ErrorCode.INPUT_REJECTED


def test_input_filter_release_all_on_disconnect():
    filter_ = InputFilter(session_id="session-1", display_width=1920, display_height=1080)

    # Press mouse button and key
    filter_.process_button(ButtonPayload(button="left", pressed=True), sequence=1)
    filter_.process_key(KeyPayload(key_code=65, key_name="A", pressed=True), sequence=2)
    assert filter_.has_held_inputs

    # Release all
    released = filter_.release_all()
    assert 65 in released["released_keys"]
    assert "left" in released["released_buttons"]
    assert not filter_.has_held_inputs


def test_input_filter_emergency_escape():
    filter_ = InputFilter(session_id="session-1", display_width=1920, display_height=1080)

    # Hold modifier keys
    filter_.process_key(KeyPayload(key_code=17, key_name="Control", pressed=True), sequence=1)
    filter_.process_key(KeyPayload(key_code=18, key_name="Alt", pressed=True), sequence=2)

    # Press Escape (key code 27)
    filter_.process_key(KeyPayload(key_code=27, key_name="Escape", pressed=True), sequence=3)
    assert filter_.emergency_escape_triggered
    assert not filter_.has_held_inputs
