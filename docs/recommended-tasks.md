# DualDesk Master Roadmap: Recommended Development Tasks

This document contains the complete and exhaustive list of all upcoming recommended tasks for Twin Desk (DualDesk). It is derived from the Product Requirements Document (`docs/prd.md`), Technical Specifications (`docs/architecture.md`, `docs/design.md`), Security Requirements (`docs/authentication-security.md`), and the Current Implementation Status (`docs/implementation-status.md`).

---

## 1. Real-Time UI Telemetry & Controls (Immediate Priority)

### TASK-01: Adaptive Bitrate UI Feedback Indicator [COMPLETED]
- **Status**: Completed & Verified
- **Category**: UI & Streaming Telemetry
- **Goal**: Expose real-time adaptive rate controller metrics to the user in the UI metric strip.
- **Details**:
  - Show live JPEG compression quality (30–85) or H.264 target bitrate alongside network throughput.
  - Display dynamic FPS target (15–60 FPS) and network status indicator (`Nominal`, `Backpressure`, `Congested`, `Recovering`).
  - Provide visual tooltip explaining how quality and framerate throttle automatically under network load.
- **Files**:
  - `src/dualdesk/ui/components.py`
  - `src/dualdesk/ui/app.py`
  - `src/dualdesk/display/adaptive.py`
  - `src/dualdesk/network/transport.py`
  - `tests/test_ui.py`
  - `tests/test_adaptive_streaming.py`
- **Acceptance Criteria**:
  - UI metric strip dynamically updates when `AdaptiveRateController` throttles quality or target FPS.
  - Automated tests verify label updates and ensure layout stability.

### TASK-02: Real-Time Performance History Graphs [COMPLETED]
- **Status**: Completed & Verified
- **Category**: UI & Diagnostics
- **Goal**: Render real-time rolling sparklines/graphs on the Performance page for FPS, latency (ms), and frame drop rate.
- **Details**:
  - Keep a 60-second rolling circular buffer of telemetry samples in `DualDeskApp`.
  - Draw lightweight native Qt canvas graphs in `PerformancePage` showing latency trends and bandwidth utilization.
  - Mark congestion spikes visually to assist network troubleshooting.
- **Files**:
  - `src/dualdesk/ui/components.py`
  - `src/dualdesk/ui/app.py`
  - `tests/test_ui.py`
- **Acceptance Criteria**:
  - Graph repaints at 1Hz without causing UI thread latency or GC spikes.
  - Graphs display clear scales, units (ms, kbps, fps), and legend.

---

## 2. Native Driver & Platform Integration

### TASK-03: Virtual Display Driver Installation UI Wizard
- **Category**: Driver & Native Integration / Onboarding
- **Goal**: Guide users safely through native IDD driver compilation, test-signing, and installation with clear disclosures.
- **Details**:
  - Add an interactive "Driver Installation Wizard" dialog on the Display Settings page.
  - Check prerequisites: Administrator elevation, Windows SDK/WDK presence, Test-Signing status (`bcdedit`).
  - Run `scripts/build_driver.ps1 -DryRun` to validate toolchains and certificates without modifying system state.
  - Provide explicit warning modals detailing test-signing mode, system requirements, and uninstallation instructions.
- **Files**:
  - `src/dualdesk/ui/app.py`
  - `src/dualdesk/ui/components.py`
  - `src/dualdesk/display/driver.py`
  - `docs/driver-installation.md`
- **Acceptance Criteria**:
  - Non-elevated users are guided to run as Administrator.
  - Dry-run validation executes safely without system modifications.
  - Clear user confirmation required before any system changes.

### TASK-04: Real Environment IDD Driver Build & Test VM Verification (Gate D)
- **Category**: Native C++ Driver / Testing
- **Goal**: Compile `native/idd_driver` using MSBuild/WDK on a dedicated Windows test VM and verify true OS monitor extension.
- **Details**:
  - Execute `scripts/build_driver.ps1` with valid WDK toolchain.
  - Enable test-signing on disposable test PC/VM (`bcdedit /set testsigning on`).
  - Install generated package via `devcon.exe install IddDriver.inf Root\DualDeskIddDriver`.
  - Verify Windows `EnumDisplayDevicesW` detects `DualDesk Virtual Monitor` and reports secondary desktop coordinates.
- **Files**:
  - `native/idd_driver/`
  - `scripts/build_driver.ps1`
  - `docs/driver-installation.md`
- **Acceptance Criteria**:
  - Windows Settings displays Monitor 2 as an "Extend these displays" target.
  - Native driver creates swapchain and provides frame buffers to capture pipeline.

### TASK-05: Windows Firewall Rule Configurator & LAN Permission Checker
- **Category**: Networking & Platform Security
- **Goal**: Automatically diagnose and configure Windows Defender Firewall rules for DualDesk ports.
- **Details**:
  - Check if UDP 53891 (Discovery), TCP 53892 (Control), and TCP 53893 (Media) are allowed on the active network profile.
  - Add `scripts/configure_firewall.ps1` to create inbound and outbound rules for `DualDesk.exe` and python virtualenv.
  - Show a non-intrusive warning banner in the Devices page if discovery is blocked by Windows Firewall.
- **Files**:
  - `scripts/configure_firewall.ps1`
  - `src/dualdesk/network/discovery.py`
  - `src/dualdesk/ui/app.py`
- **Acceptance Criteria**:
  - App detects blocked ports without crashing.
  - Firewall script requires elevated privileges and provides a dry-run flag.

---

## 3. Media & Audio Experience

### TASK-06: Audio Streaming UI Controls & Buffer Health Gauge
- **Category**: Audio & Media Controls
- **Goal**: Give users full control over remote audio forwarding and visual insight into audio playback latency.
- **Details**:
  - Add Audio Forwarding toggle in Preferences / Settings page.
  - Volume slider (0% to 150%) with mute toggle.
  - Visual jitter buffer health gauge showing audio latency and dropped packet percentage.
- **Files**:
  - `src/dualdesk/ui/app.py`
  - `src/dualdesk/audio/capture.py`
  - `src/dualdesk/network/transport.py`
- **Acceptance Criteria**:
  - Toggling audio mute stops outgoing audio frames on host.
  - Volume adjustments apply to client `AudioPlayerAdapter`.
  - Buffer underrun/overflow counters are visible and reset cleanly.

### TASK-07: Hardware Video Encoder Status & Diagnostics Card
- **Category**: Video Pipeline & Telemetry
- **Goal**: Display detected GPU hardware encoder details directly on the Performance page.
- **Details**:
  - Show active encoder backend: NVIDIA NVENC (`nvEncodeAPI64`), Intel QuickSync (`libmfx64`), AMD AMF (`amfrt64`), Windows Media Foundation (`mfplat.dll`), or Software Fallback.
  - Show encoder profile, hardware acceleration badge (`Active` / `Software Fallback`), and current codec (H.264 vs. JPEG).
- **Files**:
  - `src/dualdesk/display/encoder.py`
  - `src/dualdesk/ui/app.py`
- **Acceptance Criteria**:
  - Performance page accurately reflects detected GPU vendor encoder.
  - Software fallback is explicitly flagged with clear explanation.

---

## 4. Multi-Monitor & Desktop Usability

### TASK-08: Multi-Monitor Virtual Display Arrangement Map
- **Category**: Display & Input Coordinate Mapping
- **Goal**: Provide an interactive visual display layout canvas to position the virtual monitor relative to primary screens.
- **Details**:
  - Interactive mini-canvas on Display Settings page allowing users to drag the virtual monitor to the Left, Right, Above, or Below the primary monitor.
  - Syncs chosen arrangement with `VirtualDesktopLayout` in `src/dualdesk/display/multimonitor.py`.
  - Saves arrangement coordinates in `DualDeskDB` persistent settings.
- **Files**:
  - `src/dualdesk/ui/components.py`
  - `src/dualdesk/display/multimonitor.py`
  - `src/dualdesk/storage/db.py`
- **Acceptance Criteria**:
  - Visual monitor dragging updates host coordinate translation bounds.
  - Pointer crossover transitions smoothly at the chosen display edge.

### TASK-09: System Tray Minimization & Startup Behavior
- **Category**: UI & Windows Shell Integration
- **Goal**: Allow DualDesk to minimize to the Windows Notification Area (System Tray) and optionally launch on user login.
- **Details**:
  - Implement `QSystemTrayIcon` with context menu: `Show DualDesk`, `Session Status`, `Disconnect`, and `Exit`.
  - Add setting to "Minimize to tray on window close" and "Start minimized with Windows".
  - Manage Windows Registry auto-run key (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) with clean toggle.
- **Files**:
  - `src/dualdesk/ui/app.py`
  - `src/dualdesk/storage/db.py`
- **Acceptance Criteria**:
  - Closing window hides to tray without severing active streaming sessions.
  - Tray icon shows live connection status badge (Green = Streaming, Amber = Connecting, Gray = Inactive).

### TASK-10: Emergency Escape Shortcut Customization & Host Input Lockout
- **Category**: Security & Input Routing
- **Goal**: Let users customize the emergency pointer escape combination and optionally lock local host inputs while remote client is controlling.
- **Details**:
  - Allow re-binding `Ctrl+Alt+Shift+Escape` to custom key combinations in Preferences.
  - Add an optional "Host Input Lockout" mode: ignores physical mouse/keyboard inputs on the host while the remote client is active to prevent pointer conflict.
  - Always guarantee local escape shortcut unconditionally overrides and restores immediate host control.
- **Files**:
  - `src/dualdesk/security/input_filter.py`
  - `src/dualdesk/ui/app.py`
  - `tests/test_stream_and_input.py`
- **Acceptance Criteria**:
  - Emergency escape instantly revokes remote control token and fires `release_all`.
  - Custom keybind persists across restarts in `DualDeskDB`.

---

## 5. Network Resilience & Session Recovery

### TASK-11: Session Disconnect & Automatic Reconnection Handling
- **Category**: Network Resilience
- **Goal**: Gracefully handle network drops with retry backoff and non-blocking reconnection banners.
- **Details**:
  - On unexpected TCP disconnect, display an overlay banner with a 5-second countdown timer.
  - Implement exponential backoff retry (up to 3 attempts) before returning to `DISCONNECTED` state.
  - Preserve session security tokens and display mode settings across reconnections.
- **Files**:
  - `src/dualdesk/network/transport.py`
  - `src/dualdesk/ui/app.py`
  - `src/dualdesk/ui/viewer.py`
- **Acceptance Criteria**:
  - Transient network disconnects do not crash UI or leave sockets open.
  - Successful reconnection resumes streaming without manual user re-pairing.

---

## 6. Extended Collaboration Features

### TASK-12: Secure Out-of-Band File Transfer (PRD PR-12)
- **Category**: Collaboration & Productivity
- **Goal**: Enable encrypted drag-and-drop file transfers between host and client over the authenticated TLS control channel.
- **Details**:
  - Define `file.transfer.request`, `file.transfer.accept`, `file.transfer.chunk`, and `file.transfer.complete` protocol messages.
  - Strict security guardrails: prompt receiver with file name, type, and size before initiating transfer.
  - Anti-directory traversal path sanitization (strip `..`, write only to user-chosen `Downloads/DualDesk` directory).
  - Enforce max file size limit (default 250MB) and SHA-256 chunk verification.
- **Files**:
  - `src/dualdesk/protocol/models.py`
  - `src/dualdesk/network/transport.py`
  - `src/dualdesk/ui/viewer.py`
  - `tests/test_file_transfer.py`
- **Acceptance Criteria**:
  - Files cannot be transferred without explicit receiver consent.
  - Corrupt or interrupted transfers are cleanly discarded without leaving orphaned lock files.

---

## 7. CI / CD, Packaging & Distribution

### TASK-13: Automated CI & Test Harness Workflow
- **Category**: CI / CD & Quality Assurance
- **Goal**: Ensure continuous test pass and lint clean across multiple environments.
- **Details**:
  - GitHub Actions workflow running:
    - Code linting: `ruff check src tests`
    - Automated tests: `pytest tests/` (offscreen headless)
    - PowerShell script validation: `scripts/build_driver.ps1 -DryRun`
  - Check for unintended secrets, tokens, or certificate commits.
- **Files**:
  - `.github/workflows/ci.yml`
- **Acceptance Criteria**:
  - Clean run on Windows runner in GitHub Actions.

### TASK-14: Windows Standalone Installer & Uninstaller Packaging
- **Category**: Packaging & Distribution
- **Goal**: Package DualDesk as a production-ready Windows installer with integrated driver catalog registration.
- **Details**:
  - Create Inno Setup script (`packaging/dualdesk_installer.iss`) bundling Python executable (via PyInstaller/cx_Freeze), native driver binaries, and assets.
  - Clean uninstaller removing registry keys, firewall rules, and virtual driver devices.
- **Files**:
  - `packaging/dualdesk_installer.iss`
  - `pyproject.toml`
- **Acceptance Criteria**:
  - One-click install places binaries in `Program Files\DualDesk` and provisions start menu shortcuts.
  - Uninstaller cleanly removes all installed files and services without leaving orphaned artifacts.
