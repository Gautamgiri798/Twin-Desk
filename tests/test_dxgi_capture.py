from __future__ import annotations

import os
import platform
import time
from unittest.mock import MagicMock

# Offscreen Qt for headless test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from dualdesk.display.capture import ScreenCaptureAdapter
from dualdesk.display.dxgi_capture import DXGICaptureAdapter, DXGIFrame


def test_dxgi_frame_dataclass():
    frame = DXGIFrame(
        width=1920,
        height=1080,
        pitch=7680,
        data=b"\xaa" * 100,
        timestamp_us=1700000000000,
    )
    assert frame.width == 1920
    assert frame.height == 1080
    assert frame.pitch == 7680
    assert len(frame.data) == 100
    assert frame.timestamp_us == 1700000000000


def test_dxgi_capture_adapter_support_and_lifecycle():
    supported = DXGICaptureAdapter.is_supported()
    assert isinstance(supported, bool)

    adapter = DXGICaptureAdapter(output_index=0)
    assert not adapter.is_initialized
    assert adapter.width == 0
    assert adapter.height == 0
    assert adapter.device_name == ""

    # Cleanup uninitialized adapter must be safe
    adapter.cleanup()
    assert not adapter.is_initialized

    # Initialize on current machine (returns bool without raising)
    init_ok = adapter.initialize(0)
    assert isinstance(init_ok, bool)

    if init_ok:
        assert adapter.is_initialized
        assert adapter.width > 0
        assert adapter.height > 0

        # Attempt frame acquisition
        frame = adapter.acquire_frame(timeout_ms=10)
        if frame is not None:
            assert isinstance(frame, DXGIFrame)
            assert frame.width == adapter.width
            assert frame.height == adapter.height
            assert len(frame.data) > 0

        adapter.cleanup()
        assert not adapter.is_initialized


def test_screen_capture_with_mock_dxgi_backend():
    mock_dxgi = MagicMock(spec=DXGICaptureAdapter)
    mock_dxgi.is_initialized = True
    test_w, test_h = 640, 360
    fake_bgra = b"\x00\x80\xff\xff" * (test_w * test_h)
    mock_frame = DXGIFrame(
        width=test_w,
        height=test_h,
        pitch=test_w * 4,
        data=fake_bgra,
        timestamp_us=int(time.time() * 1_000_000),
    )
    mock_dxgi.acquire_frame.return_value = mock_frame

    adapter = ScreenCaptureAdapter(
        width=test_w,
        height=test_h,
        backend="dxgi",
        dxgi_adapter=mock_dxgi,
    )
    adapter.start_capture()
    assert adapter.is_capturing
    assert adapter.active_backend == "dxgi"

    frame_bytes, stats = adapter.capture_next_frame()
    assert frame_bytes is not None
    assert len(frame_bytes) > 0
    assert stats.backend == "dxgi"
    assert stats.total_frames_captured == 1
    assert stats.latency_ms > 0

    adapter.stop_capture()
    assert not adapter.is_capturing
    mock_dxgi.cleanup.assert_called_once()


def test_screen_capture_dxgi_timeout_and_fallback():
    mock_dxgi = MagicMock(spec=DXGICaptureAdapter)
    mock_dxgi.is_initialized = True
    # Simulate DXGI timeout (returns None)
    mock_dxgi.acquire_frame.return_value = None

    adapter = ScreenCaptureAdapter(
        width=640,
        height=360,
        backend="auto",
        dxgi_adapter=mock_dxgi,
    )
    adapter.start_capture()
    assert adapter.is_capturing

    # When DXGI times out, ScreenCaptureAdapter falls back to GDI to guarantee frame acquisition
    frame_bytes, _stats = adapter.capture_next_frame()
    if platform.system() == "Windows":
        assert frame_bytes is not None
        assert len(frame_bytes) > 0

    adapter.stop_capture()


def test_screen_capture_dxgi_access_lost_handling():
    mock_dxgi = MagicMock(spec=DXGICaptureAdapter)
    mock_dxgi.is_initialized = True

    def simulate_access_lost(timeout_ms=16):
        mock_dxgi.is_initialized = False

    mock_dxgi.acquire_frame.side_effect = simulate_access_lost

    adapter = ScreenCaptureAdapter(
        width=640,
        height=360,
        backend="auto",
        dxgi_adapter=mock_dxgi,
    )
    adapter.start_capture()
    assert adapter.active_backend == "dxgi"

    # Frame capture triggers access lost -> active_backend drops to gdi
    frame_bytes, _stats = adapter.capture_next_frame()
    assert adapter.active_backend == "gdi"
    if platform.system() == "Windows":
        assert frame_bytes is not None

    adapter.stop_capture()


def test_screen_capture_explicit_gdi_backend():
    adapter = ScreenCaptureAdapter(
        width=640,
        height=360,
        backend="gdi",
    )
    adapter.start_capture()
    assert adapter.active_backend == "gdi"
    assert adapter.dxgi_adapter is None

    frame_bytes, stats = adapter.capture_next_frame()
    assert stats.backend == "gdi"
    if platform.system() == "Windows":
        assert frame_bytes is not None
        assert len(frame_bytes) > 0

    adapter.stop_capture()
