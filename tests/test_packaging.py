from __future__ import annotations

import subprocess
from pathlib import Path


def test_inno_setup_script_structure_and_directives() -> None:
    iss_path = Path("packaging") / "dualdesk_installer.iss"
    assert iss_path.is_file(), "Inno Setup script packaging/dualdesk_installer.iss must exist"

    content = iss_path.read_text(encoding="utf-8")
    assert 'MyAppName "DualDesk"' in content
    assert 'MyAppVersion "0.1.0"' in content
    assert "PrivilegesRequired=admin" in content
    assert "ArchitecturesAllowed=x64compatible" in content
    assert "[UninstallRun]" in content
    assert "configure_firewall.ps1" in content
    assert "[UninstallDelete]" in content
    assert "InitializeSetup" in content
    assert "InitializeUninstall" in content


def test_packaging_build_script_dry_run_execution() -> None:
    script_path = Path("packaging") / "build_package.ps1"
    assert script_path.is_file(), "Packaging script packaging/build_package.ps1 must exist"

    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-DryRun",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "[DryRun] Validation successful" in result.stdout
