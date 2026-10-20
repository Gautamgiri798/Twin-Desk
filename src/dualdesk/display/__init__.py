"""DualDesk display module: virtual monitor driver detection, display mode negotiation, and screen capture."""
from dualdesk.display.capture import CaptureStats, ScreenCaptureAdapter
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
)
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
)

__all__ = [
    "CaptureStats",
    "CursorWarpController",
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
    "get_supported_modes",
    "parse_annex_b_nalus",
]
