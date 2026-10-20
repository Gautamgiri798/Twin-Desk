from __future__ import annotations

import time
from typing import Any, ClassVar

from dualdesk.protocol.models import (
    ButtonPayload,
    ErrorCode,
    GesturePayload,
    KeyPayload,
    PointerPayload,
    ProtocolError,
    TouchPayload,
    TouchPoint,
)


class InputSecurityError(Exception):
    pass


class InputFilter:
    """Validates, bounds, rate-limits and sanitizes incoming input events for an authenticated session."""

    MAX_EVENTS_PER_SECOND = 250
    ALLOWED_BUTTONS: ClassVar[set[str]] = {"left", "right", "middle"}
    ALLOWED_TOUCH_ACTIONS: ClassVar[set[str]] = {"down", "move", "up", "cancel"}
    ALLOWED_GESTURES: ClassVar[set[str]] = {
        "pan",
        "pinch",
        "tap",
        "double_tap",
        "two_finger_tap",
    }
    MAX_TOUCH_CONTACTS = 10

    def __init__(
        self,
        session_id: str,
        display_width: int = 1920,
        display_height: int = 1080,
    ) -> None:
        self.session_id = session_id
        self.display_width = display_width
        self.display_height = display_height
        self.last_sequence = -1
        self._held_keys: set[int] = set()
        self._held_buttons: set[str] = set()
        self._active_touches: set[int] = set()
        self._rate_window_start = time.time()
        self._rate_count = 0
        self.emergency_escape_triggered = False

    def update_bounds(self, width: int, height: int) -> None:
        self.display_width = max(1, width)
        self.display_height = max(1, height)

    def _check_rate_limit(self) -> None:
        now = time.time()
        if now - self._rate_window_start > 1.0:
            self._rate_window_start = now
            self._rate_count = 0
        self._rate_count += 1
        if self._rate_count > self.MAX_EVENTS_PER_SECOND:
            raise ProtocolError(
                ErrorCode.INPUT_REJECTED, "Input rate limit exceeded (possible flood attack)"
            )

    def validate_sequence(self, sequence: int) -> None:
        if sequence <= self.last_sequence:
            raise ProtocolError(
                ErrorCode.INPUT_REJECTED,
                f"Out of order or replayed input packet: got {sequence}, expected > {self.last_sequence}",
            )
        self.last_sequence = sequence

    def process_pointer(
        self, payload: PointerPayload, sequence: int
    ) -> tuple[float, float]:
        self._check_rate_limit()
        self.validate_sequence(sequence)

        if payload.normalized:
            # Normalized 0.0 to 1.0
            x = max(0.0, min(1.0, float(payload.x))) * self.display_width
            y = max(0.0, min(1.0, float(payload.y))) * self.display_height
        else:
            # Absolute pixel coordinates, clamped to display boundary
            x = max(0.0, min(float(self.display_width), float(payload.x)))
            y = max(0.0, min(float(self.display_height), float(payload.y)))

        return x, y

    def process_button(
        self, payload: ButtonPayload, sequence: int
    ) -> tuple[str, bool]:
        self._check_rate_limit()
        self.validate_sequence(sequence)

        btn = payload.button.lower()
        if btn not in self.ALLOWED_BUTTONS:
            raise ProtocolError(ErrorCode.INPUT_REJECTED, f"Unsupported mouse button: {payload.button}")

        if payload.pressed:
            self._held_buttons.add(btn)
        else:
            self._held_buttons.discard(btn)

        return btn, payload.pressed

    def process_key(
        self, payload: KeyPayload, sequence: int
    ) -> tuple[int, str, bool]:
        self._check_rate_limit()
        self.validate_sequence(sequence)

        # Check for emergency escape sequence (e.g. key code 27 for Escape when Ctrl+Alt+Shift held)
        if payload.key_code == 27 and len(self._held_keys) >= 2:
            self.emergency_escape_triggered = True
            self.release_all()
            return payload.key_code, payload.key_name, False

        if payload.pressed:
            self._held_keys.add(payload.key_code)
        else:
            self._held_keys.discard(payload.key_code)

        return payload.key_code, payload.key_name, payload.pressed

    def process_touch(
        self, payload: TouchPayload, sequence: int
    ) -> TouchPayload:
        self._check_rate_limit()
        self.validate_sequence(sequence)

        action = payload.action.lower()
        if action not in self.ALLOWED_TOUCH_ACTIONS:
            raise ProtocolError(
                ErrorCode.INPUT_REJECTED, f"Unsupported touch action: {payload.action}"
            )

        if len(payload.contacts) > self.MAX_TOUCH_CONTACTS:
            raise ProtocolError(
                ErrorCode.INPUT_REJECTED,
                f"Too many touch contacts ({len(payload.contacts)} > {self.MAX_TOUCH_CONTACTS})",
            )

        sanitized_contacts: list[TouchPoint] = []
        for contact in payload.contacts:
            if contact.normalized:
                x = max(0.0, min(1.0, float(contact.x)))
                y = max(0.0, min(1.0, float(contact.y)))
            else:
                x = max(0.0, min(float(self.display_width), float(contact.x)))
                y = max(0.0, min(float(self.display_height), float(contact.y)))

            pressure = max(0.0, min(10.0, float(contact.pressure)))

            if action == "down":
                self._active_touches.add(contact.id)
            elif action in ("up", "cancel"):
                self._active_touches.discard(contact.id)

            sanitized_contacts.append(
                TouchPoint(
                    id=int(contact.id),
                    x=x,
                    y=y,
                    pressure=pressure,
                    normalized=contact.normalized,
                )
            )

        return TouchPayload(action=action, contacts=sanitized_contacts)

    def process_gesture(
        self, payload: GesturePayload, sequence: int
    ) -> GesturePayload:
        self._check_rate_limit()
        self.validate_sequence(sequence)

        gesture = payload.gesture.lower()
        if gesture not in self.ALLOWED_GESTURES:
            raise ProtocolError(
                ErrorCode.INPUT_REJECTED, f"Unsupported gesture type: {payload.gesture}"
            )

        if payload.normalized:
            x = max(0.0, min(1.0, float(payload.x)))
            y = max(0.0, min(1.0, float(payload.y)))
        else:
            x = max(0.0, min(float(self.display_width), float(payload.x)))
            y = max(0.0, min(float(self.display_height), float(payload.y)))

        # Guard delta bounds against numeric overflows / flood
        delta_x = max(-10000.0, min(10000.0, float(payload.delta_x)))
        delta_y = max(-10000.0, min(10000.0, float(payload.delta_y)))
        scale = max(0.01, min(100.0, float(payload.scale)))

        return GesturePayload(
            gesture=gesture,
            x=x,
            y=y,
            delta_x=delta_x,
            delta_y=delta_y,
            scale=scale,
            normalized=payload.normalized,
        )

    def release_all(self) -> dict[str, Any]:
        """Synthesizes release of all currently held keys, buttons, and active touches."""
        released_keys = list(self._held_keys)
        released_buttons = list(self._held_buttons)
        released_touches = list(self._active_touches)
        self._held_keys.clear()
        self._held_buttons.clear()
        self._active_touches.clear()
        return {
            "released_keys": released_keys,
            "released_buttons": released_buttons,
            "released_touches": released_touches,
        }

    @property
    def has_held_inputs(self) -> bool:
        return bool(self._held_keys or self._held_buttons or self._active_touches)
