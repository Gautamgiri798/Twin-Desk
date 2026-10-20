"""DualDesk display module: virtual monitor driver detection, display mode negotiation, and screen capture."""
from dualdesk.display.capture import CaptureStats, ScreenCaptureAdapter
from dualdesk.display.driver import (
    DisplayDriverStatus,
    check_virtual_display_driver,
    get_supported_modes,
)

__all__ = [
    "CaptureStats",
    "DisplayDriverStatus",
    "ScreenCaptureAdapter",
    "check_virtual_display_driver",
    "get_supported_modes",
]
