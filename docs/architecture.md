# Architecture

## Architecture decision

Use a Windows-first, modular architecture. Python/PySide6 owns the UI and orchestration. C++ owns performance-critical Windows integration and the virtual display driver. WebRTC is the preferred real-time media transport, subject to prototype validation.

## Components

### Host application
- UI and session controller
- Pairing and trust store
- Virtual display service client
- Capture adapter
- H.264 encoder adapter
- WebRTC peer connection
- Input validation and injection adapter
- Telemetry/diagnostics

### Native display driver
- Windows Indirect Display Driver (IDD/IddCx)
- Advertises display modes and handles monitor lifecycle
- Provides a defined frame/resource path to capture pipeline
- Driver is a separate native build and install artifact

### Client application
- Device discovery and pairing
- WebRTC connection
- Video decode/render
- Input event collection
- Fullscreen client surface
- Connection and performance telemetry

## Data flow

1. Host driver exposes a virtual monitor.
2. Windows renders applications onto that monitor.
3. Capture adapter obtains the virtual monitor's frames.
4. Encoder produces H.264 frames.
5. WebRTC transports video to client.
6. Client decodes and renders.
7. Client sends input events through an authenticated data channel.
8. Host validates the session, sequence and bounds, then applies supported input.

The exact frame path between IDD/IddCx and capture must be proven experimentally; the driver does not automatically make every Windows capture API work with every virtual-display implementation.

## Process boundaries

Prefer separate components where privilege and failure isolation matter:
- UI process: normal user privileges.
- Native display driver: Windows driver framework requirements.
- Optional privileged helper/service: only if required, narrowly scoped, signed and authenticated.
- Network session: unprivileged where possible.

Do not run the whole UI as administrator just to simplify driver operations.

## Architecture decisions

- ADR-001: Windows-first MVP.
- ADR-002: Python/PySide6 UI; C++ native display integration.
- ADR-003: WebRTC for real-time media/data after latency testing.
- ADR-004: SQLite for local preferences/trust metadata, with secrets stored using Windows Credential Manager/DPAPI.
- ADR-005: LAN-only default; no mandatory cloud relay.
- ADR-006: Streaming prototype and true extended-display acceptance are separate milestones.

## Failure handling

- Network lost: stop accepting input, release all held keys/buttons, attempt bounded reconnect.
- Client crash: host revokes active input authority and keeps local display usable.
- Driver unavailable: disable extended-display controls; explain how to install supported driver.
- Encoder unavailable: attempt supported software fallback or report unsupported configuration.
- Unsupported mode: reject it and offer enumerated supported modes.
