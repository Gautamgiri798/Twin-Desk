# Implementation Status

## Implemented in this codebase

### 1. Core Architecture and Modules
- **Typed Protocol & Message Envelope (`dualdesk.protocol`)**: Versioned schema validation, sequence enforcement, serialization/deserialization, error codes, and typed payloads for discovery, pairing, display capabilities, input events, and telemetry.
- **SQLite Storage & Migration Engine (`dualdesk.storage`)**: Numbered schema migrations, persistent settings (`app_settings`), paired device registry with cryptographic trust statuses (`devices`), connection telemetry history (`connection_history`), and diagnostic event logging (`diagnostic_events`).
- **Security & Cryptographic Pairing (`dualdesk.security`)**: Device identity generator with public key SHA-256 fingerprinting, short-lived 6-digit confirmation challenges (60s expiry), brute-force rate limiting (max 3 attempts), constant-time verification, device revocation, and zero plain-text secret storage.
- **Secure Input Filtering (`dualdesk.security.input_filter`)**: Strict session authentication, coordinate bounding and clamping to display dimensions, out-of-order/replayed event rejection, event rate limiting (250 events/sec), mandatory `release_all` on disconnect, and local emergency escape sequence detection (`Ctrl+Alt+Shift+Escape`).
- **LAN Discovery & Transport Manager (`dualdesk.network`)**: UDP multicast/broadcast beacon on port 53891, manual IP connection fallback, peer lifecycle state machine (`NOT_CONNECTED`, `PAIRING`, `CONNECTING`, `STREAMING`, `DISCONNECTED`, `ERROR`), and rejection of unauthenticated peers.
- **TCP Control Channel & Wire Protocol (`dualdesk.network.transport`)**: TCP server and client on port 53892 exchanging versioned `MessageEnvelope` packets (newline-delimited JSON with 64KB guard limit). Implements end-to-end network pairing handshake (`pairing.request`, `pairing.challenge`, `pairing.confirm`, `pairing.reject`), session negotiation (`session.start`, `session.accept`, `session.stop`), and live over-the-wire input event transmission (`input.pointer`, `input.button`, `input.key`, `input.release_all`).
- **Windows Display Driver Detector (`dualdesk.display.driver`)**: Queries Windows `EnumDisplayDevicesW` via Win32 ctypes to detect real Indirect Display Driver (IDD/IddCx) installation and enumerates supported modes (1080p, 1440p, 720p, 4K).
- **Screen Capture & Performance Telemetry (`dualdesk.display.capture`)**: Capture adapter calculating live FPS, capture-to-encode latency, bitrate, and dropped frames, with explicit labeling distinguishing between virtual extended displays and screen preview prototypes.
- **Redacted Diagnostics System (`dualdesk.diagnostics.bundle`)**: Generates and exports JSON diagnostic bundles containing system specs, driver status, redacted logs and connection history with IP addresses and tokens stripped.
- **Modern Desktop UI (`dualdesk.ui`)**: Full PySide6 multi-page desktop application with dark theme styling, live performance telemetry strip, Dashboard, Devices management & pairing modal (with fixed `challenge_id` verification binding), Display resolution/refresh selector, Performance presets, Diagnostics inspection, and Settings.
- **Native C++ Windows IDD Driver Scaffold (`native/idd_driver`)**: Microsoft IddCx user-mode display driver source code (`Driver.cpp`, `VirtualMonitor.cpp`, `Direct3DDevice.cpp`, `IddDriver.inf`) ready for compilation with the Windows Driver Kit (WDK) and test-signing on Windows.
- **Native C++ DXGI Desktop Duplication Capture (`native/capture`)**: Low-latency DirectX 11 / DXGI Desktop Duplication (`IDXGIOutputDuplication`) capture pipeline with CMake build configuration.
- **Automated Test Suite (`tests/`)**: 25 comprehensive unit and integration tests passing in pytest (covering protocol envelope schemas, SQLite migrations, cryptographic pairing challenges, input clamping/escape, discovery, live TCP control channel handshake/input forwarding, driver detection, and UI initialization), with 100% ruff lint pass.

## Unimplemented / Next Milestones
- **Live Video Streaming Pipeline & Viewport**: Screen frame data in `ScreenCaptureAdapter` is currently a local GDI thumbnail stub; real video frames must be acquired via DXGI Desktop Duplication, encoded, and rendered in a client PySide6 surface.
- **Native Driver Installation**: True extended desktop mode requires compiling `native/idd_driver` with Visual Studio 2022 + WDK and installing on a test machine with test-signing enabled (`bcdedit /set testsigning on`).
- **Host OS Input Injection**: Remote input events are authenticated and validated in memory by `InputFilter`, but are not yet forwarded to the host operating system via Win32 `SendInput()`.

