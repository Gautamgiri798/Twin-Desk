from __future__ import annotations

import re
from pathlib import Path

NATIVE_DIR = Path(__file__).resolve().parent.parent / "native"


def test_native_files_exist() -> None:
    expected_files = [
        "CMakeLists.txt",
        "capture/dxgi_compat.h",
        "capture/dxgi_capture.h",
        "capture/dxgi_capture.cpp",
        "idd_driver/idd_compat.h",
        "idd_driver/Driver.h",
        "idd_driver/Driver.cpp",
        "idd_driver/Direct3DDevice.h",
        "idd_driver/Direct3DDevice.cpp",
        "idd_driver/VirtualMonitor.h",
        "idd_driver/VirtualMonitor.cpp",
        "idd_driver/IddDriver.inf",
    ]
    for rel_path in expected_files:
        p = NATIVE_DIR / rel_path
        assert p.is_file(), f"Expected native file missing: {rel_path}"
        assert p.stat().st_size > 0, f"Native file is empty: {rel_path}"


def test_cmakelists_structure() -> None:
    cmake_path = NATIVE_DIR / "CMakeLists.txt"
    content = cmake_path.read_text(encoding="utf-8")

    assert "add_library(dualdesk_capture STATIC" in content
    assert "add_library(dualdesk_idd SHARED" in content
    assert "target_link_libraries(dualdesk_capture PRIVATE d3d11 dxgi)" in content
    assert "target_link_libraries(dualdesk_idd PRIVATE d3d11 dxgi)" in content


def test_inf_driver_manifest() -> None:
    inf_path = NATIVE_DIR / "idd_driver" / "IddDriver.inf"
    content = inf_path.read_text(encoding="utf-8")

    assert 'Signature="$WINDOWS NT$"' in content
    assert "Class=Display" in content
    assert "ClassGuid={4d36e968-e325-11ce-bfc1-08002be10318}" in content
    assert "Root\\DualDeskDisplay" in content
    assert "UmdfLibraryVersion=2.25" in content
    assert "DualDeskIddDriver.dll" in content


def test_virtual_monitor_edid_checksum() -> None:
    vm_path = NATIVE_DIR / "idd_driver" / "VirtualMonitor.cpp"
    content = vm_path.read_text(encoding="utf-8")

    match = re.search(r"s_VirtualMonitorEdidBlock\[128\]\s*=\s*\{([^}]+)\};", content)
    assert match is not None, "s_VirtualMonitorEdidBlock not found in VirtualMonitor.cpp"

    cleaned = re.sub(r"//.*", "", match.group(1))
    hex_vals = [int(tok, 16) for tok in re.findall(r"0x[0-9a-fA-F]{2}", cleaned)]
    assert len(hex_vals) == 128, f"EDID block must be 128 bytes, found {len(hex_vals)}"

    # Standard EDID 1.4 header
    assert hex_vals[:8] == [0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00]

    # EDID 1.4 checksum (all 128 bytes sum to 0 mod 256)
    assert sum(hex_vals) % 256 == 0, f"EDID checksum failed: sum mod 256 is {sum(hex_vals) % 256}"
