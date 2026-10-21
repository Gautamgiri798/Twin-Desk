from __future__ import annotations

import os
from unittest.mock import MagicMock

# Ensure headless offscreen platform for automated tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from dualdesk.display.driver import get_supported_modes
from dualdesk.network.transport import ConnectionState
from dualdesk.protocol.models import DisplayMode
from dualdesk.ui.app import DualDeskApp


def test_ui_resolution_dropdown_populated(qapp):
    window = DualDeskApp()
    try:
        modes = get_supported_modes()
        assert window.res_combo.count() == len(modes)
        for i, m in enumerate(modes):
            data: DisplayMode = window.res_combo.itemData(i)
            assert data.width == m.width
            assert data.height == m.height
            assert data.refresh_rate == m.refresh_rate
    finally:
        window.close()


def test_ui_host_resolution_selection(qapp):
    window = DualDeskApp()
    try:
        window.role = "host"
        window.connection_manager.state = ConnectionState.STREAMING
        mock_broadcast = MagicMock(return_value=True)
        window.connection_manager.broadcast_display_mode = mock_broadcast

        # Find 2560x1440 mode index
        target_idx = -1
        for i in range(window.res_combo.count()):
            m = window.res_combo.itemData(i)
            if m.width == 2560 and m.height == 1440:
                target_idx = i
                break
        assert target_idx != -1

        window.res_combo.setCurrentIndex(target_idx)

        assert window.capture_adapter.width == 2560
        assert window.capture_adapter.height == 1440
        assert mock_broadcast.called
        called_mode = mock_broadcast.call_args[0][0]
        assert called_mode.width == 2560
        assert called_mode.height == 1440
    finally:
        window.close()


def test_ui_client_resolution_selection_requests_mode(qapp):
    window = DualDeskApp()
    try:
        window.role = "client"
        window.connection_manager.state = ConnectionState.STREAMING
        mock_request = MagicMock(return_value=True)
        window.connection_manager.request_display_mode = mock_request

        # Find 1280x720 mode index
        target_idx = -1
        for i in range(window.res_combo.count()):
            m = window.res_combo.itemData(i)
            if m.width == 1280 and m.height == 720:
                target_idx = i
                break
        assert target_idx != -1

        window.res_combo.setCurrentIndex(target_idx)

        mock_request.assert_called_once_with(1280, 720, 60)
    finally:
        window.close()


def test_ui_client_on_display_mode_negotiated_syncs_combo(qapp):
    window = DualDeskApp()
    try:
        # Reset combo to index 0 (1080p @ 60)
        window.res_combo.setCurrentIndex(0)
        assert window.res_combo.currentData().width == 1920

        # Simulate host accepting a 1280x720 @ 60 mode
        window._on_client_display_mode_negotiated(1280, 720, 60)

        current = window.res_combo.currentData()
        assert current.width == 1280
        assert current.height == 720
        assert current.refresh_rate == 60
    finally:
        window.close()


def test_ui_host_on_display_mode_changed_syncs_combo_and_capture(qapp):
    window = DualDeskApp()
    try:
        window.role = "host"
        window.res_combo.setCurrentIndex(0)

        # Remote client requests 2560x1440 @ 60
        window._on_display_mode_changed(2560, 1440, 60)

        assert window.capture_adapter.width == 2560
        assert window.capture_adapter.height == 1440
        current = window.res_combo.currentData()
        assert current.width == 2560
        assert current.height == 1440
    finally:
        window.close()
