from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar


def get_default_db_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".dualdesk"))
    target = base / "DualDesk"
    target.mkdir(parents=True, exist_ok=True)
    return target / "dualdesk.sqlite3"


@dataclass
class DeviceRecord:
    device_id: str
    display_name: str
    platform: str
    trust_status: str  # 'pending', 'paired', 'revoked'
    public_key_fingerprint: str | None
    created_at: str
    updated_at: str
    last_seen_at: str | None = None


@dataclass
class ConnectionHistoryRecord:
    id: int | None
    peer_device_id: str | None
    started_at: str
    ended_at: str | None
    result: str
    failure_code: str | None
    avg_fps: float | None
    avg_latency_ms: float | None
    bytes_sent: int | None
    bytes_received: int | None


@dataclass
class DiagnosticEventRecord:
    id: int | None
    created_at: str
    level: str
    component: str
    event_code: str
    message_redacted: str
    correlation_id: str | None = None


class DualDeskDB:
    MIGRATIONS: ClassVar[list[str]] = [
        # Migration 1: Initial schema based on docs/database.md
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            platform TEXT NOT NULL,
            last_seen_at TEXT NULL,
            trust_status TEXT NOT NULL CHECK (trust_status IN ('pending', 'paired', 'revoked')),
            public_key_fingerprint TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS connection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_device_id TEXT NULL REFERENCES devices(device_id),
            started_at TEXT NOT NULL,
            ended_at TEXT NULL,
            result TEXT NOT NULL,
            failure_code TEXT NULL,
            avg_fps REAL NULL,
            avg_latency_ms REAL NULL,
            bytes_sent INTEGER NULL,
            bytes_received INTEGER NULL
        );

        CREATE TABLE IF NOT EXISTS diagnostic_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            level TEXT NOT NULL,
            component TEXT NOT NULL,
            event_code TEXT NOT NULL,
            message_redacted TEXT NOT NULL,
            correlation_id TEXT NULL
        );
        """,
    ]

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else get_default_db_path()
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_migrations()

    def _init_migrations(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            cursor = self.conn.execute("SELECT version FROM schema_migrations")
            applied_versions = {row[0] for row in cursor.fetchall()}

            for index, sql in enumerate(self.MIGRATIONS, start=1):
                if index not in applied_versions:
                    self.conn.executescript(sql)
                    now_str = datetime.now(UTC).isoformat()
                    self.conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                        (index, now_str),
                    )

    # Settings operations
    def set_setting(self, key: str, value: Any) -> None:
        now_str = datetime.now(UTC).isoformat()
        val_json = json.dumps(value)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, val_json, now_str),
            )

    def get_setting(self, key: str, default: Any = None) -> Any:
        cursor = self.conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value_json"])
        except Exception:
            return default

    # Devices operations
    def upsert_device(
        self,
        device_id: str,
        display_name: str,
        platform: str,
        trust_status: str = "pending",
        public_key_fingerprint: str | None = None,
    ) -> DeviceRecord:
        now_str = datetime.now(UTC).isoformat()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO devices (
                    device_id, display_name, platform, trust_status,
                    public_key_fingerprint, created_at, updated_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    platform = excluded.platform,
                    trust_status = excluded.trust_status,
                    public_key_fingerprint = coalesce(excluded.public_key_fingerprint, devices.public_key_fingerprint),
                    updated_at = excluded.updated_at,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    device_id,
                    display_name,
                    platform,
                    trust_status,
                    public_key_fingerprint,
                    now_str,
                    now_str,
                    now_str,
                ),
            )
        return self.get_device(device_id)  # type: ignore

    def get_device(self, device_id: str) -> DeviceRecord | None:
        cursor = self.conn.execute(
            "SELECT * FROM devices WHERE device_id = ?", (device_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return DeviceRecord(
            device_id=row["device_id"],
            display_name=row["display_name"],
            platform=row["platform"],
            last_seen_at=row["last_seen_at"],
            trust_status=row["trust_status"],
            public_key_fingerprint=row["public_key_fingerprint"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_devices(self, trust_status: str | None = None) -> list[DeviceRecord]:
        if trust_status:
            cursor = self.conn.execute(
                "SELECT * FROM devices WHERE trust_status = ? ORDER BY updated_at DESC",
                (trust_status,),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM devices ORDER BY updated_at DESC"
            )
        return [
            DeviceRecord(
                device_id=row["device_id"],
                display_name=row["display_name"],
                platform=row["platform"],
                last_seen_at=row["last_seen_at"],
                trust_status=row["trust_status"],
                public_key_fingerprint=row["public_key_fingerprint"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in cursor.fetchall()
        ]

    def update_trust_status(self, device_id: str, status: str) -> bool:
        if status not in ("pending", "paired", "revoked"):
            raise ValueError(f"Invalid trust status: {status}")
        now_str = datetime.now(UTC).isoformat()
        with self.conn:
            res = self.conn.execute(
                "UPDATE devices SET trust_status = ?, updated_at = ? WHERE device_id = ?",
                (status, now_str, device_id),
            )
            return res.rowcount > 0

    def delete_device(self, device_id: str) -> bool:
        with self.conn:
            res = self.conn.execute(
                "DELETE FROM devices WHERE device_id = ?", (device_id,)
            )
            return res.rowcount > 0

    # Diagnostic Events
    def log_diagnostic_event(
        self,
        level: str,
        component: str,
        event_code: str,
        message_redacted: str,
        correlation_id: str | None = None,
    ) -> int:
        now_str = datetime.now(UTC).isoformat()
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO diagnostic_events (
                    created_at, level, component, event_code, message_redacted, correlation_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now_str, level, component, event_code, message_redacted, correlation_id),
            )
            return cursor.lastrowid

    def list_diagnostic_events(self, limit: int = 100) -> list[DiagnosticEventRecord]:
        cursor = self.conn.execute(
            "SELECT * FROM diagnostic_events ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [
            DiagnosticEventRecord(
                id=row["id"],
                created_at=row["created_at"],
                level=row["level"],
                component=row["component"],
                event_code=row["event_code"],
                message_redacted=row["message_redacted"],
                correlation_id=row["correlation_id"],
            )
            for row in cursor.fetchall()
        ]

    def clear_diagnostic_events(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM diagnostic_events")

    # Connection History
    def record_connection_start(self, peer_device_id: str | None) -> int:
        now_str = datetime.now(UTC).isoformat()
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO connection_history (
                    peer_device_id, started_at, result
                ) VALUES (?, ?, ?)
                """,
                (peer_device_id, now_str, "in_progress"),
            )
            return cursor.lastrowid

    def record_connection_end(
        self,
        history_id: int,
        result: str,
        failure_code: str | None = None,
        avg_fps: float | None = None,
        avg_latency_ms: float | None = None,
        bytes_sent: int | None = None,
        bytes_received: int | None = None,
    ) -> None:
        now_str = datetime.now(UTC).isoformat()
        with self.conn:
            self.conn.execute(
                """
                UPDATE connection_history SET
                    ended_at = ?,
                    result = ?,
                    failure_code = ?,
                    avg_fps = ?,
                    avg_latency_ms = ?,
                    bytes_sent = ?,
                    bytes_received = ?
                WHERE id = ?
                """,
                (
                    now_str,
                    result,
                    failure_code,
                    avg_fps,
                    avg_latency_ms,
                    bytes_sent,
                    bytes_received,
                    history_id,
                ),
            )

    def list_connection_history(self, limit: int = 50) -> list[ConnectionHistoryRecord]:
        cursor = self.conn.execute(
            "SELECT * FROM connection_history ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [
            ConnectionHistoryRecord(
                id=row["id"],
                peer_device_id=row["peer_device_id"],
                started_at=row["started_at"],
                ended_at=row["ended_at"],
                result=row["result"],
                failure_code=row["failure_code"],
                avg_fps=row["avg_fps"],
                avg_latency_ms=row["avg_latency_ms"],
                bytes_sent=row["bytes_sent"],
                bytes_received=row["bytes_received"],
            )
            for row in cursor.fetchall()
        ]

    def clear_connection_history(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM connection_history")

    def close(self) -> None:
        self.conn.close()
