from __future__ import annotations

import os

# Ensure headless offscreen platform for automated tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from dualdesk.ui.app import DualDeskApp


def test_dualdesk_ui_initialization(qapp):
    window = DualDeskApp()
    assert window.windowTitle().startswith("DualDesk")
    assert window.stack.count() == 7  # 7 main views: Dashboard, Devices, Display, Stream View, Performance, Diagnostics, Settings

    # Check page switching
    window._switch_page(1)
    assert window.stack.currentIndex() == 1

    window._switch_page(3)
    assert window.stack.currentIndex() == 3

    window._switch_page(5)
    assert window.stack.currentIndex() == 5

    window._switch_page(0)
    assert window.stack.currentIndex() == 0

    # Ensure status cards exist and display proper text
    assert window.card_conn.title_label.text() == "CONNECTION"
    assert window.card_driver.title_label.text() == "VIRTUAL DISPLAY"
    assert window.notice.text_label.text().startswith("Screen Preview Prototype")

    # Clean close
    window.close()
