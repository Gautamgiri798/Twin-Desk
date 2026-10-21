"""DualDesk display module: virtual monitor driver detection, display mode negotiation, and screen capture."""
from dualdesk.display.capture import CaptureStats, ScreenCaptureAdapter
from dualdesk.display.clipboard import ClipboardAdapter
from dualdesk.display.decoder import (
    DecodedVideoFrame,
    DecoderBackend,
    VideoDecoderAdapter,
    parse_annex_b_nalus,
)
from dualdesk.display.driver import (
    DisplayDriverStatus,
    check_virtual_display_driver,
    get_supported_modes,
    negotiate_target_mode,
)
from dualdesk.display.dxgi_capture import DXGICaptureAdapter, DXGIFrame
from dualdesk.display.encoder import (
    EncodedVideoPacket,
    EncoderBackend,
    EncoderCapabilities,
    EncoderConfig,
    VideoCodec,
    VideoEncoderAdapter,
    detect_encoder_capabilities,
)
from dualdesk.display.input_injector import InputInjector
from dualdesk.display.multimonitor import (
    CursorWarpController,
    DisplayGeometry,
    VirtualDesktopLayout,
    enable_per_monitor_dpi_awareness,
    get_dpi_for_point,
    scale_coordinate_between_displays,
)

__all__ = [
    "CaptureStats",
    "ClipboardAdapter",
    "CursorWarpController",
    "DXGICaptureAdapter",
    "DXGIFrame",
    "DecodedVideoFrame",
    "DecoderBackend",
    "DisplayDriverStatus",
    "DisplayGeometry",
    "EncodedVideoPacket",
    "EncoderBackend",
    "EncoderCapabilities",
    "EncoderConfig",
    "InputInjector",
    "ScreenCaptureAdapter",
    "VideoCodec",
    "VideoDecoderAdapter",
    "VideoEncoderAdapter",
    "VirtualDesktopLayout",
    "check_virtual_display_driver",
    "detect_encoder_capabilities",
    "enable_per_monitor_dpi_awareness",
    "get_dpi_for_point",
    "get_supported_modes",
    "negotiate_target_mode",
    "parse_annex_b_nalus",
    "scale_coordinate_between_displays",
]
