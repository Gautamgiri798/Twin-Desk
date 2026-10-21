from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

# Headless offscreen Qt for test runners
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QSize
from PySide6.QtGui import QResizeEvent

from dualdesk.display.capture import ScreenCaptureAdapter
from dualdesk.display.driver import negotiate_target_mode
from dualdesk.display.encoder import EncoderConfig, VideoCodec, VideoEncoderAdapter
from dualdesk.network.transport import ConnectionManager, ConnectionState
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB
from dualdesk.ui.viewer import StreamViewerWidget


def test_negotiate_target_mode_exact_match():
    mode = negotiate_target_mode(1920, 1080, 60)
    assert mode.width == 1920
    assert mode.height == 1080
    assert mode.refresh_rate == 60


def test_negotiate_target_mode_resolution_match_closest_fps():
    # 1920x1080 with 45Hz requested -> should pick 60Hz or 30Hz closest
    mode = negotiate_target_mode(1920, 1080, 50)
    assert mode.width == 1920
    assert mode.height == 1080
    assert mode.refresh_rate == 60


def test_negotiate_target_mode_aspect_ratio_selection():
    # 1600x900 is 16:9, should pick 16:9 widescreen format (1920x1080, 1366x768, 1280x720, or 2560x1440)
    mode = negotiate_target_mode(1600, 900, 60)
    assert mode.width in (1920, 1366, 1280, 2560)
    assert mode.refresh_rate == 60
    assert abs((mode.width / mode.height) - (16 / 9)) < 0.05

    # 4K request
    mode_4k = negotiate_target_mode(3840, 2160, 60)
    assert mode_4k.width == 3840
    assert mode_4k.height == 2160


def test_screen_capture_adapter_dynamic_resolution():
    adapter = ScreenCaptureAdapter(width=1920, height=1080, target_fps=60)
    assert adapter.width == 1920
    assert adapter.height == 1080

    adapter.set_resolution(1280, 720, 30)
    assert adapter.width == 1280
    assert adapter.height == 720
    assert adapter.target_fps == 30

    # Clamping below minimum
    adapter.set_resolution(100, 50)
    assert adapter.width == 320
    assert adapter.height == 180

    # With encoder attached
    encoder = VideoEncoderAdapter(
        EncoderConfig(codec=VideoCodec.H264, width=1920, height=1080, target_fps=60)
    )
    adapter_enc = ScreenCaptureAdapter(width=1920, height=1080, encoder=encoder)
    adapter_enc.set_resolution(1280, 720, 30)
    assert adapter_enc.encoder.config.width == 1280
    assert adapter_enc.encoder.config.height == 720
    assert adapter_enc.encoder.config.target_fps == 30


def test_display_mode_negotiation_over_wire():
    with tempfile.TemporaryDirectory() as tmp_dir:
        host_db = DualDeskDB(Path(tmp_dir) / "host.db")
        host_pm = PairingManager(host_db, local_fingerprint="SHA256:HOST_MODE")
        host_mode_changes: list[tuple[int, int, int]] = []

        host_cm = ConnectionManager(
            db=host_db,
            pairing_manager=host_pm,
            role="host",
            control_port=54011,
            media_port=54012,
            on_display_mode_changed=lambda w, h, fps: host_mode_changes.append((w, h, fps)),
        )
        host_cm.start_control_server(host="127.0.0.1", port=54011)

        client_db = DualDeskDB(Path(tmp_dir) / "client.db")
        client_pm = PairingManager(client_db, local_fingerprint="SHA256:CLIENT_MODE")
        client_negotiated_modes: list[tuple[int, int, int]] = []

        client_cm = ConnectionManager(
            db=client_db,
            pairing_manager=client_pm,
            role="client",
            on_display_mode_negotiated=lambda w, h, fps: client_negotiated_modes.append((w, h, fps)),
        )

        time.sleep(0.1)

        try:
            # Pair and connect
            pair_ok = client_cm.pair_with_host(
                host_address="127.0.0.1",
                port=54011,
                client_device_id="client-mode-test",
                client_name="Client Mode Tester",
                client_fingerprint="SHA256:CLIENT_MODE",
            )
            assert pair_ok

            conn_ok = client_cm.connect_to_host(
                host_address="127.0.0.1",
                port=54011,
                client_device_id="client-mode-test",
                client_fingerprint="SHA256:CLIENT_MODE",
            )
            assert conn_ok
            assert client_cm.state == ConnectionState.STREAMING

            time.sleep(0.15)

            # Client requests 1280x720 @ 60Hz
            req_sent = client_cm.request_display_mode(1280, 720, 60)
            assert req_sent is True

            time.sleep(0.2)

            # Verify host accepted and changed mode
            assert len(host_mode_changes) == 1
            assert host_mode_changes[0] == (1280, 720, 60)
            assert host_cm.current_display_mode.width == 1280
            assert host_cm.current_display_mode.height == 720

            # Verify client received accept confirmation
            assert len(client_negotiated_modes) == 1
            assert client_negotiated_modes[0] == (1280, 720, 60)
            assert client_cm.current_display_mode.width == 1280
            assert client_cm.current_display_mode.height == 720

            # Request out-of-bounds mode (50x50) -> should be rejected
            req_bad = client_cm.request_display_mode(50, 50, 60)
            assert req_bad is True
            time.sleep(0.15)
            # Host should NOT update to 50x50
            assert len(host_mode_changes) == 1

            client_cm.disconnect()
        finally:
            host_cm.stop_control_server()
            host_db.close()
            client_db.close()


def test_stream_viewer_debounced_resize(qapp):
    mock_cm = MagicMock(spec=ConnectionManager)
    mock_cm.state = ConnectionState.STREAMING
    mock_cm.role = "client"

    viewer = StreamViewerWidget(mock_cm)
    viewer.resize(1600, 900)

    # Trigger resize event directly
    resize_ev = QResizeEvent(QSize(1600, 900), QSize(1280, 720))
    viewer.resizeEvent(resize_ev)

    # Debounce timer should be active
    assert viewer._resize_timer.isActive()

    # Fast forward debounced resize slot
    viewer._on_debounced_resize()
    mock_cm.request_display_mode.assert_called_with(1600, 900)
