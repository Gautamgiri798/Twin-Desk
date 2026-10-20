from __future__ import annotations

import tempfile
import time
from pathlib import Path

from dualdesk.display.adaptive import AdaptiveProfile, AdaptiveRateController
from dualdesk.display.capture import ScreenCaptureAdapter
from dualdesk.network.transport import ConnectionManager, ConnectionState
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB


def test_adaptive_rate_controller_initial_state() -> None:
    ctrl = AdaptiveRateController()
    metrics = ctrl.get_metrics()
    assert metrics.current_fps == 60
    assert metrics.current_quality == 70
    assert metrics.is_congested is False
    assert metrics.avg_send_latency_ms == 0.0


def test_adaptive_rate_controller_congestion_throttling() -> None:
    profile = AdaptiveProfile(
        target_fps=60,
        jpeg_quality=70,
        min_fps=15,
        min_quality=30,
        congestion_latency_ms=30.0,
    )
    ctrl = AdaptiveRateController(profile)

    # Moderate congestion: send duration 35ms (>= 30ms)
    ctrl.record_send_latency(35.0)
    assert ctrl.is_congested is True
    assert ctrl.current_quality == 65
    assert ctrl.current_fps == 55

    # Severe congestion: send duration 60ms (>= 45ms)
    ctrl.record_send_latency(60.0)
    assert ctrl.current_quality == 50
    assert ctrl.current_fps == 40

    # Continued severe congestion clamps to minimums
    for _ in range(5):
        ctrl.record_send_latency(80.0)

    assert ctrl.current_quality == 30
    assert ctrl.current_fps == 15


def test_adaptive_rate_controller_gradual_recovery() -> None:
    profile = AdaptiveProfile(
        target_fps=30,
        jpeg_quality=50,
        min_fps=15,
        max_fps=60,
        min_quality=30,
        max_quality=80,
        recovery_latency_ms=15.0,
        consecutive_fast_frames_required=4,
    )
    ctrl = AdaptiveRateController(profile)

    # Fast frames trigger steady recovery
    for _ in range(4):
        ctrl.record_send_latency(8.0)

    # Quality recovers first
    assert ctrl.current_quality > 50
    assert ctrl.is_congested is False

    # Extended fast transmissions recover to max quality and FPS
    for _ in range(25):
        ctrl.record_send_latency(5.0)

    assert ctrl.current_quality == 80
    assert ctrl.current_fps == 60


def test_screen_capture_adapter_with_adaptive_controller() -> None:
    ctrl = AdaptiveRateController()
    adapter = ScreenCaptureAdapter(
        width=1280,
        height=720,
        target_fps=60,
        adaptive_controller=ctrl,
    )
    adapter.start_capture()

    # Initial frame
    frame_bytes, stats = adapter.capture_next_frame()
    assert frame_bytes is not None
    assert stats.quality == 70
    assert stats.is_congested is False

    # Simulate heavy network congestion
    for _ in range(3):
        ctrl.record_send_latency(60.0)

    # Next frame should automatically use throttled parameters
    time.sleep(0.05)
    throttled_frame, stats = adapter.capture_next_frame()
    assert throttled_frame is not None
    assert stats.quality < 70
    assert stats.is_congested is True
    assert adapter.target_fps < 60
    assert adapter.quality < 70


def test_connection_manager_broadcast_latency_tracking() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_db = DualDeskDB(str(tmp_path / "host.db"))
        client_db = DualDeskDB(str(tmp_path / "client.db"))

        host_pm = PairingManager(host_db, "SHA256:1111-2222-3333-4444")
        client_pm = PairingManager(client_db, "SHA256:5555-6666-7777-8888")

        ctrl = AdaptiveRateController()
        sent_events: list[tuple[float, int]] = []

        host_cm = ConnectionManager(
            db=host_db,
            pairing_manager=host_pm,
            role="host",
            control_port=53972,
            media_port=53973,
            adaptive_controller=ctrl,
            on_frame_sent=lambda latency, size: sent_events.append((latency, size)),
        )

        client_cm = ConnectionManager(
            db=client_db,
            pairing_manager=client_pm,
            role="client",
            control_port=53972,
            media_port=53973,
        )

        host_cm.start_control_server()
        time.sleep(0.3)

        try:
            assert client_cm.pair_with_host(
                host_address="127.0.0.1",
                port=53972,
                client_device_id="cli-1",
                client_name="Client",
                client_fingerprint="SHA256:5555-6666-7777-8888",
            )
            assert client_cm.connect_to_host(
                host_address="127.0.0.1",
                port=53972,
                client_device_id="cli-1",
                client_fingerprint="SHA256:5555-6666-7777-8888",
            )
            assert client_cm.state == ConnectionState.STREAMING

            time.sleep(0.3)
            test_frame = b"\xFF\xD8\xFF\xE0" + b"\x01" * 2048 + b"\xFF\xD9"
            ok = host_cm.broadcast_frame(test_frame)
            assert ok is True
            assert host_cm.last_send_latency_ms >= 0.0
            assert len(sent_events) == 1
            assert sent_events[0][1] == len(test_frame)
            assert ctrl.avg_send_latency_ms >= 0.0
        finally:
            client_cm.disconnect()
            host_cm.stop_control_server()
            time.sleep(0.1)
            client_cm.db.close()
            host_cm.db.close()
