from __future__ import annotations

import subprocess
from pathlib import Path


def test_driver_build_script_exists_and_declares_parameters():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "build_driver.ps1"
    assert script_path.exists(), "scripts/build_driver.ps1 must exist"

    content = script_path.read_text(encoding="utf-8")
    assert "[ValidateSet(\"Release\", \"Debug\")]" in content
    assert "[ValidateSet(\"x64\", \"ARM64\")]" in content
    assert "[switch]$BuildOnly" in content
    assert "[switch]$SignOnly" in content
    assert "[switch]$Install" in content
    assert "[switch]$DryRun" in content
    assert "Root\\DualDeskDisplay" in content
    assert "IddDriver.inf" in content


def test_driver_installation_documentation_exists():
    repo_root = Path(__file__).resolve().parent.parent
    doc_path = repo_root / "docs" / "driver-installation.md"
    assert doc_path.exists(), "docs/driver-installation.md must exist"

    doc_text = doc_path.read_text(encoding="utf-8")
    assert "Windows Indirect Display Driver (IDD)" in doc_text
    assert "Prerequisites" in doc_text
    assert "bcdedit.exe /set testsigning on" in doc_text
    assert "devcon.exe install" in doc_text
    assert "Root\\DualDeskDisplay" in doc_text
    assert "pnputil.exe" in doc_text


def test_driver_build_script_dry_run_execution():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "build_driver.ps1"

    # Execute dry run via PowerShell
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-DryRun",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, f"Dry run failed with code {proc.returncode}: {proc.stderr}"
    output = proc.stdout
    assert "[DualDesk Driver Build] Resolving project structure..." in output
    assert "[DualDesk Driver Build] Detecting Visual Studio & CMake..." in output
    assert "[DRY RUN] Summary of planned actions:" in output
    assert "[OK] [DRY RUN] Completed successfully" in output
