from __future__ import annotations

import tempfile
from pathlib import Path

from dualdesk.display.capture import ScreenCaptureAdapter
from dualdesk.network.discovery import DiscoveryBeacon, DiscoveryService
from dualdesk.network.transport import ConnectionManager, ConnectionState
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB


def test_discovery_beacon_and_manual_device():
    beacon = DiscoveryBeacon(
        device_id="host-1",
        display_name="Desktop-Host",
        platform_name="Windows 11",
        role="host",
        port=53891,
        fingerprint="SHA256:TEST",
        has_virtual_driver=False,
    )
    env = beacon.to_envelope()
    assert env.type == "discovery.announce"
    assert env.payload["device_id"] == "host-1"

    service = DiscoveryService(beacon)
    manual_dev = service.add_manual_device("192.168.1.50", 53891)
    assert manual_dev.ip_address == "192.168.1.50"
    assert "192.168.1.50" in manual_dev.device_id
    devices = service.get_discovered_devices()
    assert len(devices) == 1
    assert devices[0].ip_address == "192.168.1.50"


def test_connection_manager_lifecycle_and_unpaired_rejection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db = DualDeskDB(Path(tmp_dir) / "test.db")
        pm = PairingManager(db, local_fingerprint="SHA256:LOCAL")

        states = []
        cm = ConnectionManager(
            db=db,
            pairing_manager=pm,
            role="host",
            on_state_changed=lambda st, dt: states.append(st),
        )

        assert cm.state == ConnectionState.NOT_CONNECTED

        # Unpaired connection attempt must fail
        success = cm.connect(
            peer_device_id="unpaired-peer",
            peer_fingerprint="SHA256:UNPAIRED",
            peer_address="192.168.1.99",
        )
        assert not success
        assert cm.state == ConnectionState.ERROR

        # Pair the device
        db.upsert_device(
            device_id="paired-peer",
            display_name="Paired Client",
            platform="Windows",
            trust_status="paired",
            public_key_fingerprint="SHA256:VALID-FP",
        )

        # Connect now succeeds
        success2 = cm.connect(
            peer_device_id="paired-peer",
            peer_fingerprint="SHA256:VALID-FP",
            peer_address="192.168.1.100",
        )
        assert success2
        assert cm.state == ConnectionState.STREAMING

        # Telemetry updates
        cm.update_telemetry(fps=60.0, latency_ms=14.0, bitrate_kbps=5000.0, dropped_frames=0)
        assert cm.telemetry.fps == 60.0

        # Disconnect
        cm.disconnect()
        assert cm.state == ConnectionState.DISCONNECTED
        db.close()


def test_capture_adapter_metrics():
    adapter = ScreenCaptureAdapter(width=1920, height=1080, target_fps=60, is_virtual_display=False)
    assert "Screen Preview Prototype" in adapter.source_label

    adapter.start_capture()
    assert adapter.is_capturing

    _data, stats = adapter.capture_next_frame()
    assert stats.width == 1920
    assert stats.height == 1080
    assert stats.latency_ms > 0

    adapter.stop_capture()
    assert not adapter.is_capturing


def test_pairing_manager_peer_id_fallback():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db = DualDeskDB(Path(tmp_dir) / "test.db")
        pm = PairingManager(db, local_fingerprint="SHA256:LOCAL")
        session = pm.create_challenge(
            peer_device_id="peer-device-xyz",
            peer_name="Remote Laptop",
            peer_fingerprint="SHA256:PEER",
        )

        # Lookup by peer_device_id fallback
        found = pm.get_challenge("peer-device-xyz")
        assert found is not None
        assert found.challenge_id == session.challenge_id

        # Verify using peer_device_id fallback
        verified = pm.verify_code("peer-device-xyz", session.code, "SHA256:PEER")
        assert verified
        assert pm.is_peer_paired("peer-device-xyz", "SHA256:PEER")
        db.close()


def test_tcp_control_channel_pairing_and_session():
    import time

    with tempfile.TemporaryDirectory() as tmp_dir:
        host_db = DualDeskDB(Path(tmp_dir) / "host.db")
        host_pm = PairingManager(host_db, local_fingerprint="SHA256:HOST-FP")
        host_cm = ConnectionManager(db=host_db, pairing_manager=host_pm, role="host", control_port=53992)
        host_cm.start_control_server(host="127.0.0.1", port=53992)

        client_db = DualDeskDB(Path(tmp_dir) / "client.db")
        client_pm = PairingManager(client_db, local_fingerprint="SHA256:CLIENT-FP")
        client_cm = ConnectionManager(db=client_db, pairing_manager=client_pm, role="client")

        time.sleep(0.1)  # Allow socket to bind

        try:
            # 1. Unpaired connect should be rejected
            connect_ok = client_cm.connect_to_host(
                host_address="127.0.0.1",
                port=53992,
                client_device_id="client-pc-01",
                client_fingerprint="SHA256:CLIENT-FP",
            )
            assert not connect_ok
            assert client_cm.state == ConnectionState.ERROR

            # 2. Pairing with invalid code fails
            pair_wrong = client_cm.pair_with_host(
                host_address="127.0.0.1",
                port=53992,
                client_device_id="client-pc-01",
                client_name="Client PC",
                client_fingerprint="SHA256:CLIENT-FP",
                code="000000",
            )
            assert not pair_wrong

            # 3. Successful pairing over TCP
            pair_ok = client_cm.pair_with_host(
                host_address="127.0.0.1",
                port=53992,
                client_device_id="client-pc-01",
                client_name="Client PC",
                client_fingerprint="SHA256:CLIENT-FP",
                code=None,  # Auto-submits challenge code received
            )
            assert pair_ok
            assert host_pm.is_peer_paired("client-pc-01", "SHA256:CLIENT-FP")

            # 4. Connect now succeeds over TCP control channel
            session_ok = client_cm.connect_to_host(
                host_address="127.0.0.1",
                port=53992,
                client_device_id="client-pc-01",
                client_fingerprint="SHA256:CLIENT-FP",
            )
            assert session_ok
            assert client_cm.state == ConnectionState.STREAMING
            time.sleep(0.2)
            assert host_cm.state == ConnectionState.STREAMING
            assert host_cm.input_filter is not None

            # 5. Over-the-wire input forwarding
            client_cm.send_pointer(800, 600)
            client_cm.send_button("left", pressed=True)
            client_cm.send_key(65, "A", pressed=True)
            time.sleep(0.2)
            assert host_cm.input_filter.has_held_inputs

            # 6. Release all inputs
            client_cm.send_release_all()
            time.sleep(0.2)
            assert not host_cm.input_filter.has_held_inputs

            # 7. Disconnect cleanly
            client_cm.disconnect()
            time.sleep(0.2)
            assert client_cm.state == ConnectionState.DISCONNECTED
            assert host_cm.state == ConnectionState.DISCONNECTED

        finally:
            host_cm.stop_control_server()
            host_db.close()
            client_db.close()


def test_get_local_ip():
    from dualdesk.network.discovery import get_local_ip

    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4
    # Ensure it is a valid IPv4 string
    octets = [int(x) for x in ip.split(".")]
    assert all(0 <= octet <= 255 for octet in octets)


