from __future__ import annotations

import ctypes
import platform

from dualdesk.display.multimonitor import CursorWarpController, VirtualDesktopLayout

# Win32 Mouse Event Flags
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

# Win32 Keyboard Event Flags
KEYEVENTF_KEYUP = 0x0002


class InputInjector:
    """
    Safely injects validated and bounded mouse and keyboard events into Windows OS.
    Supports multimonitor virtual desktop coordinate normalization, cursor warping,
    edge resistance, and safe non-Windows fallback.
    """

    def __init__(
        self,
        display_width: int = 1920,
        display_height: int = 1080,
        enabled: bool = True,
        layout: VirtualDesktopLayout | None = None,
        warp_controller: CursorWarpController | None = None,
    ) -> None:
        self.display_width = display_width
        self.display_height = display_height
        self.enabled = enabled
        self._is_windows = platform.system() == "Windows"
        self.layout = layout or VirtualDesktopLayout.from_system_metrics(
            secondary_width=display_width,
            secondary_height=display_height,
        )
        self.warp_controller = warp_controller or CursorWarpController()
        self.last_cursor_pos: tuple[float, float] = (0.0, 0.0)

    def update_bounds(self, width: int, height: int) -> None:
        self.display_width = max(1, width)
        self.display_height = max(1, height)
        self.layout = VirtualDesktopLayout.from_system_metrics(
            secondary_width=self.display_width,
            secondary_height=self.display_height,
        )

    def inject_pointer(
        self,
        x: float,
        y: float,
        normalized: bool = False,
        relative: bool = False,
    ) -> bool:
        """
        Moves cursor to coordinates on the virtual desktop.
        Supports normalized (0.0..1.0), relative delta, and absolute display coordinates.
        """
        if not self.enabled or not self._is_windows:
            return True

        if relative:
            curr_x, curr_y = self.last_cursor_pos
            target_x, target_y = self.warp_controller.apply_relative_motion(curr_x, curr_y, x, y)
            smoothed_x, smoothed_y = self.warp_controller.smooth_position((target_x, target_y))
            gx, gy = int(smoothed_x), int(smoothed_y)
        elif normalized and (0.0 <= x <= 1.0) and (0.0 <= y <= 1.0):
            gx, gy = self.layout.map_client_to_virtual_desktop(x, y)
            smoothed_x, smoothed_y = self.warp_controller.smooth_position((float(gx), float(gy)))
            gx, gy = int(smoothed_x), int(smoothed_y)
        else:
            target = self.layout.get_target_display()
            clamped_x = max(0.0, min(float(self.display_width), x))
            clamped_y = max(0.0, min(float(self.display_height), y))
            gx = int(target.x + clamped_x)
            gy = int(target.y + clamped_y)

        self.last_cursor_pos = (float(gx), float(gy))

        try:
            user32 = ctypes.windll.user32
            # Primary: direct Win32 SetCursorPos
            if user32.SetCursorPos(gx, gy):
                return True

            # Fallback: mouse_event with MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK (0xC001)
            vw = max(1, self.layout.virtual_width)
            vh = max(1, self.layout.virtual_height)
            vx = self.layout.virtual_x
            vy = self.layout.virtual_y
            norm_x = int(((gx - vx) / vw) * 65535)
            norm_y = int(((gy - vy) / vh) * 65535)
            user32.mouse_event(0xC001, norm_x, norm_y, 0, 0)
            return True
        except (AttributeError, OSError):
            return False

    def inject_button(self, button: str, pressed: bool) -> bool:
        """Injects mouse button press or release."""
        if not self.enabled or not self._is_windows:
            return True

        btn = button.lower()
        if btn == "left":
            flags = MOUSEEVENTF_LEFTDOWN if pressed else MOUSEEVENTF_LEFTUP
        elif btn == "right":
            flags = MOUSEEVENTF_RIGHTDOWN if pressed else MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            flags = MOUSEEVENTF_MIDDLEDOWN if pressed else MOUSEEVENTF_MIDDLEUP
        else:
            return False

        try:
            user32 = ctypes.windll.user32
            user32.mouse_event(flags, 0, 0, 0, 0)
            return True
        except (AttributeError, OSError):
            return False

    def inject_key(self, key_code: int, pressed: bool) -> bool:
        """Injects virtual key press or release."""
        if not self.enabled or not self._is_windows:
            return True

        if key_code <= 0 or key_code > 255:
            return False

        flags = 0 if pressed else KEYEVENTF_KEYUP
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(key_code, 0, flags, 0)
            return True
        except (AttributeError, OSError):
            return False

    def release_all(self, keys: list[int] | None = None, buttons: list[str] | None = None) -> None:
        """Synthesizes release for all currently held keys and buttons."""
        if not self.enabled or not self._is_windows:
            return

        if buttons:
            for btn in buttons:
                self.inject_button(btn, pressed=False)
        else:
            for btn in ("left", "right", "middle"):
                self.inject_button(btn, pressed=False)

        if keys:
            for k in keys:
                self.inject_key(k, pressed=False)
