from __future__ import annotations

import tempfile
from pathlib import Path

from dualdesk.storage.db import DualDeskDB


def test_sqlite_repository_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "test.sqlite3"
        db = DualDeskDB(db_file)

        # Settings
        db.set_setting("role", "host")
        db.set_setting("target_fps", 60)
        assert db.get_setting("role") == "host"
        assert db.get_setting("target_fps") == 60
        assert db.get_setting("non_existent", "fallback") == "fallback"

        # Devices
        dev = db.upsert_device(
            device_id="dev-pc-01",
            display_name="Workstation A",
            platform="Windows 11",
            trust_status="pending",
            public_key_fingerprint="SHA256:1111-2222-3333-4444",
        )
        assert dev.device_id == "dev-pc-01"
        assert dev.trust_status == "pending"

        # Update trust
        updated = db.update_trust_status("dev-pc-01", "paired")
        assert updated
        dev_paired = db.get_device("dev-pc-01")
        assert dev_paired is not None
        assert dev_paired.trust_status == "paired"

        # List devices
        paired_list = db.list_devices("paired")
        assert len(paired_list) == 1
        assert paired_list[0].device_id == "dev-pc-01"

        # Diagnostic events
        ev_id = db.log_diagnostic_event(
            level="INFO",
            component="pairing",
            event_code="PAIR_START",
            message_redacted="Initiated pairing challenge",
            correlation_id="corr-1",
        )
        assert ev_id > 0
        events = db.list_diagnostic_events()
        assert len(events) == 1
        assert events[0].event_code == "PAIR_START"

        db.clear_diagnostic_events()
        assert len(db.list_diagnostic_events()) == 0

        # Connection History
        hist_id = db.record_connection_start("dev-pc-01")
        assert hist_id > 0
        db.record_connection_end(
            history_id=hist_id,
            result="completed",
            avg_fps=60.0,
            avg_latency_ms=12.5,
        )
        histories = db.list_connection_history()
        assert len(histories) == 1
        assert histories[0].result == "completed"
        assert histories[0].avg_fps == 60.0

        db.clear_connection_history()
        assert len(db.list_connection_history()) == 0

        # Delete device
        assert db.delete_device("dev-pc-01")
        assert db.get_device("dev-pc-01") is None

        db.close()
