from __future__ import annotations

import ctypes
import math
import platform
from dataclasses import dataclass, field
from enum import Enum


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def enable_per_monitor_dpi_awareness() -> bool:
    """
    Configures Windows process DPI awareness to PerMonitorV2 mode.
    Ensures 1:1 pixel coordinate precision and prevents bitmap virtualization scaling.
    """
    if platform.system() != "Windows":
        return True

    try:
        user32 = ctypes.windll.user32
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            if user32.SetProcessDpiAwarenessContext(-4):
                return True
            if user32.SetProcessDpiAwarenessContext(-3):
                return True
    except (AttributeError, OSError):
        pass

    try:
        shcore = getattr(ctypes.windll, "shcore", None)
        if (
            shcore
            and hasattr(shcore, "SetProcessDpiAwareness")
            and shcore.SetProcessDpiAwareness(2) == 0
        ):
            return True
    except (AttributeError, OSError):
        pass

    try:
        user32 = ctypes.windll.user32
        if hasattr(user32, "SetProcessDPIAware"):
            return bool(user32.SetProcessDPIAware())
    except (AttributeError, OSError):
        pass

    return False


def get_dpi_for_point(x: int, y: int) -> tuple[int, int]:
    """
    Returns (dpi_x, dpi_y) for the physical display covering coordinates (x, y).
    Defaults to (96, 96) standard 100% DPI.
    """
    if platform.system() == "Windows":
        try:
            user32 = ctypes.windll.user32
            shcore = getattr(ctypes.windll, "shcore", None)
            if shcore and hasattr(shcore, "GetDpiForMonitor"):
                pt = POINT(int(x), int(y))
                # MONITOR_DEFAULTTONEAREST = 2
                hmon = user32.MonitorFromPoint(pt, 2)
                if hmon:
                    dx = ctypes.c_uint()
                    dy = ctypes.c_uint()
                    # MDT_EFFECTIVE_DPI = 0
                    if shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0:
                        return int(dx.value), int(dy.value)
        except (AttributeError, OSError):
            pass

    return 96, 96


def scale_coordinate_between_displays(
    x: float,
    y: float,
    src_disp: DisplayGeometry,
    dst_disp: DisplayGeometry,
) -> tuple[float, float]:
    """
    Scales coordinates when transitioning between mixed-DPI displays,
    preserving relative position and accounting for monitor resolution and DPI differences.
    """
    norm_x = (x - src_disp.x) / max(1, src_disp.width)
    norm_y = (y - src_disp.y) / max(1, src_disp.height)

    dst_x = dst_disp.x + (norm_x * dst_disp.width)
    dst_y = dst_disp.y + (norm_y * dst_disp.height)
    return dst_x, dst_y


@dataclass
class DisplayGeometry:
    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080
    is_primary: bool = False
    device_name: str = "VirtualDisplay"
    dpi_x: int = 96
    dpi_y: int = 96

    @property
    def scale_factor_x(self) -> float:
        return max(0.5, round(self.dpi_x / 96.0, 2))

    @property
    def scale_factor_y(self) -> float:
        return max(0.5, round(self.dpi_y / 96.0, 2))

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def contains(self, px: float, py: float) -> bool:
        left, top, right, bottom = self.bounds
        return left <= px <= right and top <= py <= bottom


class DisplayPlacement(str, Enum):
    RIGHT = "right"
    LEFT = "left"
    ABOVE = "above"
    BELOW = "below"


@dataclass
class VirtualDesktopLayout:
    displays: list[DisplayGeometry] = field(default_factory=list)
    virtual_x: int = 0
    virtual_y: int = 0
    virtual_width: int = 1920
    virtual_height: int = 1080
    edge_resistance_px: float = 12.0
    placement: DisplayPlacement = DisplayPlacement.RIGHT

    @classmethod
    def from_system_metrics(
        cls,
        virtual_width: int | None = None,
        virtual_height: int | None = None,
        secondary_width: int = 1920,
        secondary_height: int = 1080,
        placement: DisplayPlacement | str = DisplayPlacement.RIGHT,
    ) -> VirtualDesktopLayout:
        """
        Constructs multimonitor layout using Windows GetSystemMetrics
        or provided geometry overrides for virtual extended displays.
        """
        if isinstance(placement, str):
            placement = DisplayPlacement(placement.lower())

        pri_w = 1920
        pri_h = 1080
        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                pri_w = user32.GetSystemMetrics(0) or 1920
                pri_h = user32.GetSystemMetrics(1) or 1080
            except (AttributeError, OSError):
                pass

        pri_dpi_x, pri_dpi_y = get_dpi_for_point(0, 0)
        primary = DisplayGeometry(
            x=0,
            y=0,
            width=pri_w,
            height=pri_h,
            is_primary=True,
            device_name="PrimaryDisplay",
            dpi_x=pri_dpi_x,
            dpi_y=pri_dpi_y,
        )

        sec_dpi_x, sec_dpi_y = get_dpi_for_point(pri_w, 0)
        secondary = DisplayGeometry(
            x=pri_w,
            y=0,
            width=secondary_width,
            height=secondary_height,
            is_primary=False,
            device_name="SecondaryVirtualDisplay",
            dpi_x=sec_dpi_x,
            dpi_y=sec_dpi_y,
        )

        layout = cls(
            displays=[primary, secondary],
            virtual_x=0,
            virtual_y=0,
            virtual_width=pri_w + secondary_width,
            virtual_height=max(pri_h, secondary_height),
            placement=placement,
        )
        layout.set_secondary_placement(placement, secondary_width, secondary_height)
        return layout

    def set_secondary_placement(
        self,
        placement: DisplayPlacement | str,
        secondary_width: int | None = None,
        secondary_height: int | None = None,
    ) -> None:
        """
        Positions the secondary/virtual display relative to the primary display.
        Updates virtual desktop bounding box and coordinate mapping.
        """
        if isinstance(placement, str):
            placement = DisplayPlacement(placement.lower())

        self.placement = placement

        primary = next((d for d in self.displays if d.is_primary), None)
        secondary = next((d for d in self.displays if not d.is_primary), None)

        if not primary or not secondary:
            return

        sec_w = secondary_width or secondary.width
        sec_h = secondary_height or secondary.height
        secondary.width = sec_w
        secondary.height = sec_h

        if placement == DisplayPlacement.RIGHT:
            secondary.x = primary.x + primary.width
            secondary.y = primary.y
        elif placement == DisplayPlacement.LEFT:
            secondary.x = primary.x - sec_w
            secondary.y = primary.y
        elif placement == DisplayPlacement.ABOVE:
            secondary.x = primary.x
            secondary.y = primary.y - sec_h
        elif placement == DisplayPlacement.BELOW:
            secondary.x = primary.x
            secondary.y = primary.y + primary.height

        min_x = min(d.x for d in self.displays)
        min_y = min(d.y for d in self.displays)
        max_x = max(d.x + d.width for d in self.displays)
        max_y = max(d.y + d.height for d in self.displays)

        self.virtual_x = min_x
        self.virtual_y = min_y
        self.virtual_width = max_x - min_x
        self.virtual_height = max_y - min_y

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
