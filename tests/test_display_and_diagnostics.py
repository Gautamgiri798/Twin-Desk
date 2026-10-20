from __future__ import annotations

import json
import tempfile
from pathlib import Path

from dualdesk.diagnostics.bundle import DiagnosticBundleGenerator, redact_sensitive_string
from dualdesk.display.driver import check_virtual_display_driver, get_supported_modes
from dualdesk.storage.db import DualDeskDB


def test_supported_display_modes():
    modes = get_supported_modes()
    assert len(modes) >= 4
    resolutions = [(m.width, m.height) for m in modes]
    assert (1920, 1080) in resolutions
    assert (2560, 1440) in resolutions


def test_check_virtual_display_driver():
    status = check_virtual_display_driver()
    assert hasattr(status, "is_installed")
    assert hasattr(status, "is_active")
    assert hasattr(status, "status_summary")
    assert len(status.supported_modes) > 0


def test_redact_sensitive_string():
    raw = "Connection from 192.168.1.42 with token 12345678-1234-5678-1234-567812345678 failed."
    redacted = redact_sensitive_string(raw)
    assert "192.168.1.42" not in redacted
    assert "[REDACTED_IP]" in redacted
    assert "12345678-1234-5678-1234-567812345678" not in redacted
    assert "[REDACTED_UUID]" in redacted


def test_diagnostic_bundle_export():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db = DualDeskDB(Path(tmp_dir) / "test.db")
        db.log_diagnostic_event(
            level="ERROR",
            component="transport",
            event_code="ERR_CONN",
            message_redacted="Failed connecting to 10.0.0.1",
        )
        generator = DiagnosticBundleGenerator(db)
        bundle = generator.generate_bundle()

        assert bundle["application"]["name"] == "DualDesk"
        assert bundle["system"]["os"]
        assert "driver_status" in bundle
        assert len(bundle["recent_events"]) == 1
        assert "10.0.0.1" not in bundle["recent_events"][0]["message"]

        export_file = Path(tmp_dir) / "bundle.json"
        generator.export_to_file(export_file)
        assert export_file.is_file()

        with open(export_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["application"]["name"] == "DualDesk"
        db.close()
