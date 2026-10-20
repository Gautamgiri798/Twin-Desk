from __future__ import annotations

import os

import pytest

# Ensure headless offscreen platform for automated tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from dualdesk.ui.app import DualDeskApp


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dualdesk_ui_initialization(qapp):
    window = DualDeskApp()
    assert window.windowTitle().startswith("DualDesk")
    assert window.stack.count() == 6  # 6 main views: Dashboard, Devices, Display, Performance, Diagnostics, Settings

    # Check page switching
    window._switch_page(1)
    assert window.stack.currentIndex() == 1

    window._switch_page(4)
    assert window.stack.currentIndex() == 4

    window._switch_page(0)
    assert window.stack.currentIndex() == 0

    # Ensure status cards exist and display proper text
    assert window.card_conn.title_label.text() == "CONNECTION"
    assert window.card_driver.title_label.text() == "VIRTUAL DISPLAY"
    assert window.notice.text_label.text().startswith("Screen Preview Prototype")

    # Clean close
    window.close()
