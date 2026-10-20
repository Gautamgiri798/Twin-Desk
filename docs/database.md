# Database and Local State

## Scope

DualDesk does not need a remote application database for the local-network MVP. Use SQLite for non-secret local preferences and metadata. Store credentials, private keys and pairing secrets in Windows Credential Manager or DPAPI-protected storage rather than raw database columns.

## Proposed tables

### `app_settings`
- `key` TEXT PRIMARY KEY
- `value_json` TEXT NOT NULL
- `updated_at` TEXT NOT NULL (UTC ISO-8601)

Store non-sensitive preferences only: role preference, selected quality preset, last used display mode, UI theme.

### `devices`
- `device_id` TEXT PRIMARY KEY (stable random identifier)
- `display_name` TEXT NOT NULL
- `platform` TEXT NOT NULL
- `last_seen_at` TEXT NULL
- `trust_status` TEXT NOT NULL CHECK (`pending`, `paired`, `revoked`)
- `public_key_fingerprint` TEXT NULL
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

Do not store private keys in this table.

### `connection_history`
- `id` INTEGER PRIMARY KEY
- `peer_device_id` TEXT NULL REFERENCES devices(device_id)
- `started_at` TEXT NOT NULL
- `ended_at` TEXT NULL
- `result` TEXT NOT NULL
- `failure_code` TEXT NULL
- `avg_fps` REAL NULL
- `avg_latency_ms` REAL NULL
- `bytes_sent` INTEGER NULL
- `bytes_received` INTEGER NULL

Avoid logging personal content or input payloads.

### `diagnostic_events`
- `id` INTEGER PRIMARY KEY
- `created_at` TEXT NOT NULL
- `level` TEXT NOT NULL
- `component` TEXT NOT NULL
- `event_code` TEXT NOT NULL
- `message_redacted` TEXT NOT NULL
- `correlation_id` TEXT NULL

## Data retention

- Keep connection history locally by default.
- Provide a clear-log option.
- Bound diagnostic logs by size and age.
- Never store screenshots, keystrokes, clipboard contents or file contents by default.
- Exported diagnostic bundles must redact IPs/device names where practical and warn the user before sharing.

## Migration policy

- Use numbered SQL migrations.
- Back up the SQLite file before destructive migrations.
- Test migrations from the previous released schema.
- Use parameterized SQL and transactions.
