from __future__ import annotations

import ctypes
import math
import platform
from dataclasses import dataclass, field


@dataclass
class DisplayGeometry:
    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080
    is_primary: bool = False
    device_name: str = "VirtualDisplay"

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def contains(self, px: float, py: float) -> bool:
        left, top, right, bottom = self.bounds
        return left <= px <= right and top <= py <= bottom


@dataclass
class VirtualDesktopLayout:
    displays: list[DisplayGeometry] = field(default_factory=list)
    virtual_x: int = 0
    virtual_y: int = 0
    virtual_width: int = 1920
    virtual_height: int = 1080
    edge_resistance_px: float = 12.0

    @classmethod
    def from_system_metrics(
        cls,
        virtual_width: int | None = None,
        virtual_height: int | None = None,
        secondary_width: int = 1920,
        secondary_height: int = 1080,
    ) -> VirtualDesktopLayout:
        """
        Constructs multimonitor layout using Windows GetSystemMetrics
        or provided geometry overrides for virtual extended displays.
        """
        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                # SM_XVIRTUALSCREEN = 76, SM_YVIRTUALSCREEN = 77
                # SM_CXVIRTUALSCREEN = 78, SM_CYVIRTUALSCREEN = 79
                # SM_CXSCREEN = 0, SM_CYSCREEN = 1
                vx = user32.GetSystemMetrics(76)
                vy = user32.GetSystemMetrics(77)
                vw = user32.GetSystemMetrics(78)
                vh = user32.GetSystemMetrics(79)
                pri_w = user32.GetSystemMetrics(0)
                pri_h = user32.GetSystemMetrics(1)

                primary = DisplayGeometry(
                    x=0,
                    y=0,
                    width=pri_w or 1920,
                    height=pri_h or 1080,
                    is_primary=True,
                    device_name="PrimaryDisplay",
                )

                # Secondary display positioned to the right of primary monitor
                sec_x = pri_w or 1920
                secondary = DisplayGeometry(
                    x=sec_x,
                    y=0,
                    width=secondary_width,
                    height=secondary_height,
                    is_primary=False,
                    device_name="SecondaryVirtualDisplay",
                )

                total_vw = max(vw or (pri_w + secondary_width), pri_w + secondary_width)
                total_vh = max(vh or max(pri_h, secondary_height), max(pri_h, secondary_height))

                return cls(
                    displays=[primary, secondary],
                    virtual_x=vx or 0,
                    virtual_y=vy or 0,
                    virtual_width=total_vw,
                    virtual_height=total_vh,
                )
            except (AttributeError, OSError):
                pass

        # Fallback layout: Primary 1920x1080 at (0,0) + Secondary 1920x1080 at (1920,0)
        pri = DisplayGeometry(0, 0, 1920, 1080, is_primary=True, device_name="Primary")
        sec = DisplayGeometry(1920, 0, secondary_width, secondary_height, is_primary=False, device_name="Secondary")
        return cls(
            displays=[pri, sec],
            virtual_x=0,
            virtual_y=0,
            virtual_width=1920 + secondary_width,
            virtual_height=max(1080, secondary_height),
        )

    def get_target_display(self, index: int = -1) -> DisplayGeometry:
        if not self.displays:
            return DisplayGeometry(0, 0, 1920, 1080, True)
        if index < 0 or index >= len(self.displays):
            # Default to the non-primary extended display
            for d in self.displays:
                if not d.is_primary:
                    return d
            return self.displays[-1]
        return self.displays[index]

    def map_client_to_virtual_desktop(
        self,
        norm_x: float,
        norm_y: float,
        display_index: int = -1,
    ) -> tuple[int, int]:
        """
        Maps normalized (0.0 to 1.0) client coordinates from the target secondary display
        into global Windows virtual desktop screen coordinates.
        """
        target = self.get_target_display(display_index)
        clamped_nx = max(0.0, min(1.0, float(norm_x)))
        clamped_ny = max(0.0, min(1.0, float(norm_y)))

        gx = int(target.x + (clamped_nx * target.width))
        gy = int(target.y + (clamped_ny * target.height))
        return gx, gy

    def apply_edge_resistance(
        self,
        current_x: float,
        current_y: float,
        target_x: float,
        target_y: float,
        from_display_index: int = -1,
    ) -> tuple[float, float]:
        """
        Applies edge resistance when transitioning near display boundaries,
        preventing erratic cursor slipping across the screen seam.
        """
        from_disp = self.get_target_display(from_display_index)
        left, top, right, bottom = from_disp.bounds

        # If staying inside the current display, no resistance needed
        if left <= target_x <= right and top <= target_y <= bottom:
            return target_x, target_y

        # Crossing left boundary
        if target_x < left:
            delta = left - target_x
            if delta < self.edge_resistance_px:
                target_x = left

        # Crossing right boundary
        elif target_x > right:
            delta = target_x - right
            if delta < self.edge_resistance_px:
                target_x = right

        # Crossing top boundary
        if target_y < top:
            delta = top - target_y
            if delta < self.edge_resistance_px:
                target_y = top

        # Crossing bottom boundary
        elif target_y > bottom:
            delta = target_y - bottom
            if delta < self.edge_resistance_px:
                target_y = bottom

        return target_x, target_y


class CursorWarpController:
    """
    Normalizes cursor ballistics, sensitivity, and relative motion scaling
    for smooth remote touch, trackpad, and mouse inputs.
    """

    def __init__(
        self,
        sensitivity: float = 1.0,
        smoothing_factor: float = 0.35,
    ) -> None:
        self.sensitivity = max(0.1, min(5.0, sensitivity))
        self.smoothing_factor = max(0.0, min(1.0, smoothing_factor))
        self._last_position: tuple[float, float] | None = None

    def apply_relative_motion(
        self,
        current_x: float,
        current_y: float,
        dx: float,
        dy: float,
    ) -> tuple[float, float]:
        """
        Applies sensitivity scaling and acceleration curve to relative motion deltas.
        """
        magnitude = math.hypot(dx, dy)
        # Power-law acceleration curve for low-speed precision and high-speed flicking
        accel = 1.0 + (min(magnitude, 50.0) / 50.0) * 0.5
        scaled_dx = dx * self.sensitivity * accel
        scaled_dy = dy * self.sensitivity * accel
        return current_x + scaled_dx, current_y + scaled_dy

    def smooth_position(
        self,
        new_pos: tuple[float, float],
    ) -> tuple[float, float]:
        """
        Filters jittery touch/trackpad inputs using exponential moving average.
        """
        if self._last_position is None or self.smoothing_factor <= 0.0:
            self._last_position = new_pos
            return new_pos

        alpha = 1.0 - self.smoothing_factor
        sx = (self._last_position[0] * self.smoothing_factor) + (new_pos[0] * alpha)
        sy = (self._last_position[1] * self.smoothing_factor) + (new_pos[1] * alpha)
        self._last_position = (sx, sy)
        return sx, sy

    def reset(self) -> None:
        self._last_position = None
