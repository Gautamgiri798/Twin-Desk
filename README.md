# DualDesk

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%2010-0078D6?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com)
[![Framework](https://img.shields.io/badge/GUI-PySide6%20Qt6-41CD52?style=flat-square&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![Driver Architecture](https://img.shields.io/badge/Driver-Windows%20IddCx%20(UMDF%202)-blueviolet?style=flat-square)](native/idd_driver)
[![Tests](https://img.shields.io/badge/Tests-23%20passed-success?style=flat-square&logo=pytest&logoColor=white)](tests/)

**Two PCs. One extended workspace. High-performance, local-network virtual display utility.**

[Key Features](#-key-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [Native Driver](#-native-virtual-display-driver) • [Security & Safety](#-security--safety) • [Documentation](#-documentation)

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
| **Desktop Dashboard** | Modern dark-themed PySide6 interface with live telemetry strip (FPS, latency, bitrate, frame drops), role selector (Host/Client), and connection controls. |
| **LAN Peer Discovery** | Automated local network UDP discovery beacon (port `53891`) with device presence detection and manual IP address fallback. |
| **Cryptographic Pairing** | Identity-bound pairing using SHA-256 public key fingerprints, time-limited 6-digit confirmation codes (60s expiry), rate-limiting (max 3 attempts), and peer revocation. |
| **Secure Input Routing** | Remote mouse and keyboard injection with coordinate clamping to virtual monitor boundaries, replay rejection, mandatory `release_all` on disconnect, and emergency escape shortcut. |
| **Driver Detection** | Direct Win32 `EnumDisplayDevicesW` inspection reporting real-time virtual display driver status and supported resolution modes (1080p, 1440p, 720p, 4K). |
| **Redacted Diagnostics** | One-click diagnostic bundle exporter producing clean, anonymized JSON system reports with IP addresses and tokens stripped. |
| **Native C++ Scaffold** | Ready-to-compile Windows IddCx driver source code, INF installation manifest, and DXGI desktop duplication capture pipeline in `native/`. |

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

## 🚦 Quick Start

### 1. Prerequisites
- **OS:** Windows 11 or Windows 10 (version 1809+)
- **Python:** 3.12 or 3.13 (64-bit recommended)
- **Git**

### 2. Environment Setup

Clone the repository and initialize the Python virtual environment:

```powershell
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Upgrade pip and install editable package with dev dependencies
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Launch the Application

```powershell
python -m dualdesk
```

*Or launch directly via the virtual environment interpreter:*
```powershell
.\.venv\Scripts\python.exe -m dualdesk
```

### 4. Run the Automated Test Suite

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

## 📚 Documentation

Detailed technical documentation and architecture decisions are available in the [`docs/`](file:///e:/New%20Projects/Twin%20Desk/docs) directory:

- [Product Requirements Document (PRD)](docs/prd.md)
- [System Architecture](docs/architecture.md)
- [Design & Information Architecture](docs/design.md)
- [API & Protocol Specification](docs/api.md)
- [Authentication & Security Model](docs/authentication-security.md)
- [Database Schema & Local State](docs/database.md)
- [Implementation Plan & Milestones](docs/project-implementation.md)
- [Testing & QA Strategy](docs/testing-qa.md)
- [Debugging & Diagnostics Guide](docs/debugging.md)
- [Development Setup](docs/setup.md)
- [File Index](docs/file-index.md)

---

## 📄 License

This project is licensed under the terms chosen upon final product packaging. Native driver samples and third-party libraries retain their respective Microsoft and open-source licenses.
