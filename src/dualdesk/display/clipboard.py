from __future__ import annotations

import ctypes
import platform
import threading
import time
from collections.abc import Callable

from dualdesk.security.clipboard_guard import ClipboardGuard

# Win32 Clipboard Formats
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


class ClipboardAdapter:
    """
    Cross-platform clipboard adapter with echo-loop suppression.
    Supports Qt QApplication.clipboard() when available, Win32 ctypes clipboard
    access on Windows, and thread-safe fallback buffer in headless/test environments.
    """

    def __init__(self, on_change: Callable[[str], None] | None = None) -> None:
        self.on_change = on_change
        self._last_sent_hash: str | None = None
        self._last_received_hash: str | None = None
        self._in_memory_text: str = ""
        self._is_windows = platform.system() == "Windows"
        self._monitor_thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

    def get_text(self) -> str:
        """Retrieves current clipboard text from Qt, Win32, or fallback buffer."""
        # 1. Try Qt if QApplication exists
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None:
                cb = app.clipboard()
                if cb is not None:
                    return cb.text() or ""
        except (ImportError, RuntimeError):
            pass

        # 2. Try Win32 ctypes
        if self._is_windows:
            try:
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                if user32.OpenClipboard(None):
                    try:
                        handle = user32.GetClipboardData(CF_UNICODETEXT)
                        if handle:
                            ptr = kernel32.GlobalLock(handle)
                            if ptr:
                                try:
                                    return str(ctypes.c_wchar_p(ptr).value or "")
                                finally:
                                    kernel32.GlobalUnlock(handle)
                    finally:
                        user32.CloseClipboard()
            except (AttributeError, OSError):
                pass

        with self._lock:
            return self._in_memory_text

    def set_text(self, text: str) -> bool:
        """Sets clipboard text locally and records hash to suppress echo feedback loops."""
        text_hash = ClipboardGuard.hash_text(text)
        with self._lock:
            self._last_received_hash = text_hash
            self._in_memory_text = text

        success = True

        # 1. Try Qt if QApplication exists
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None:
                cb = app.clipboard()
                if cb is not None:
                    cb.setText(text)
                    return True
        except (ImportError, RuntimeError):
            pass

        # 2. Try Win32 ctypes
        if self._is_windows:
            try:
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                if user32.OpenClipboard(None):
                    try:
                        user32.EmptyClipboard()
                        encoded = text.encode("utf-16le") + b"\x00\x00"
                        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
                        if h_mem:
                            ptr = kernel32.GlobalLock(h_mem)
                            if ptr:
                                ctypes.memmove(ptr, encoded, len(encoded))
                                kernel32.GlobalUnlock(h_mem)
                                user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                    finally:
                        user32.CloseClipboard()
            except (AttributeError, OSError):
                success = False

        return success

    def check_for_updates(self) -> str | None:
        """
        Inspects current clipboard text and returns it only if it is genuinely new local content
        (i.e. not echoing remote content and not already sent).
        """
        current_text = self.get_text()
        if not current_text:
            return None

        current_hash = ClipboardGuard.hash_text(current_text)
        with self._lock:
            if current_hash == self._last_received_hash:
                # Echo suppression: this content originated from the remote peer
                return None
            if current_hash == self._last_sent_hash:
                # Content already sent previously
                return None

            self._last_sent_hash = current_hash
            return current_text

    def start_monitoring(self, poll_interval_s: float = 0.5) -> None:
        """Starts background poll thread to notify on local clipboard modifications."""
        with self._lock:
            if self._running:
                return
            self._running = True
            # Pre-seed hash to avoid broadcasting existing clipboard on startup
            current = self.get_text()
            if current:
                self._last_sent_hash = ClipboardGuard.hash_text(current)

        def _poll_loop() -> None:
            while True:
                with self._lock:
                    if not self._running:
                        break
                new_text = self.check_for_updates()
                if new_text is not None and self.on_change:
                    try:
                        self.on_change(new_text)
                    except (RuntimeError, OSError, ValueError):
                        continue
                time.sleep(poll_interval_s)

        self._monitor_thread = threading.Thread(
            target=_poll_loop, name="ClipboardMonitorThread", daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stops background poll thread."""
        with self._lock:
            self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None
