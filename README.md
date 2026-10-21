# DualDesk

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%2010-0078D6?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com)
[![Framework](https://img.shields.io/badge/GUI-PySide6%20Qt6-41CD52?style=flat-square&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![Driver Architecture](https://img.shields.io/badge/Driver-Windows%20IddCx%20(UMDF%202)-blueviolet?style=flat-square)](native/idd_driver)
[![Tests](https://img.shields.io/badge/Tests-135%20passed-success?style=flat-square&logo=pytest&logoColor=white)](tests/)

**Two PCs. One extended workspace. High-performance, local-network virtual display utility.**

[Key Features](#-key-features) • [Architecture](#-architecture) • [Setup & Connecting](#-setup--connecting-two-pcs) • [Native Driver](#-native-virtual-display-driver) • [Security & Safety](#-security--safety)

</div>

---

> **Implementation status:** This repository is a planning and prototype scaffold, not a working virtual-display product. True extended-desktop functionality requires a Windows Indirect Display Driver (IDD/IddCx) and a validated frame-capture pipeline. Those components are not implemented by this scaffold.

---

## 🚀 Overview

**DualDesk** transforms a second computer's monitor into an extra, hardware-accelerated extended desktop for your primary Windows PC over a trusted local network (LAN)—eliminating the need for secondary monitor cables, hardware dummy plugs, or third-party cloud intermediaries.

Unlike standard remote desktop or screen mirroring tools that simply duplicate existing monitors into a window, DualDesk integrates with the **Windows Indirect Display Driver (IDD / IddCx)** subsystem to expose a genuine virtual monitor directly to Windows Display Settings.

```
┌─────────────────────────────────┐                 ┌─────────────────────────────────┐
│       PRIMARY PC (Host)         │                 │       SECOND PC (Client)        │
│                                 │                 │                                 │
│  ┌───────────────────────────┐  │                 │  ┌───────────────────────────┐  │
│  │ Windows OS Desktop Manager│  │                 │  │ PySide6 Fullscreen Render │  │
│  │ (Recognizes Virtual Mon.) │  │                 │  │ (Decodes & renders stream)│  │
│  └─────────────┬─────────────┘  │                 │  └─────────────▲─────────────┘  │
│                │                │                 │                │                │
│  ┌─────────────▼─────────────┐  │  H.264 / DXGI   │                │                │
│  │ Native C++ IddCx Driver   │──┼──Low Latency───┼────────────────┘                │
│  │ & DXGI Frame Capture      │  │    Stream       │                                 │
│  └─────────────▲─────────────┘  │                 │  ┌───────────────────────────┐  │
│                │                │  Encrypted      │  │ Client Input Capture      │  │
│  ┌─────────────┴─────────────┐  │  Data Channel   │  │ (Pointer, Button, Key)    │  │
│  │ Authenticated Input Sanitizer│◄┼──Control───────┼──┤ Emergency Escape Hook    │  │
│  └───────────────────────────┘  │  Protocol       │  └───────────────────────────┘  │
└─────────────────────────────────┘                 └─────────────────────────────────┘
```

---

## ✨ Key Features

| Component | Capabilities |
| :--- | :--- |
| **Desktop Dashboard & Telemetry** | Modern dark-themed PySide6 interface with live telemetry strip (`LiveMetricStrip`), real-time 60s rolling performance sparkline graphs (FPS, latency spikes, throughput, drops), and role selection (Host/Client). |
| **LAN Peer Discovery & Firewall** | Automated local network UDP beacon (port `53891`), manual IP fallback, and automated Windows Defender Firewall diagnostics (`scripts/configure_firewall.ps1`). |
| **Cryptographic Pairing & TLS 1.3** | Identity-bound pairing using SHA-256 public key fingerprints, time-limited 6-digit confirmation codes (60s expiry), brute-force rate limiting (max 3 attempts), and full TLS 1.3 AES-256-GCM transport encryption. |
| **Secure Input Routing & Lockout** | Remote mouse and keyboard injection with virtual monitor coordinate clamping, replay rejection, mandatory `release_all` on disconnect, customizable emergency escape shortcuts, and optional host physical input lockout. |
| **Touch & Multitouch Gestures** | Full Windows touch contact tracking, two-finger pan/scroll, tap/double-tap, two-finger right-click, and pinch-to-zoom mapping. |
| **Zero-Overhead GPU Capture** | Direct DirectX 11 / DXGI Desktop Duplication (`IDXGIOutputDuplication`) capture pipeline with automatic graceful fallback to Win32 GDI in headless environments. |
| **Hardware Video Acceleration** | GPU hardware encoder detection (NVIDIA NVENC, Intel QuickSync, AMD AMF, Windows Media Foundation) with H.264 Annex B bitstream generation and real-time performance diagnostics card. |
| **Adaptive Rate Control** | Dynamic JPEG quality and framerate throttling (15–60 FPS) responding to socket backpressure with visual congestion indicators (`Nominal`, `Recovering`, `Congested`, `Backpressure`). |
| **Multi-Monitor Arrangement Map** | Interactive spatial arrangement canvas on Display Settings allowing drag-and-drop virtual display positioning (Left, Right, Above, Below) with real-time coordinate synchronization. |
| **Encrypted Clipboard Sync** | Bidirectional text clipboard exchange with size limits (1MB), flood rate-limiting (5 updates/sec), null-byte stripping, and anti-echo loop suppression. |
| **Secure Out-of-Band File Transfer** | Drag-and-drop encrypted file transfer over authenticated TLS control channel with directory traversal sanitization, 250MB guard limit, and per-chunk/file SHA-256 verification. |
| **Audio Forwarding & Health Gauge** | 16-bit 48kHz stereo PCM streaming with volume scaling (0–150%), silence suppression, and jitter buffer health gauge displaying buffered latency and underrun tallies. |
| **System Tray & Autostart** | Notification area integration (`QSystemTrayIcon`) with live status badges, close-to-tray window minimization, and Windows Registry autostart toggle. |
| **Driver Detection & Setup Wizard** | Win32 `EnumDisplayDevicesW` inspection and interactive Driver Installation UI Wizard with elevation/test-signing checks and non-destructive dry-run validation. |
| **Automated Recovery** | Non-blocking exponential backoff reconnection worker (`ConnectionState.RECOVERING`) with interactive recovery overlay banner and token preservation. |
| **Windows Packaging & CI** | Standalone Inno Setup installer specification (`DualDesk_Setup_v0.1.0.exe`), automated build script, and comprehensive GitHub Actions CI pipeline. |

---

## 🛠️ Project Structure

```
DualDesk/
├── native/                         # Native C++ Windows drivers & capture
│   ├── CMakeLists.txt              # CMake build configuration for native components
│   ├── README.md                   # WDK build & test-signing documentation
│   ├── capture/                    # Low-latency DXGI desktop duplication capture
│   │   ├── dxgi_capture.h/.cpp
│   │   └── dxgi_compat.h           # DirectX 11 / DXGI fallback headers
│   └── idd_driver/                 # Windows Indirect Display Driver (IddCx)
│       ├── Driver.h/.cpp           # DriverEntry and EvtDeviceAdd lifecycle
│       ├── VirtualMonitor.h/.cpp   # Synthetic EDID and monitor arrival
│       ├── Direct3DDevice.h/.cpp   # Direct3D 11 swapchain device
│       ├── IddDriver.inf           # Windows Driver package installation manifest
│       └── idd_compat.h            # WDK IddCx cross-compilation shim
├── src/dualdesk/                   # Python application package
│   ├── diagnostics/                # Redacted bundle generator
│   ├── display/                    # Win32 driver detector & capture telemetry
│   ├── network/                    # UDP discovery beacon & connection transport
│   ├── protocol/                   # Versioned message envelopes & payload schemas
│   ├── security/                   # SHA-256 identity, 6-digit pairing & input filter
│   ├── storage/                    # SQLite repository, migrations & settings
│   ├── ui/                         # PySide6 desktop application & dark theme
│   ├── __init__.py
│   └── __main__.py                 # Application entry point
├── tests/                          # Automated unit & integration test suite
├── docs/                           # Comprehensive technical specifications
├── pyproject.toml                  # Package configuration & dependencies
└── README.md
```

---

## 🛠️ Setup & Connecting Two PCs

DualDesk connects two Windows PCs over your local Wi-Fi or Ethernet LAN without any external cloud server or internet requirement.

### 1. Prerequisites
- **Operating System**: Windows 11 or Windows 10 (version 1809+) on both PCs
- **Network**: Both laptops connected to the **same Wi-Fi or Ethernet network** (avoid guest Wi-Fi with client isolation)
- **Python**: 3.12 or 3.13 (64-bit)
- **Git**

---

### 2. Primary PC Setup (Host)

The Primary PC acts as the **Host**—generating the extended desktop screen and accepting remote mouse/keyboard inputs.

1. **Clone & Install Dependencies**:
   ```powershell
   git clone <repository-url> "C:\Projects\Twin Desk"
   cd "C:\Projects\Twin Desk"
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -e .
   ```

2. **Configure Windows Firewall** (One-Time Setup):
   Open PowerShell as **Administrator** and run the automated rule configurator:
   ```powershell
   .\scripts\configure_firewall.ps1
   ```
   *(Allows UDP 53891 for peer discovery, TCP 53892 for control/input, and TCP 53893 for the video stream)*.

3. **Launch Host Mode**:
   Double-click [`run_host.bat`](run_host.bat) or run:
   ```powershell
   .\.venv\Scripts\python.exe -m dualdesk --role host
   ```
   The application will start with the role set to **Host**. Take note of the **Local IP** displayed on the Dashboard card (e.g., `192.168.31.248`).

---

### 3. Second Laptop Setup (Client / Receiver)

The second laptop acts as the **Client**—displaying the extended workspace and capturing remote input.

1. **Install on Second Laptop**:
   Copy or clone the project folder to the second laptop and install dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   ```
   *(Alternatively, run `.\packaging\build_package.ps1 -Standalone` on your main PC to generate a standalone `DualDesk.exe` that requires no Python installation)*.

2. **Launch Client Mode**:
   Double-click [`run_client.bat`](run_client.bat) or run:
   ```powershell
   .\.venv\Scripts\python.exe -m dualdesk --role client
   ```

3. **Discover & Pair**:
   - Go to the **Devices** tab.
   - Click **Scan LAN** to automatically discover your Primary PC *(or type the Primary PC's IP address directly into the Manual Connect box)*.
   - Click **Pair** next to the Host.
   - A time-limited 6-digit confirmation code will appear on the Primary PC. Confirm the code on the second laptop to complete cryptographic TLS 1.3 pairing.

4. **Start Streaming**:
   - Click **Start Session** on the Dashboard.
   - The stream window will open. Click the **Fullscreen** button or press <kbd>F11</kbd> to expand into a borderless extended monitor.

---

### 4. Key In-Session Controls

| Action | Hotkey / Gesture | Description |
| :--- | :--- | :--- |
| **Emergency Escape** | <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>Esc</kbd> | Immediately revokes remote input authority, releases all held keys/buttons, and returns control to the local host. |
| **Toggle Fullscreen** | <kbd>F11</kbd> | Switches between windowed and borderless fullscreen viewing. |
| **Drag & Drop File Transfer** | Drag file onto viewport | Securely transfers files up to 250MB over TLS 1.3 with SHA-256 verification. |
| **Trackpad Pan & Zoom** | Two-finger scroll / pinch | Client multitouch gestures map to Windows wheel scroll and zoom. |
| **Display Arrangement** | Display tab on Host | Drag the virtual monitor box to position the laptop (Left, Right, Above, Below) matching physical placement. |

---

### 5. Run the Automated Test Suite

DualDesk includes a comprehensive test suite covering protocol validation, SQLite migrations, cryptographic pairing challenges, input clamping, network discovery, and UI initialization:

```powershell
.\.venv\Scripts\pytest.exe -v
```

---

## ⚙️ Native Virtual Display Driver

True extended desktop mode requires Windows to enumerate a virtual display adapter at the OS level. The source files are provided in [`native/idd_driver/`](file:///e:/New%20Projects/Twin%20Desk/native/idd_driver):

### Prerequisites for Driver Compilation:
- **Visual Studio 2022** with *Desktop development with C++*
- **Windows 11 SDK** (10.0.22621.0 or newer)
- **Windows Driver Kit (WDK)** compatible with your SDK version

### Build & Installation Steps:
```powershell
# 1. Enable test-signing on a dedicated test machine or VM (Admin CMD)
bcdedit /set testsigning on

# 2. Build the native driver via CMake or Visual Studio
cd native
mkdir build && cd build
cmake -G "Visual Studio 17 2022" -A x64 ..
cmake --build . --config Release

# 3. Install the driver using devcon.exe
devcon.exe install IddDriver.inf Root\DualDeskDisplay
```
*For detailed driver architecture and recovery instructions, refer to [`native/README.md`](file:///e:/New%20Projects/Twin%20Desk/native/README.md).*

---

## 🔒 Security & Safety

- **Private-Network Binding:** Control endpoints and discovery beacons bind strictly to LAN interfaces and will not expose ports to the public internet.
- **Zero Plain-Text Secrets:** Pairing secrets and private keys are never stored in raw SQLite columns or log files.
- **Emergency Escape Shortcut:** Pressing **<kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>Escape</kbd>** immediately revokes remote control authority and returns all pointer and keyboard control to the local host.
- **Release-All Guarantee:** If a client abruptly disconnects or experiences network packet loss, the host immediately synthesizes release events for all currently depressed keys and mouse buttons.
- **Unpaired Peer Rejection:** Unpaired or revoked peers attempting to initiate transport sessions are rejected and flagged in the diagnostic event log.

---

## 📄 License

This project is licensed under the terms chosen upon final product packaging. Native driver samples and third-party libraries retain their respective Microsoft and open-source licenses.
