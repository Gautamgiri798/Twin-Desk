from __future__ import annotations

import ctypes
import platform

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
    Guarantees coordinate bounds clamping, release-all synthesis, and safe non-Windows fallback.
    """

    def __init__(
        self,
        display_width: int = 1920,
        display_height: int = 1080,
        enabled: bool = True,
    ) -> None:
        self.display_width = display_width
        self.display_height = display_height
        self.enabled = enabled
        self._is_windows = platform.system() == "Windows"

    def update_bounds(self, width: int, height: int) -> None:
        self.display_width = max(1, width)
        self.display_height = max(1, height)

    def inject_pointer(self, x: float, y: float) -> bool:
        """Moves cursor to coordinates clamped to the target display boundary."""
        if not self.enabled or not self._is_windows:
            return True

        clamped_x = max(0.0, min(float(self.display_width), x))
        clamped_y = max(0.0, min(float(self.display_height), y))

        try:
            user32 = ctypes.windll.user32
            norm_x = int((clamped_x / max(1, self.display_width)) * 65535)
            norm_y = int((clamped_y / max(1, self.display_height)) * 65535)
            # MOUSEEVENTF_MOVE (0x0001) | MOUSEEVENTF_ABSOLUTE (0x8000)
            user32.mouse_event(0x8001, norm_x, norm_y, 0, 0)
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
