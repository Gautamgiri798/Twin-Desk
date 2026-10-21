from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Ensure headless offscreen platform for automated tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from dualdesk.network.discovery import check_firewall_status
from dualdesk.ui.app import DualDeskApp


def test_firewall_script_exists_and_parameters():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "configure_firewall.ps1"
    assert script_path.exists(), "configure_firewall.ps1 must exist"

    content = script_path.read_text(encoding="utf-8")
    assert "[switch]$DryRun" in content
    assert "[switch]$CheckOnly" in content
    assert "[switch]$Remove" in content
    assert "$DiscoveryPort" in content
    assert "$ControlPort" in content
    assert "$MediaPort" in content


def test_firewall_script_dry_run_execution():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "configure_firewall.ps1"
    proc = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-DryRun"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert proc.returncode == 0, f"Dry-run failed: {proc.stderr}"
    assert "[DualDesk Firewall]" in proc.stdout


def test_firewall_script_check_only_execution():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "configure_firewall.ps1"
    proc = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-CheckOnly"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert proc.returncode == 0, f"CheckOnly failed: {proc.stderr}"
    assert "[DualDesk Firewall]" in proc.stdout


def test_check_firewall_status_function():
    status = check_firewall_status()
    assert isinstance(status.is_firewall_checked, bool)
    assert isinstance(status.is_firewall_ok, bool)
    assert isinstance(status.blocked_ports, list)
    assert isinstance(status.status_summary, str)


def test_ui_devices_page_firewall_integration(qapp):
    window = DualDeskApp()
    try:
        assert hasattr(window, "firewall_status")
        # Devices page index is 1
        window._switch_page(1)
        assert window.stack.currentIndex() == 1
    finally:
        window.close()
