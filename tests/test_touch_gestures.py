from __future__ import annotations

import pytest

from dualdesk.display.input_injector import InputInjector
from dualdesk.protocol.models import (
    ErrorCode,
    GesturePayload,
    GestureType,
    MessageEnvelope,
    MessageType,
    ProtocolError,
    TouchAction,
    TouchPayload,
    TouchPoint,
)
from dualdesk.security.input_filter import InputFilter


def test_touch_and_gesture_models_serialization() -> None:
    # 1. Touch payload serialization
    touch = TouchPayload(
        action=TouchAction.DOWN.value,
        contacts=[
            TouchPoint(id=1, x=0.25, y=0.5, pressure=0.8, normalized=True),
            TouchPoint(id=2, x=0.30, y=0.55, pressure=1.0, normalized=True),
        ],
    )
    assert touch.action == "down"
    assert len(touch.contacts) == 2
    assert touch.contacts[0].id == 1

    env_touch = MessageEnvelope(
        type=MessageType.INPUT_TOUCH.value,
        session_id="test_sess",
        sequence=1,
        payload={
            "action": touch.action,
            "contacts": [
                {"id": c.id, "x": c.x, "y": c.y, "pressure": c.pressure, "normalized": c.normalized}
                for c in touch.contacts
            ],
        },
    )
    raw = env_touch.serialize()
    deserialized = MessageEnvelope.deserialize(raw)
    assert deserialized.type == MessageType.INPUT_TOUCH.value
    assert deserialized.payload["action"] == "down"
    assert len(deserialized.payload["contacts"]) == 2

    # 2. Gesture payload serialization
    gesture = GesturePayload(
        gesture=GestureType.PAN.value,
        x=0.5,
        y=0.5,
        delta_x=0.0,
        delta_y=-120.0,
        scale=1.0,
        normalized=True,
    )
    env_gesture = MessageEnvelope(
        type=MessageType.INPUT_GESTURE.value,
        session_id="test_sess",
        sequence=2,
        payload={
            "gesture": gesture.gesture,
            "x": gesture.x,
            "y": gesture.y,
            "delta_x": gesture.delta_x,
            "delta_y": gesture.delta_y,
            "scale": gesture.scale,
            "normalized": gesture.normalized,
        },
    )
    raw_g = env_gesture.serialize()
    deserialized_g = MessageEnvelope.deserialize(raw_g)
    assert deserialized_g.type == MessageType.INPUT_GESTURE.value
    assert deserialized_g.payload["gesture"] == "pan"
    assert deserialized_g.payload["delta_y"] == -120.0


def test_input_filter_touch_bounding_and_tracking() -> None:
    filt = InputFilter(session_id="sess_touch", display_width=1920, display_height=1080)

    # Down with 2 fingers out-of-bounds -> clamped
    touch_down = TouchPayload(
        action="down",
        contacts=[
            TouchPoint(id=1, x=-0.5, y=1.5, pressure=12.0, normalized=True),
            TouchPoint(id=2, x=0.5, y=0.5, pressure=-1.0, normalized=True),
        ],
    )
    sanitized = filt.process_touch(touch_down, sequence=1)
    assert sanitized.action == "down"
    assert sanitized.contacts[0].x == 0.0
    assert sanitized.contacts[0].y == 1.0
    assert sanitized.contacts[0].pressure == 10.0  # clamped to max 10.0
    assert sanitized.contacts[1].pressure == 0.0   # clamped to min 0.0
    assert filt.has_held_inputs is True

    # Move contact 1
    touch_move = TouchPayload(
        action="move",
        contacts=[TouchPoint(id=1, x=0.1, y=0.2, pressure=1.0, normalized=True)],
    )
    filt.process_touch(touch_move, sequence=2)
    assert filt.has_held_inputs is True

    # Lift contact 1
    touch_up = TouchPayload(
        action="up",
        contacts=[TouchPoint(id=1, x=0.1, y=0.2, pressure=0.0, normalized=True)],
    )
    filt.process_touch(touch_up, sequence=3)
    assert filt.has_held_inputs is True  # contact 2 still held

    # Release all
    rel = filt.release_all()
    assert rel["released_touches"] == [2]
    assert filt.has_held_inputs is False

    # Invalid touch action
    with pytest.raises(ProtocolError) as exc_info:
        filt.process_touch(TouchPayload(action="fly"), sequence=4)
    assert exc_info.value.code == ErrorCode.INPUT_REJECTED

    # Too many contacts (>10)
    many_contacts = [TouchPoint(id=i, x=0.5, y=0.5) for i in range(12)]
    with pytest.raises(ProtocolError):
        filt.process_touch(TouchPayload(action="down", contacts=many_contacts), sequence=5)


def test_input_filter_gesture_sanitization() -> None:
    filt = InputFilter(session_id="sess_gesture", display_width=1920, display_height=1080)

    # Pan gesture with excessive delta -> clamped to +-10000
    pan = GesturePayload(
        gesture="pan",
        x=0.5,
        y=0.5,
        delta_x=25000.0,
        delta_y=-99999.0,
        scale=1.0,
        normalized=True,
    )
    sanitized = filt.process_gesture(pan, sequence=1)
    assert sanitized.gesture == "pan"
    assert sanitized.delta_x == 10000.0
    assert sanitized.delta_y == -10000.0

    # Pinch gesture with extreme scale
    pinch = GesturePayload(
        gesture="pinch",
        x=0.5,
        y=0.5,
        scale=999.0,
        normalized=True,
    )
    sanitized_pinch = filt.process_gesture(pinch, sequence=2)
    assert sanitized_pinch.scale == 100.0

    # Unsupported gesture
    with pytest.raises(ProtocolError):
        filt.process_gesture(GesturePayload(gesture="swirl", x=0.0, y=0.0), sequence=3)


def test_input_injector_gestures_and_scroll() -> None:
    injector = InputInjector(display_width=1920, display_height=1080, enabled=True)

    # 1. Scroll injection
    assert injector.inject_scroll(delta_x=0.0, delta_y=120.0) is True
    assert injector.inject_scroll(delta_x=-120.0, delta_y=0.0) is True

    # 2. Gesture injection: pan
    pan_g = GesturePayload(gesture="pan", x=0.5, y=0.5, delta_y=-120.0)
    assert injector.inject_gesture(pan_g) is True

    # 3. Gesture injection: tap
    tap_g = GesturePayload(gesture="tap", x=0.5, y=0.5, normalized=True)
    assert injector.inject_gesture(tap_g) is True

    # 4. Gesture injection: double_tap
    dtap_g = GesturePayload(gesture="double_tap", x=0.5, y=0.5, normalized=True)
    assert injector.inject_gesture(dtap_g) is True

    # 5. Gesture injection: two_finger_tap
    r_tap = GesturePayload(gesture="two_finger_tap", x=0.5, y=0.5, normalized=True)
    assert injector.inject_gesture(r_tap) is True

    # 6. Gesture injection: pinch zoom in and zoom out
    pinch_in = GesturePayload(gesture="pinch", x=0.5, y=0.5, scale=1.5, normalized=True)
    assert injector.inject_gesture(pinch_in) is True

    pinch_out = GesturePayload(gesture="pinch", x=0.5, y=0.5, scale=0.7, normalized=True)
    assert injector.inject_gesture(pinch_out) is True

    # 7. Touch injection: down, move, up
    touch_down = TouchPayload(action="down", contacts=[TouchPoint(id=0, x=0.4, y=0.4, normalized=True)])
    assert injector.inject_touch(touch_down) is True

    touch_move = TouchPayload(action="move", contacts=[TouchPoint(id=0, x=0.45, y=0.45, normalized=True)])
    assert injector.inject_touch(touch_move) is True

    touch_up = TouchPayload(action="up", contacts=[TouchPoint(id=0, x=0.45, y=0.45, normalized=True)])
    assert injector.inject_touch(touch_up) is True

    # Release all
    injector.release_all(touches=[0])


def test_connection_manager_touch_and_gesture_handling() -> None:
    import tempfile
    from pathlib import Path

    from dualdesk.network.transport import ConnectionManager, ConnectionState
    from dualdesk.security.pairing import PairingManager
    from dualdesk.storage.db import DualDeskDB

    with tempfile.TemporaryDirectory() as tmp_dir:
        db = DualDeskDB(Path(tmp_dir) / "cm_touch.db")
        pm = PairingManager(db, local_fingerprint="SHA256:LOCAL")
        cm = ConnectionManager(db=db, pairing_manager=pm, role="host")

        # Must reject when not STREAMING
        with pytest.raises(ProtocolError):
            cm.handle_incoming_touch(TouchPayload(action="down"), sequence=1)

        with pytest.raises(ProtocolError):
            cm.handle_incoming_gesture(GesturePayload(gesture="pan", x=0.5, y=0.5), sequence=1)

        # Set active streaming state with input filter and injector
        cm.set_state(ConnectionState.STREAMING)
        cm.input_filter = InputFilter("sess_cm", 1920, 1080)
        cm.input_injector = InputInjector(1920, 1080, enabled=True)

        res_touch = cm.handle_incoming_touch(
            TouchPayload(
                action="down",
                contacts=[TouchPoint(id=1, x=0.5, y=0.5, normalized=True)],
            ),
            sequence=1,
        )
        assert res_touch is not None
        assert res_touch.action == "down"

        res_gesture = cm.handle_incoming_gesture(
            GesturePayload(gesture="pan", x=0.5, y=0.5, delta_y=-120.0),
            sequence=2,
        )
        assert res_gesture is not None
        assert res_gesture.gesture == "pan"

        db.close()


def test_stream_viewer_wheel_event(qapp) -> None:
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
    from PySide6.QtGui import QWheelEvent

    from dualdesk.network.transport import ConnectionManager
    from dualdesk.security.pairing import PairingManager
    from dualdesk.storage.db import DualDeskDB
    from dualdesk.ui.viewer import StreamViewerWidget

    with tempfile.TemporaryDirectory() as tmp_dir:
        db = DualDeskDB(Path(tmp_dir) / "viewer_wheel.db")
        pm = PairingManager(db, local_fingerprint="SHA256:VIEWER")
        cm = ConnectionManager(db=db, pairing_manager=pm, role="client")

        sent_gestures: list[dict] = []

        def mock_send_gesture(gesture, x, y, delta_x=0.0, delta_y=0.0, scale=1.0, normalized=True):
            sent_gestures.append({
                "gesture": gesture,
                "x": x,
                "y": y,
                "delta_x": delta_x,
                "delta_y": delta_y,
                "scale": scale,
                "normalized": normalized,
            })

        cm.send_gesture = mock_send_gesture  # type: ignore

        viewer = StreamViewerWidget(cm)
        viewer.resize(800, 600)
        viewer._render_rect = QRectF(0, 0, 800, 600)

        # Create QWheelEvent: vertical delta = 120 (one wheel notch)
        pos = QPointF(400, 300)
        global_pos = QPointF(400, 300)
        pixel_delta = QPoint(0, 0)
        angle_delta = QPoint(0, 120)

        wheel_ev = QWheelEvent(
            pos,
            global_pos,
            pixel_delta,
            angle_delta,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )

        viewer.wheelEvent(wheel_ev)
        assert len(sent_gestures) == 1
        assert sent_gestures[0]["gesture"] == "pan"
        assert sent_gestures[0]["delta_y"] == 120.0
        assert sent_gestures[0]["x"] == 0.5
        assert sent_gestures[0]["y"] == 0.5

        db.close()

