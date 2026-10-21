from __future__ import annotations

import ctypes
import platform
from dataclasses import dataclass, field

from dualdesk.protocol.models import DisplayMode


@dataclass
class DisplayDriverStatus:
    is_installed: bool
    is_active: bool
    device_name: str
    status_summary: str
    detected_monitors: list[str] = field(default_factory=list)
    supported_modes: list[DisplayMode] = field(default_factory=list)


def get_supported_modes() -> list[DisplayMode]:
    """Default candidate display modes for DualDesk virtual display."""
    return [
        DisplayMode(1920, 1080, 60, "1920x1080 @ 60Hz (Full HD)"),
        DisplayMode(1920, 1080, 30, "1920x1080 @ 30Hz (Power Saver)"),
        DisplayMode(2560, 1440, 60, "2560x1440 @ 60Hz (2K QHD)"),
        DisplayMode(1280, 720, 60, "1280x720 @ 60Hz (HD 720p)"),
        DisplayMode(1366, 768, 60, "1366x768 @ 60Hz (Standard Laptop)"),
        DisplayMode(3840, 2160, 30, "3840x2160 @ 30Hz (4K UHD)"),
    ]


def negotiate_target_mode(
    requested_width: int,
    requested_height: int,
    requested_fps: int = 60,
    supported_modes: list[DisplayMode] | None = None,
) -> DisplayMode:
    """
    Selects the best matching supported display mode for a requested resolution and refresh rate.
    Picks exact match if available, or closest mode by aspect ratio, resolution Euclidean distance, and refresh rate.
    """
    modes = supported_modes or get_supported_modes()
    if not modes:
        return DisplayMode(requested_width, requested_height, requested_fps)

    # 1. Exact match
    for m in modes:
        if m.width == requested_width and m.height == requested_height and m.refresh_rate == requested_fps:
            return m

    # 2. Resolution match with closest refresh rate
    res_matches = [m for m in modes if m.width == requested_width and m.height == requested_height]
    if res_matches:
        return min(res_matches, key=lambda m: abs(m.refresh_rate - requested_fps))

    # 3. Closest resolution prioritizing aspect ratio and pixel area
    req_pixels = requested_width * requested_height
    req_aspect = requested_width / max(1, requested_height)

    def mode_distance(m: DisplayMode) -> float:
        aspect = m.width / max(1, m.height)
        aspect_penalty = abs(aspect - req_aspect) * 1000.0
        pixel_diff = abs((m.width * m.height) - req_pixels) / 1000.0
        fps_diff = abs(m.refresh_rate - requested_fps)
        return aspect_penalty + pixel_diff + fps_diff

    return min(modes, key=mode_distance)


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("DeviceName", ctypes.c_wchar * 32),
        ("DeviceString", ctypes.c_wchar * 128),
        ("StateFlags", ctypes.c_ulong),
        ("DeviceID", ctypes.c_wchar * 128),
        ("DeviceKey", ctypes.c_wchar * 128),
    ]


def check_virtual_display_driver() -> DisplayDriverStatus:
    """
    Checks for the presence of a real Windows Indirect Display Driver (IDD/IddCx)
    using Windows User32 EnumDisplayDevices API.
    """
    supported_modes = get_supported_modes()
    detected_monitors: list[str] = []
    is_idd_found = False
    idd_name = ""

    if platform.system() != "Windows":
        return DisplayDriverStatus(
            is_installed=False,
            is_active=False,
            device_name="Non-Windows OS",
            status_summary="Windows Indirect Display Driver is only supported on Windows.",
            detected_monitors=[],
            supported_modes=supported_modes,
        )

    try:
        user32 = ctypes.windll.user32
        dev = DISPLAY_DEVICEW()
        dev.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        i = 0

        # Scan display adapters
        while user32.EnumDisplayDevicesW(None, i, ctypes.byref(dev), 0):
            adapter_name = dev.DeviceString.strip()
            adapter_id = dev.DeviceID.strip()
            
            # Check for known virtual display drivers (e.g., IddSampleDriver, DualDesk, Amyuni, etc.)
            known_virtual_signatures = [
                "iddsampledriver",
                "dualdesk",
                "indirect display",
                "virtual display",
                "usb display",
            ]
            lower_str = (adapter_name + " " + adapter_id).lower()
            if any(sig in lower_str for sig in known_virtual_signatures):
                is_idd_found = True
                idd_name = adapter_name or "DualDesk Virtual Display Adapter"

            # Enumerate attached monitors for this adapter
            mon_dev = DISPLAY_DEVICEW()
            mon_dev.cb = ctypes.sizeof(DISPLAY_DEVICEW)
            mon_idx = 0
            while user32.EnumDisplayDevicesW(dev.DeviceName, mon_idx, ctypes.byref(mon_dev), 0):
                if mon_dev.DeviceString:
                    detected_monitors.append(f"{dev.DeviceName}: {mon_dev.DeviceString}")
                mon_idx += 1
            i += 1
    except (AttributeError, OSError, TypeError) as e:
        return DisplayDriverStatus(
            is_installed=False,
            is_active=False,
            device_name="Detection Error",
            status_summary=f"Failed to query Windows display devices: {e}",
            detected_monitors=[],
            supported_modes=supported_modes,
        )

    if is_idd_found:
        return DisplayDriverStatus(
            is_installed=True,
            is_active=True,
            device_name=idd_name,
            status_summary="Windows IDD virtual display driver detected and active.",
            detected_monitors=detected_monitors,
            supported_modes=supported_modes,
        )
    else:
        return DisplayDriverStatus(
            is_installed=False,
            is_active=False,
            device_name="Not installed",
            status_summary=(
                "Windows IDD/IddCx driver is not installed on this system. "
                "The application will operate in Screen Preview Prototype mode. "
                "See native/ for driver source and installation instructions."
            ),
            detected_monitors=detected_monitors,
            supported_modes=supported_modes,
        )
