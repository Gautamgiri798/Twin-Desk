from __future__ import annotations

from unittest.mock import MagicMock

from dualdesk.network.transport import ConnectionManager, ConnectionState
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB
from dualdesk.ui.viewer import ReconnectionOverlay, StreamWindow


def test_reconnection_state_and_backoff_flow() -> None:
    db = DualDeskDB(":memory:")
    pm = PairingManager(db, local_fingerprint="SHA256:LOCAL-FP")
    cm = ConnectionManager(db=db, pairing_manager=pm, role="client")

    # Configure client connection state mock
    cm.last_connected_peer_id = "host-01"
    cm.last_connected_peer_fingerprint = "SHA256:HOST-FP"
    cm.last_connected_peer_address = "127.0.0.1"
    cm.set_state(ConnectionState.STREAMING, "Active streaming")

    state_changes: list[tuple[ConnectionState, str]] = []
    cm.on_state_changed = lambda s, d: state_changes.append((s, d))

    # Simulate unexpected network drop
    cm.disconnect(reason="Socket closed unexpectedly (ECONNRESET)")

    # Verify it entered RECOVERING state
    assert cm.state == ConnectionState.RECOVERING
    assert cm._is_reconnecting is True
    assert cm.reconnect_attempt >= 1

    # Cancel reconnection
    cm.cancel_reconnect()
    assert cm.state == ConnectionState.DISCONNECTED
    assert cm._is_reconnecting is False
    db.close()


def test_reconnection_overlay_ui_widget(qapp) -> None:
    db = DualDeskDB(":memory:")
    pm = PairingManager(db, local_fingerprint="SHA256:LOCAL-FP")
    cm = ConnectionManager(db=db, pairing_manager=pm, role="client")

    overlay = ReconnectionOverlay(connection_manager=cm)
    assert overlay.isHidden()

    # Show reconnecting
    overlay.show_reconnecting(attempt=1, max_attempts=3, detail="Connection dropped. Retrying...")
    assert not overlay.isHidden()
    assert "Attempt 1/3" in overlay.msg_label.text()

    # User clicks cancel
    cancel_mock = MagicMock()
    cm.cancel_reconnect = cancel_mock
    overlay._on_cancel_clicked()
    assert cancel_mock.called
    assert overlay.isHidden()

    # StreamWindow integration
    window = StreamWindow(connection_manager=cm)
    assert hasattr(window, "reconnect_overlay")
    assert window.reconnect_overlay.isHidden()

    # Fire state changed to RECOVERING
    window._on_conn_state_changed(ConnectionState.RECOVERING, "Link timeout (Attempt 2/3)")
    assert not window.reconnect_overlay.isHidden()

    # Fire state changed to STREAMING (successful recovery)
    window._on_conn_state_changed(ConnectionState.STREAMING, "Re-established")
    assert window.reconnect_overlay.isHidden()

    window.close()
    db.close()


def test_reconnection_clean_exit_bypasses_recovery() -> None:
    db = DualDeskDB(":memory:")
    pm = PairingManager(db, local_fingerprint="SHA256:LOCAL-FP")
    cm = ConnectionManager(db=db, pairing_manager=pm, role="client")

    cm.set_state(ConnectionState.STREAMING, "Active streaming")
    cm.disconnect(reason="User disconnect")

    assert cm.state == ConnectionState.DISCONNECTED
    assert cm._is_reconnecting is False
    db.close()
