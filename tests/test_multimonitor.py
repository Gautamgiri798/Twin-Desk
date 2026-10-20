from __future__ import annotations

from dualdesk.display.input_injector import InputInjector
from dualdesk.display.multimonitor import (
    CursorWarpController,
    DisplayGeometry,
    VirtualDesktopLayout,
    enable_per_monitor_dpi_awareness,
    get_dpi_for_point,
    scale_coordinate_between_displays,
)


def test_display_geometry() -> None:
    disp = DisplayGeometry(x=1920, y=0, width=1920, height=1080, is_primary=False)
    assert disp.bounds == (1920, 0, 3840, 1080)
    assert disp.contains(2000, 500) is True
    assert disp.contains(1920, 0) is True
    assert disp.contains(3840, 1080) is True
    assert disp.contains(100, 100) is False
    assert disp.contains(4000, 500) is False


def test_virtual_desktop_layout_mapping() -> None:
    pri = DisplayGeometry(0, 0, 1920, 1080, is_primary=True, device_name="Primary")
    sec = DisplayGeometry(1920, 0, 1920, 1080, is_primary=False, device_name="Secondary")
    layout = VirtualDesktopLayout(
        displays=[pri, sec],
        virtual_x=0,
        virtual_y=0,
        virtual_width=3840,
        virtual_height=1080,
    )

    # Secondary display origin (top-left)
    gx, gy = layout.map_client_to_virtual_desktop(0.0, 0.0)
    assert gx == 1920
    assert gy == 0

    # Center of secondary display
    gx, gy = layout.map_client_to_virtual_desktop(0.5, 0.5)
    assert gx == 2880
    assert gy == 540

    # Bottom-right of secondary display
    gx, gy = layout.map_client_to_virtual_desktop(1.0, 1.0)
    assert gx == 3840
    assert gy == 1080

    # Out-of-bounds clamping
    gx, gy = layout.map_client_to_virtual_desktop(-0.5, 2.0)
    assert gx == 1920
    assert gy == 1080


def test_edge_resistance() -> None:
    sec = DisplayGeometry(1920, 0, 1920, 1080, is_primary=False)
    layout = VirtualDesktopLayout(
        displays=[sec],
        edge_resistance_px=15.0,
    )

    # In-bounds movement -> unchanged
    tx, ty = layout.apply_edge_resistance(2000, 500, 2010, 510)
    assert tx == 2010
    assert ty == 510

    # Small movement past left edge (within 15px threshold) -> clamped to edge 1920
    tx, ty = layout.apply_edge_resistance(1925, 500, 1915, 500)
    assert tx == 1920
    assert ty == 500

    # Large movement past left edge (exceeding 15px threshold) -> breaks through
    tx, ty = layout.apply_edge_resistance(1925, 500, 1890, 500)
    assert tx == 1890
    assert ty == 500


def test_cursor_warp_controller() -> None:
    warp = CursorWarpController(sensitivity=1.5, smoothing_factor=0.5)

    # Relative motion
    nx, ny = warp.apply_relative_motion(100.0, 200.0, 10.0, -10.0)
    assert nx > 100.0
    assert ny < 200.0

    # Smoothing position
    pos1 = warp.smooth_position((500.0, 500.0))
    assert pos1 == (500.0, 500.0)

    # Next jittery position should be filtered towards 500.0
    pos2 = warp.smooth_position((600.0, 600.0))
    assert 500.0 < pos2[0] < 600.0
    assert 500.0 < pos2[1] < 600.0

    warp.reset()
    assert warp._last_position is None


def test_input_injector_multimonitor() -> None:
    pri = DisplayGeometry(0, 0, 1920, 1080, is_primary=True)
    sec = DisplayGeometry(1920, 0, 1920, 1080, is_primary=False)
    layout = VirtualDesktopLayout(
        displays=[pri, sec],
        virtual_x=0,
        virtual_y=0,
        virtual_width=3840,
        virtual_height=1080,
    )
    injector = InputInjector(
        display_width=1920,
        display_height=1080,
        layout=layout,
        enabled=True,
    )

    # Normalized coordinate injection
    ok_norm = injector.inject_pointer(0.5, 0.5, normalized=True)
    assert ok_norm is True
    assert injector.last_cursor_pos[0] == 2880.0
    assert injector.last_cursor_pos[1] == 540.0

    # Relative delta injection
    ok_rel = injector.inject_pointer(20.0, -10.0, relative=True)
    assert ok_rel is True
    assert injector.last_cursor_pos[0] > 2880.0

    # Bounds update updates layout
    injector.update_bounds(2560, 1440)
    assert injector.display_width == 2560
    assert injector.display_height == 1440


def test_mixed_dpi_scale_factors() -> None:
    d1 = DisplayGeometry(width=1920, height=1080, dpi_x=96, dpi_y=96)
    assert d1.scale_factor_x == 1.0
    assert d1.scale_factor_y == 1.0

    d2 = DisplayGeometry(width=1920, height=1080, dpi_x=144, dpi_y=144)
    assert d2.scale_factor_x == 1.5
    assert d2.scale_factor_y == 1.5

    d3 = DisplayGeometry(width=3840, height=2160, dpi_x=192, dpi_y=192)
    assert d3.scale_factor_x == 2.0
    assert d3.scale_factor_y == 2.0


def test_scale_coordinate_between_displays() -> None:
    src = DisplayGeometry(x=0, y=0, width=1920, height=1080, dpi_x=144, dpi_y=144)
    dst = DisplayGeometry(x=1920, y=0, width=1920, height=1080, dpi_x=96, dpi_y=96)

    # Origin (0, 0) maps to destination origin (1920, 0)
    cx, cy = scale_coordinate_between_displays(0, 0, src, dst)
    assert cx == 1920.0
    assert cy == 0.0

    # Center (960, 540) maps to destination center (2880, 540)
    cx, cy = scale_coordinate_between_displays(960, 540, src, dst)
    assert cx == 2880.0
    assert cy == 540.0


def test_enable_per_monitor_dpi_awareness() -> None:
    # Must execute safely on host OS without raising exceptions
    res = enable_per_monitor_dpi_awareness()
    assert isinstance(res, bool)


def test_get_dpi_for_point() -> None:
    dx, dy = get_dpi_for_point(100, 100)
    assert dx >= 96
    assert dy >= 96

