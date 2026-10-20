from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

# Ensure headless offscreen platform for Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QApplication

from dualdesk.display.capture import ScreenCaptureAdapter
from dualdesk.display.input_injector import InputInjector
from dualdesk.network.transport import ConnectionManager, ConnectionState
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB
from dualdesk.ui.viewer import StreamViewerWidget, StreamWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_screen_capture_real_frames():
    adapter = ScreenCaptureAdapter(width=640, height=360, target_fps=30)
    adapter.start_capture()
    assert adapter.is_capturing

    frame_bytes, stats = adapter.capture_next_frame()
    assert frame_bytes is not None
    assert len(frame_bytes) > 0
    assert stats.fps >= 0.0
    assert stats.latency_ms > 0.0
    assert stats.width == 640
    assert stats.height == 360
    assert "Screen Preview Prototype" in stats.source_label

    adapter.stop_capture()
    assert not adapter.is_capturing


def test_input_injector_bounds_and_methods():
    injector = InputInjector(display_width=1920, display_height=1080, enabled=True)

    # In-bounds pointer
    ok_p1 = injector.inject_pointer(500, 600)
    assert ok_p1 is True

    # Out-of-bounds pointer (should clamp safely and succeed)
    ok_p2 = injector.inject_pointer(-200, 5000)
    assert ok_p2 is True

    # Mouse buttons
    assert injector.inject_button("left", pressed=True) is True
    assert injector.inject_button("left", pressed=False) is True
    assert injector.inject_button("right", pressed=True) is True
    assert injector.inject_button("middle", pressed=True) is True
    assert injector.inject_button("invalid_button", pressed=True) is False

    # Keyboard events
    assert injector.inject_key(65, pressed=True) is True  # 'A'
    assert injector.inject_key(65, pressed=False) is True
    assert injector.inject_key(999, pressed=True) is False  # Invalid VK

    # Release all
    injector.release_all(keys=[65, 66], buttons=["left", "right"])


def test_media_frame_streaming_over_loopback():
    with tempfile.TemporaryDirectory() as tmp_dir:
        host_db = DualDeskDB(Path(tmp_dir) / "host.db")
        host_pm = PairingManager(host_db, local_fingerprint="SHA256:HOST")
        host_cm = ConnectionManager(
            db=host_db,
            pairing_manager=host_pm,
            role="host",
            control_port=54001,
            media_port=54002,
        )
        host_cm.start_control_server(host="127.0.0.1", port=54001)

        received_frames: list[bytes] = []

        client_db = DualDeskDB(Path(tmp_dir) / "client.db")
        client_pm = PairingManager(client_db, local_fingerprint="SHA256:CLIENT")
        client_cm = ConnectionManager(
            db=client_db,
            pairing_manager=client_pm,
            role="client",
            on_frame_received=lambda data: received_frames.append(data),
        )

        time.sleep(0.1)

        try:
            # Pair client with host
            pair_ok = client_cm.pair_with_host(
                host_address="127.0.0.1",
                port=54001,
                client_device_id="client-test",
                client_name="Test PC",
                client_fingerprint="SHA256:CLIENT",
            )
            assert pair_ok

            # Connect session (starts media streaming receiver)
            conn_ok = client_cm.connect_to_host(
                host_address="127.0.0.1",
                port=54001,
                client_device_id="client-test",
                client_fingerprint="SHA256:CLIENT",
            )
            assert conn_ok
            assert client_cm.state == ConnectionState.STREAMING

            time.sleep(0.2)

            # Broadcast frame from host
            test_frame = b"\xff\xd8\xff\xe0" + b"\x42" * 500  # Valid test frame payload
            sent = host_cm.broadcast_frame(test_frame)
            assert sent is True

            time.sleep(0.2)
            assert len(received_frames) == 1
            assert received_frames[0] == test_frame

            # Disconnect
            client_cm.disconnect()
            time.sleep(0.1)
            assert client_cm.state == ConnectionState.DISCONNECTED

        finally:
            host_cm.stop_control_server()
            host_db.close()
            client_db.close()


def test_stream_viewer_widget(qapp):
    with tempfile.TemporaryDirectory() as tmp_dir:
        db = DualDeskDB(Path(tmp_dir) / "test.db")
        pm = PairingManager(db, local_fingerprint="SHA256:TEST")
        cm = ConnectionManager(db=db, pairing_manager=pm, role="client")

        viewer = StreamViewerWidget(cm)
        viewer.resize(800, 600)

        # Coordinate mapping when no frame is rendered
        assert viewer._map_to_normalized(QPointF(400, 300)) is None

        # Synthesize a test frame
        adapter = ScreenCaptureAdapter(width=320, height=180)
        adapter.start_capture()
        frame_bytes, _ = adapter.capture_next_frame()
        adapter.stop_capture()

        if frame_bytes:
            viewer.update_frame(frame_bytes)
            viewer._render_rect = QRectF(100, 50, 600, 400)

            # Map point inside render rect
            norm = viewer._map_to_normalized(QPointF(400, 250))
            assert norm is not None
            assert 0.0 <= norm[0] <= 1.0
            assert 0.0 <= norm[1] <= 1.0

            # Map point outside render rect
            outside = viewer._map_to_normalized(QPointF(50, 20))
            assert outside is None

        window = StreamWindow(cm)
        window.resize(640, 480)
        if frame_bytes:
            window.update_frame(frame_bytes)
        window.close()
        db.close()
