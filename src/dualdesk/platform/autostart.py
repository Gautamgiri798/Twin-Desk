from __future__ import annotations

import platform
import sys

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_auto_start_enabled(app_name: str = "DualDesk") -> bool:
    """
    Checks whether DualDesk is registered to run on user login in Windows registry HKCU.
    Returns False on non-Windows platforms or if key does not exist.
    """
    if not is_windows():
        return False

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            try:
                _val, _type = winreg.QueryValueEx(key, app_name)
                return True
            except FileNotFoundError:
                return False
    except (OSError, PermissionError):
        return False


def set_auto_start(
    enabled: bool,
    app_name: str = "DualDesk",
    exec_path: str | None = None,
) -> bool:
    """
    Adds or removes the application from the Windows HKCU Run registry key.
    Safe and non-destructive: only touches the specified app_name key in HKCU.
    """
    if not is_windows():
        return False

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ
        ) as key:
            if enabled:
                target_cmd = exec_path or f'"{sys.executable}" -m dualdesk --minimized'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, target_cmd)
                return True
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
                return True
    except (OSError, PermissionError):
        return False
