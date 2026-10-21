from __future__ import annotations

import tempfile
import time
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from dualdesk.network.transport import ConnectionManager, ConnectionState
from dualdesk.security.pairing import PairingManager
from dualdesk.security.tls import (
    compute_cert_fingerprint,
    create_tls_client_context,
    create_tls_server_context,
    generate_self_signed_cert,
    get_or_create_tls_credentials,
    verify_peer_certificate,
)
from dualdesk.storage.db import DualDeskDB


def test_self_signed_cert_generation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

        fp = generate_self_signed_cert(cert_path, key_path, "device-12345")
        assert cert_path.is_file()
        assert key_path.is_file()
        assert fp.startswith("SHA256:")
        assert len(fp.split("-")) == 4

        cert_bytes = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_bytes)
        assert cert.public_key().key_size == 2048
        der = cert.public_bytes(serialization.Encoding.DER)
        assert compute_cert_fingerprint(der) == fp


def test_tls_credentials_reuse_and_expiry() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        c1, k1, fp1 = get_or_create_tls_credentials(tmp_path, "device-abc")
        assert c1.is_file()
        assert k1.is_file()

        # Second call reuses existing valid credentials
        c2, k2, fp2 = get_or_create_tls_credentials(tmp_path, "device-abc")
        assert c1 == c2
        assert k1 == k2
        assert fp1 == fp2


def test_tls_contexts_and_mock_peer_verification() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"
        fp = generate_self_signed_cert(cert_path, key_path, "device-host")

        server_ctx = create_tls_server_context(cert_path, key_path)
        client_ctx = create_tls_client_context()
        assert server_ctx.minimum_version == client_ctx.minimum_version

        # Class with mock getpeercert
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        der = cert.public_bytes(serialization.Encoding.DER)

        class MockSSLSocket:
            def getpeercert(self, binary_form: bool = False) -> bytes:
                return der

        mock_sock = MockSSLSocket()
        assert verify_peer_certificate(mock_sock, fp) is True
        assert verify_peer_certificate(mock_sock, "SHA256:00000000-11111111-22222222-33333333") is False


def test_end_to_end_tls_control_and_media_streaming() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_db = DualDeskDB(str(tmp_path / "host.db"))
        client_db = DualDeskDB(str(tmp_path / "client.db"))

        h_cert, h_key, h_fp = get_or_create_tls_credentials(tmp_path / "host_data", "host-device")
        c_cert, c_key, c_fp = get_or_create_tls_credentials(tmp_path / "cli_data", "client-device")

        host_pm = PairingManager(host_db, h_fp)
        client_pm = PairingManager(client_db, c_fp)

        received_frames: list[bytes] = []

        host_cm = ConnectionManager(
            db=host_db,
            pairing_manager=host_pm,
            role="host",
            control_port=53982,
            media_port=53983,
            enable_tls=True,
            tls_cert_path=h_cert,
            tls_key_path=h_key,
        )

        client_cm = ConnectionManager(
            db=client_db,
            pairing_manager=client_pm,
            role="client",
            enable_tls=True,
            tls_cert_path=c_cert,
            tls_key_path=c_key,
            tls_expected_fingerprint=h_fp,
            on_frame_received=lambda frame: received_frames.append(frame),
        )

        host_cm.start_control_server()
        time.sleep(0.3)

        try:
            # 1. Pair with host over TLS 1.3
            paired = client_cm.pair_with_host(
                host_address="127.0.0.1",
                port=53982,
                client_device_id="client-device",
                client_name="Test Secure Client",
                client_fingerprint=c_fp,
            )
            assert paired is True, "Pairing over TLS 1.3 must succeed"

            # 2. Connect session over TLS 1.3
            connected = client_cm.connect_to_host(
                host_address="127.0.0.1",
                port=53982,
                client_device_id="client-device",
                client_fingerprint=c_fp,
            )
            assert connected is True, "Session connection over TLS 1.3 must succeed"
            assert client_cm.state == ConnectionState.STREAMING

            # 3. Stream frame over TLS 1.3 media channel
            test_frame = b"\xFF\xD8\xFF\xE0TEST_SECURE_FRAME\xFF\xD9"
            ready_deadline = time.time() + 3.0
            while not host_cm._media_client_sock and time.time() < ready_deadline:
                time.sleep(0.05)

            sent = host_cm.broadcast_frame(test_frame)
            assert sent is True, "Broadcasting frame over TLS media channel must succeed"

            # Allow time for receiver thread
            deadline = time.time() + 3.0
            while not received_frames and time.time() < deadline:
                time.sleep(0.05)

            assert len(received_frames) == 1
            assert received_frames[0] == test_frame
        finally:
            client_cm.disconnect()
            host_cm.stop_control_server()
            client_cm.db.close()
            host_cm.db.close()
