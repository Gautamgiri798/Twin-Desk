from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from dualdesk.network.file_transfer import (
    MAX_FILE_SIZE_BYTES,
    FileTransferManager,
    sanitize_filename,
)
from dualdesk.network.transport import ConnectionManager, ConnectionState
from dualdesk.protocol.models import (
    FileTransferChunkPayload,
    FileTransferRequestPayload,
)
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB


def test_sanitize_filename() -> None:
    # Directory traversal attack payloads
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\calc.exe") == "calc.exe"
    assert sanitize_filename("/var/log/syslog") == "syslog"
    assert sanitize_filename("C:\\Users\\User\\secret.docx") == "secret.docx"

    # Forbidden chars on Windows
    assert sanitize_filename("test:file*name?.txt") == "test_file_name_.txt"
    assert sanitize_filename('<evil>"pipe|file.bin') == "_evil__pipe_file.bin"

    # Edge cases
    assert sanitize_filename("") == "transferred_file.bin"
    assert sanitize_filename("..") == "transferred_file.bin"
    assert sanitize_filename(".") == "transferred_file.bin"
    assert sanitize_filename("   ...   ") == "transferred_file.bin"


def test_prepare_outgoing_file_and_bounds() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        test_file = tmp_path / "sample.txt"
        content = b"DualDesk Secure File Transfer Payload" * 100
        test_file.write_bytes(content)

        mgr = FileTransferManager(save_dir=tmp_path)
        req, chunks = mgr.prepare_outgoing_file(test_file, sender_device_id="dev-1")

        assert req.file_name == "sample.txt"
        assert req.file_size_bytes == len(content)
        assert len(req.file_sha256) == 64
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1
        assert len(chunks[0].chunk_sha256) == 64

        # Nonexistent file
        with pytest.raises(FileNotFoundError):
            mgr.prepare_outgoing_file(tmp_path / "nonexistent.bin")


def test_file_transfer_size_limit_rejection() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        mgr = FileTransferManager(save_dir=tmp_path)

        req = FileTransferRequestPayload(
            transfer_id="t-1",
            file_name="huge.iso",
            file_size_bytes=MAX_FILE_SIZE_BYTES + 1024,
            file_sha256="abc",
        )
        resp = mgr.handle_transfer_request(req, explicit_consent=True)
        assert not resp.accepted
        assert "exceeds maximum size limit" in resp.reason


def test_file_transfer_explicit_consent_requirement() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        mgr = FileTransferManager(save_dir=tmp_path)

        req = FileTransferRequestPayload(
            transfer_id="t-2",
            file_name="document.pdf",
            file_size_bytes=1024,
            file_sha256="dummy",
        )

        # Receiver declines
        declined_resp = mgr.handle_transfer_request(req, explicit_consent=False)
        assert not declined_resp.accepted
        assert "declined by receiver" in declined_resp.reason.lower()

        # Receiver accepts
        accepted_resp = mgr.handle_transfer_request(req, explicit_consent=True)
        assert accepted_resp.accepted


def test_file_transfer_end_to_end_verification_and_collision() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        save_dir = Path(tmp_dir) / "downloads"
        save_dir.mkdir()

        # Create source file
        src_dir = Path(tmp_dir) / "source"
        src_dir.mkdir()
        src_file = src_dir / "report.dat"
        payload_data = b"Encrypted data block\n" * 5000
        src_file.write_bytes(payload_data)

        sender_mgr = FileTransferManager()
        req, chunks = sender_mgr.prepare_outgoing_file(src_file)

        receiver_mgr = FileTransferManager(save_dir=save_dir)
        accept = receiver_mgr.handle_transfer_request(req, explicit_consent=True)
        assert accept.accepted

        # Feed all chunks
        for chunk in chunks:
            ok = receiver_mgr.handle_chunk(chunk)
            assert ok

        # Finalize
        success, final_path, _msg = receiver_mgr.finalize_transfer(req.transfer_id)
        assert success
        assert final_path is not None
        assert final_path.exists()
        assert final_path.name == "report.dat"
        assert final_path.read_bytes() == payload_data

        # Transfer same file again -> should avoid overwrite with collision numbering
        req2, chunks2 = sender_mgr.prepare_outgoing_file(src_file)
        receiver_mgr.handle_transfer_request(req2, explicit_consent=True)
        for chunk in chunks2:
            receiver_mgr.handle_chunk(chunk)
        success2, final_path2, _ = receiver_mgr.finalize_transfer(req2.transfer_id)
        assert success2
        assert final_path2 is not None
        assert final_path2.name == "report (1).dat"
        assert final_path2.read_bytes() == payload_data


def test_corrupted_chunk_and_checksum_mismatch_discard() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        save_dir = Path(tmp_dir) / "downloads"
        save_dir.mkdir()
        src_file = Path(tmp_dir) / "test.txt"
        src_file.write_bytes(b"Clean test contents")

        mgr = FileTransferManager(save_dir=save_dir)
        req, chunks = mgr.prepare_outgoing_file(src_file)

        mgr.handle_transfer_request(req, explicit_consent=True)

        # Corrupt chunk hash
        corrupt_chunk = FileTransferChunkPayload(
            transfer_id=chunks[0].transfer_id,
            chunk_index=chunks[0].chunk_index,
            total_chunks=chunks[0].total_chunks,
            data_b64=chunks[0].data_b64,
            chunk_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        )
        ok = mgr.handle_chunk(corrupt_chunk)
        assert not ok
        # Ensure partial file was cleanly removed
        part_files = list(save_dir.glob("*.part"))
        assert len(part_files) == 0


def test_connection_manager_file_transfer_over_wire() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        host_db = DualDeskDB(":memory:")
        host_pm = PairingManager(host_db, local_fingerprint="SHA256:HOST-FP")
        host_cm = ConnectionManager(
            db=host_db, pairing_manager=host_pm, role="host", control_port=53995
        )
        host_cm.start_control_server(host="127.0.0.1", port=53995)

        client_db = DualDeskDB(":memory:")
        client_pm = PairingManager(client_db, local_fingerprint="SHA256:CLIENT-FP")
        client_cm = ConnectionManager(db=client_db, pairing_manager=client_pm, role="client")

        time.sleep(0.1)

        # Pair peers
        client_cm.pair_with_host(
            host_address="127.0.0.1",
            port=53995,
            client_device_id="client-pc",
            client_name="Client PC",
            client_fingerprint="SHA256:CLIENT-FP",
        )
        # Connect
        connected = client_cm.connect_to_host(
            host_address="127.0.0.1",
            port=53995,
            client_device_id="client-pc",
            client_fingerprint="SHA256:CLIENT-FP",
        )
        assert connected
        assert client_cm.state == ConnectionState.STREAMING

        # Configure host file transfer destination
        host_save_dir = tmp_path / "host_received"
        host_cm.file_transfer_manager.save_dir = host_save_dir
        host_save_dir.mkdir(parents=True, exist_ok=True)

        received_files: list[Path] = []
        host_cm.on_file_transfer_completed = (
            lambda tid, success, path, msg: received_files.append(path) if success and path else None
        )

        # Create source file on client
        send_file = tmp_path / "client_note.txt"
        test_payload = b"Synchronized note transferred over TLS control stream."
        send_file.write_bytes(test_payload)

        # Send file from client to host
        transfer_id = client_cm.send_file(send_file)
        assert transfer_id

        # Wait briefly for transfer completion over loopback
        for _ in range(20):
            if received_files:
                break
            time.sleep(0.1)

        assert len(received_files) == 1
        rx_path = received_files[0]
        assert rx_path.name == "client_note.txt"
        assert rx_path.read_bytes() == test_payload

        # Clean shutdown
        client_cm.disconnect()
        host_cm.stop_control_server()
        host_db.close()
        client_db.close()
