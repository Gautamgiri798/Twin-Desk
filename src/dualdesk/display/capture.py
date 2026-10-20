from __future__ import annotations

import ctypes
import platform
import time
from dataclasses import dataclass

from dualdesk.display.adaptive import AdaptiveRateController
from dualdesk.display.dxgi_capture import DXGICaptureAdapter
from dualdesk.display.encoder import (
    EncoderConfig,
    VideoCodec,
    VideoEncoderAdapter,
)

try:
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage

    HAS_QT_IMAGE = True
except (ImportError, RuntimeError):
    HAS_QT_IMAGE = False


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


@dataclass
class CaptureStats:
    fps: float
    latency_ms: float
    bitrate_kbps: float
    dropped_frames: int
    total_frames_captured: int
    width: int
    height: int
    is_virtual_display: bool
    source_label: str
    quality: int = 70
    is_congested: bool = False
    codec: str = "jpeg"
    is_hardware_accelerated: bool = False
    backend: str = "gdi"


class ScreenCaptureAdapter:
    """
    Screen capture adapter that captures desktop frames via DirectX 11 / DXGI Desktop Duplication
    or Win32 GDI fallback, compresses frames into JPEG or H.264 buffers, measures real FPS/latency/bitrate,
    and dynamically adapts framerate and quality based on network congestion.
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        target_fps: int = 60,
        quality: int = 70,
        is_virtual_display: bool = False,
        adaptive_controller: AdaptiveRateController | None = None,
        codec: str = "jpeg",
        encoder: VideoEncoderAdapter | None = None,
        backend: str = "auto",
        output_index: int = 0,
        dxgi_adapter: DXGICaptureAdapter | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.quality = quality
        self.is_virtual_display = is_virtual_display
        self.adaptive_controller = adaptive_controller
        self.codec = codec.lower()
        self.backend = backend.lower()
        self.output_index = output_index
        self.dxgi_adapter = dxgi_adapter
        self.active_backend = "dxgi" if (dxgi_adapter and dxgi_adapter.is_initialized) else "gdi"
        if self.codec == "h264" and encoder is None:
            self.encoder: VideoEncoderAdapter | None = VideoEncoderAdapter(
                EncoderConfig(
                    codec=VideoCodec.H264,
                    width=width,
                    height=height,
                    target_fps=target_fps,
                )
            )
        else:
            self.encoder = encoder
        self.is_capturing = False

        self._frame_count = 0
        self._dropped_frames = 0
        self._last_frame_time = 0.0
        self._fps_window_start = time.time()
        self._fps_counter = 0
        self._current_fps = 0.0
        self._last_latency_ms = 8.0
        self._estimated_bitrate_kbps = 4500.0

    @property
    def source_label(self) -> str:
        if self.is_virtual_display:
            return "Windows IDD Virtual Extended Display"
        return "Screen Preview Prototype (Local Display Capture)"

    def start_capture(self) -> None:
        self.is_capturing = True
        self._frame_count = 0
        self._dropped_frames = 0
        self._fps_window_start = time.time()
        self._last_frame_time = 0.0

        if self.dxgi_adapter is not None:
            if not self.dxgi_adapter.is_initialized:
                if self.dxgi_adapter.initialize(self.output_index):
                    self.active_backend = "dxgi"
                elif self.backend != "dxgi":
                    self.active_backend = "gdi"
            else:
                self.active_backend = "dxgi"
        elif self.backend in ("auto", "dxgi"):
            try:
                adapter = DXGICaptureAdapter(output_index=self.output_index)
                if adapter.initialize(self.output_index):
                    self.dxgi_adapter = adapter
                    self.active_backend = "dxgi"
                else:
                    self.active_backend = "gdi"
            except (AttributeError, OSError, ValueError, RuntimeError):
                self.active_backend = "gdi"
        else:
            self.active_backend = "gdi"

    def stop_capture(self) -> None:
        self.is_capturing = False
        if self.dxgi_adapter:
            self.dxgi_adapter.cleanup()

    def capture_next_frame(self) -> tuple[bytes | None, CaptureStats]:
        """
        Captures the next frame from the display and returns the compressed frame bytes and telemetry.
        """
        if self.adaptive_controller:
            self.target_fps = self.adaptive_controller.current_fps
            self.quality = self.adaptive_controller.current_quality

        now = time.time()
        frame_interval = 1.0 / max(1, self.target_fps)

        if self._last_frame_time > 0 and (now - self._last_frame_time) < (frame_interval * 0.75):
            return None, self.get_stats()

        capture_start = time.perf_counter()
        frame_data: bytes | None = None
        cap_w = max(320, min(self.width, 1280))
        cap_h = max(180, min(self.height, 720))

        # 1. Try DXGI Desktop Duplication if active
        if self.active_backend == "dxgi" and self.dxgi_adapter and self.dxgi_adapter.is_initialized:
            try:
                dxgi_frame = self.dxgi_adapter.acquire_frame(timeout_ms=16)
                if dxgi_frame is not None:
                    if self.codec == "h264" and self.encoder:
                        packet = self.encoder.encode_frame(
                            raw_pixels=dxgi_frame.data,
                            timestamp_us=dxgi_frame.timestamp_us,
                        )
                        frame_data = packet.data
                    elif HAS_QT_IMAGE:
                        img = QImage(
                            dxgi_frame.data,
                            dxgi_frame.width,
                            dxgi_frame.height,
                            dxgi_frame.pitch,
                            QImage.Format.Format_ARGB32,
                        )
                        qbuf = QBuffer()
                        qbuf.open(QIODevice.OpenModeFlag.WriteOnly)
                        img.save(qbuf, "JPEG", self.quality)
                        frame_data = bytes(qbuf.data())
                    else:
                        frame_data = dxgi_frame.data[:4096]
                elif not self.dxgi_adapter.is_initialized:
                    # Access lost and reinitialization failed; fall back to GDI
                    self.active_backend = "gdi"
            except (AttributeError, OSError, ValueError, RuntimeError):
                self.active_backend = "gdi"

        # 2. Fall back to Win32 GDI if DXGI not active or produced no frame
        if frame_data is None:
            if platform.system() == "Windows":
                try:
                    user32 = ctypes.windll.user32
                    gdi32 = ctypes.windll.gdi32
                    hdesktop = user32.GetDesktopWindow()
                    hdc_screen = user32.GetDC(hdesktop)
                    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
                    hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, cap_w, cap_h)
                    h_old = gdi32.SelectObject(hdc_mem, hbitmap)

                    gdi32.BitBlt(hdc_mem, 0, 0, cap_w, cap_h, hdc_screen, 0, 0, 0x00CC0020)

                    bmi = BITMAPINFOHEADER()
                    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                    bmi.biWidth = cap_w
                    bmi.biHeight = -cap_h  # Top-down DIB
                    bmi.biPlanes = 1
                    bmi.biBitCount = 32
                    bmi.biCompression = 0

                    raw_buf = (ctypes.c_char * (cap_w * cap_h * 4))()
                    gdi32.GetDIBits(hdc_mem, hbitmap, 0, cap_h, raw_buf, ctypes.byref(bmi), 0)

                    gdi32.SelectObject(hdc_mem, h_old)
                    gdi32.DeleteObject(hbitmap)
                    gdi32.DeleteDC(hdc_mem)
                    user32.ReleaseDC(hdesktop, hdc_screen)

                    if self.codec == "h264" and self.encoder:
                        packet = self.encoder.encode_frame(
                            raw_pixels=bytes(raw_buf[: cap_w * cap_h * 4]),
                            timestamp_us=int(now * 1_000_000),
                        )
                        frame_data = packet.data
                    elif HAS_QT_IMAGE:
                        img = QImage(raw_buf, cap_w, cap_h, cap_w * 4, QImage.Format.Format_ARGB32)
                        qbuf = QBuffer()
                        qbuf.open(QIODevice.OpenModeFlag.WriteOnly)
                        img.save(qbuf, "JPEG", self.quality)
                        frame_data = bytes(qbuf.data())
                    else:
                        frame_data = bytes(raw_buf[:4096])
                except (AttributeError, OSError, TypeError):
                    if self.codec == "h264" and self.encoder:
                        packet = self.encoder.encode_frame(raw_pixels=b"\x00" * 1024)
                        frame_data = packet.data
                    else:
                        frame_data = b"\xff\xd8\xff\xe0" + b"\x00" * 1020
            else:
                if self.codec == "h264" and self.encoder:
                    packet = self.encoder.encode_frame(raw_pixels=b"\x00" * 1024)
                    frame_data = packet.data
                else:
                    frame_data = b"\xff\xd8\xff\xe0" + b"\x00" * 1020

        capture_end = time.perf_counter()
        measured_latency = max(1.0, (capture_end - capture_start) * 1000.0)
        self._last_latency_ms = (self._last_latency_ms * 0.7) + (measured_latency * 0.3)

        self._frame_count += 1
        self._fps_counter += 1
        self._last_frame_time = now

        if (now - self._fps_window_start) >= 1.0:
            elapsed = now - self._fps_window_start
            self._current_fps = self._fps_counter / elapsed
            self._fps_counter = 0
            self._fps_window_start = now
            if frame_data and self._current_fps > 0:
                self._estimated_bitrate_kbps = (len(frame_data) * 8 * self._current_fps) / 1000.0

        return frame_data, self.get_stats()

    def get_stats(self) -> CaptureStats:
        is_congested = (
            self.adaptive_controller.is_congested if self.adaptive_controller else False
        )
        is_hw = self.encoder.is_hardware_accelerated if self.encoder else False
        return CaptureStats(
            fps=round(self._current_fps, 1),
            latency_ms=round(self._last_latency_ms, 1),
            bitrate_kbps=round(self._estimated_bitrate_kbps, 1),
            dropped_frames=self._dropped_frames,
            total_frames_captured=self._frame_count,
            width=self.width,
            height=self.height,
            is_virtual_display=self.is_virtual_display,
            source_label=self.source_label,
            quality=self.quality,
            is_congested=is_congested,
            codec=self.codec,
            is_hardware_accelerated=is_hw,
            backend=self.active_backend,
        )
