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
