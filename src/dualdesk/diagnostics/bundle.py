from __future__ import annotations

import json
import platform
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dualdesk.display.driver import check_virtual_display_driver
from dualdesk.storage.db import DualDeskDB


def redact_sensitive_string(text: str) -> str:
    """Redacts IP addresses, tokens, and keys from diagnostic messages."""
    # Redact IPv4
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_IP]", text)
    # Redact potential UUIDs/tokens
    text = re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "[REDACTED_UUID]",
        text,
    )
    return text


class DiagnosticBundleGenerator:
    """Generates an exportable, redacted diagnostic bundle in adherence with docs/debugging.md."""

    APP_VERSION = "0.1.0"

    def __init__(self, db: DualDeskDB) -> None:
        self.db = db

    def generate_bundle(self) -> dict[str, Any]:
        driver_status = check_virtual_display_driver()
        raw_events = self.db.list_diagnostic_events(limit=50)
        history = self.db.list_connection_history(limit=20)

        redacted_events = [
            {
                "created_at": ev.created_at,
                "level": ev.level,
                "component": ev.component,
                "event_code": ev.event_code,
                "message": redact_sensitive_string(ev.message_redacted),
                "correlation_id": redact_sensitive_string(ev.correlation_id or ""),
            }
            for ev in raw_events
        ]

        sanitized_history = [
            {
                "started_at": h.started_at,
                "ended_at": h.ended_at,
                "result": h.result,
                "failure_code": h.failure_code,
                "avg_fps": h.avg_fps,
                "avg_latency_ms": h.avg_latency_ms,
                "bytes_sent": h.bytes_sent,
                "bytes_received": h.bytes_received,
            }
            for h in history
        ]

        bundle = {
            "metadata": {
                "bundle_version": 1,
                "generated_at": datetime.now(UTC).isoformat(),
                "notice": "This diagnostic bundle has sensitive identifiers and IP addresses redacted.",
            },
            "application": {
                "name": "DualDesk",
                "version": self.APP_VERSION,
                "python_version": sys.version.split()[0],
            },
            "system": {
                "os": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
            "driver_status": {
                "is_installed": driver_status.is_installed,
                "is_active": driver_status.is_active,
                "device_name": driver_status.device_name,
                "status_summary": driver_status.status_summary,
                "detected_monitors": driver_status.detected_monitors,
            },
            "recent_events": redacted_events,
            "connection_history": sanitized_history,
        }
        return bundle

    def export_to_file(self, target_path: Path) -> Path:
        bundle = self.generate_bundle()
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)
        return target_path
