from __future__ import annotations

from PySide6.QtGui import QCloseEvent

from dualdesk.network.transport import ConnectionState
from dualdesk.platform.autostart import is_auto_start_enabled, is_windows, set_auto_start
from dualdesk.ui.app import DualDeskApp
from dualdesk.ui.components import create_tray_icon


def test_create_tray_icon(qapp) -> None:
    icon_inactive = create_tray_icon("inactive")
    assert not icon_inactive.isNull()

    icon_streaming = create_tray_icon("streaming")
    assert not icon_streaming.isNull()

    icon_connecting = create_tray_icon("connecting")
    assert not icon_connecting.isNull()


def test_autostart_helper_safety() -> None:
    # Query auto start status safely
    enabled = is_auto_start_enabled("DualDeskTestNonExistent")
    assert isinstance(enabled, bool)
    assert enabled is False

    # Dry set / clean remove of test key
    if is_windows():
        res = set_auto_start(False, app_name="DualDeskTestNonExistent")
        assert isinstance(res, bool)


def test_dualdesk_ui_system_tray_and_close_to_tray(qapp) -> None:
    window = DualDeskApp()
    try:
        assert hasattr(window, "tray_icon")
        assert window.tray_icon.isVisible()
        assert hasattr(window, "chk_minimize_to_tray")
        assert hasattr(window, "chk_auto_start")
        assert window.chk_minimize_to_tray.isChecked() is True

        # Test state change updates tray icon and labels
        window._on_connection_state_changed(ConnectionState.STREAMING, "Session active")
        assert "Streaming" in window.tray_status_action.text()
        assert "Disconnect" in window.tray_connect_action.text()

        window._on_connection_state_changed(ConnectionState.DISCONNECTED, "Peer disconnected")
        assert "Disconnected" in window.tray_status_action.text()
        assert "Start Session" in window.tray_connect_action.text()

        # Test close-to-tray behavior (event ignored, window hidden, active session preserved)
        close_ev = QCloseEvent()
        window.closeEvent(close_ev)
        assert close_ev.isAccepted() is False
        assert window.isHidden() is True

        # Show from tray
        window._show_from_tray()
        assert window.isVisible() is True

        # Force quit allows window to close
        quit_ev = QCloseEvent()
        window._force_quit = True
        window.closeEvent(quit_ev)
        assert quit_ev.isAccepted() is True
    finally:
        window.close()
