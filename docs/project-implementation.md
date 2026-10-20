# Project Implementation Plan

## Repository layout

The root repository contains:
- `src/dualdesk/`: Python UI and orchestration scaffold.
- `native/`: reserved for C++ driver/capture/input projects.
- `docs/`: product and technical documentation.
- `tests/`: automated tests.
- `pyproject.toml`: package metadata and development dependencies.

## Implementation stages

### Stage 0 — Scaffold
- Establish packaging, logging, settings and dashboard.
- Make explicit that display streaming is not yet implemented.
- Add CI for Python tests.

### Stage 1 — UI and settings
- Host/client role selection.
- Device list and connection state model.
- SQLite settings and device metadata.
- Diagnostics view.

### Stage 2 — Pairing
- LAN discovery with manual address fallback.
- Short-lived pairing challenge.
- Out-of-band user confirmation.
- Key/fingerprint persistence using OS secure storage.
- Negative tests for spoofed/unpaired devices.

### Stage 3 — Streaming proof of concept
- Capture a permitted existing display as a temporary source.
- Send video to the client.
- Measure FPS, latency, bandwidth and reconnect behavior.
- Clearly label this mode "Screen preview prototype".

### Stage 4 — Virtual monitor
- Build a minimal C++ IDD/IddCx proof of concept from Microsoft's sample.
- Test virtual monitor enumeration and lifecycle on a disposable test PC/VM where supported.
- Verify a frame path from the virtual display to the encoder.
- Do not proceed to end-to-end claims until it works.

### Stage 5 — Input and integration
- Map client coordinates to virtual-display coordinates.
- Implement secure input messages and release-all behavior.
- Test keyboard layouts, DPI, focus and escape behavior.

### Stage 6 — Hardening and release
- Threat model and security review.
- Driver signing and packaging.
- Performance profiling and soak tests.
- Crash recovery, installer rollback and diagnostics.

## First implementation task

Create a PySide6 dashboard that shows:
- Host/client role selector.
- Connection status.
- Driver availability (initially "Not integrated").
- Display state (initially "Unavailable").
- A visible notice: "This scaffold does not yet create an extended desktop."

This establishes honest product behavior while native work proceeds.
