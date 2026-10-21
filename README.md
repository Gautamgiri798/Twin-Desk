# Twin Desk

<div align="center">

<br>

<h1>🖥️ Twin Desk</h1>
<h3>Two PCs. One Seamless Extended Workspace.</h3>

<p align="center">
  <b>High-performance, ultra-low-latency virtual display and encrypted input utility for Windows.</b><br>
  Transform any secondary laptop or PC into a genuine, hardware-accelerated extended monitor over your local Wi-Fi or Ethernet LAN.
</p>

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%2010-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com)
[![Framework](https://img.shields.io/badge/GUI-PySide6%20Qt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![Driver Architecture](https://img.shields.io/badge/Driver-Windows%20IddCx%20(UMDF%202)-blueviolet?style=for-the-badge)](native/idd_driver)
[![Security](https://img.shields.io/badge/Security-TLS%201.3%20%7C%20SHA--256-blue?style=for-the-badge)](src/dualdesk/security)
[![Tests](https://img.shields.io/badge/Tests-136%20passed-success?style=for-the-badge&logo=pytest&logoColor=white)](tests/)

<br>

[✨ Key Features](#-key-features) • [⚡ 3-Step Quick Start](#-3-step-quick-start) • [🏗️ Architecture](#️-architecture) • [📂 Project Structure](#-project-structure) • [🛠️ Setup & Connecting](#️-setup--connecting-two-pcs) • [🔒 Security & Safety](#-security--safety)

<br>

</div>

---

> [!NOTE]
> **Extended Desktop Architecture**: Unlike standard remote desktop or window-mirroring software, Twin Desk is designed around the **Windows Indirect Display Driver (IDD / IddCx)** subsystem to register a genuine secondary display adapter in Windows Display Settings. When operating without the driver, Twin Desk runs in a high-efficiency prototype screen-streaming mode.

---

## ⚡ 3-Step Quick Start

Once installed on both machines, connecting whenever you want to work takes less than 10 seconds:

```d2
shape: sequence_diagram

user: "User"
host: "Primary PC (Host)"
network: "Local Wi-Fi / LAN"
client: "Second Laptop (Client)"

user -> host: "1. Launch run_host.bat"
host -> host: "Start TLS 1.3 server (Port 53892/53893) & show IP"
user -> client: "2. Launch run_client.bat"
client -> network: "Broadcast UDP Discovery (Port 53891)"
network -> host: "Forward Discovery Probe"
host -> client: "Announce presence with public key fingerprint"
client -> host: "Request Cryptographic Pairing"
host -> user: "Display 6-digit confirmation code"
user -> client: "3. Confirm 6-digit confirmation code"
client -> host: "TLS 1.3 Mutual Authentication (AES-256-GCM)"
host -> client: "Stream 60 FPS Video (DXGI / NVENC)"
client -> user: "Borderless Fullscreen Extended Desktop (Press F11)"
```

*Declarative D2 specification: [`docs/quickstart.d2`](docs/quickstart.d2)*

1. **On your Primary PC (Host)**:
   - Double-click [`run_host.bat`](run_host.bat).
   - The dashboard opens in **Host** mode and displays your local IP (e.g. `192.168.31.248`).
2. **On your Second Laptop (Client)**:
   - Connect to the same Wi-Fi/LAN and double-click [`run_client.bat`](run_client.bat).
   - In the **Devices** tab, click **Scan LAN** (or enter the Host's IP) and click **Pair**.
3. **Confirm & Extend**:
   - Confirm the 6-digit code shown on the Primary PC.
   - Click **Start Session / Connect** — press **<kbd>F11</kbd>** for borderless fullscreen extended display!

---

## ✨ Key Features

### 🚀 Video Pipeline & Hardware Acceleration
- **Zero-Overhead GPU Capture**: Direct DirectX 11 / DXGI Desktop Duplication (`IDXGIOutputDuplication`) capture pipeline with automatic graceful fallback to Win32 GDI in non-DWM or headless environments.
- **Hardware Encoder Auto-Detection**: Native acceleration probing for NVIDIA NVENC (`nvEncodeAPI64`), Intel QuickSync (`libmfx64`), AMD AMF (`amfrt64`), and Windows Media Foundation (`mfplat.dll`) with H.264 Annex B bitstream generation.
- **Adaptive Rate Control**: Real-time latency tracking dynamically throttles JPEG/H.264 compression quality and framerate (15–60 FPS) to eliminate buffer lag under network congestion.
- **Live Performance Telemetry**: 60-second rolling circular buffer rendered on a native Qt `QPainter` canvas widget with sparklines for FPS, latency spikes, throughput, and dropped frames.

### 🛡️ Zero-Trust Security & Transport
- **TLS 1.3 Transport Encryption**: Control (53892) and media streaming (53893) channels are strictly encrypted using TLS 1.3 with AES-256-GCM cipher suite and ephemeral key exchange.
- **Identity-Bound Cryptographic Pairing**: Device identity generated from public-key fingerprints (`SHA-256`) with time-limited 6-digit confirmation challenges (60s expiry) and brute-force rate-limiting.
- **Private-Network Binding**: Sockets bind strictly to LAN interfaces and reject unauthenticated transport requests.

### 🖱️ Input Routing & Desktop Ergonomics
- **Sub-Millisecond Remote Input**: Mouse, button, and keyboard injection with coordinate bounding and clamping to virtual display dimensions.
- **Multitouch Gestures**: Two-finger trackpad panning and scrolling translates dynamically to Windows wheel events (`MOUSEEVENTF_WHEEL`), with pinch-to-zoom mapping.
- **Customizable Emergency Escape**: Pressing **<kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>Esc</kbd>** (re-bindable) unconditionally revokes remote authority, synthesizes release of all held keys/buttons, and returns control to the local host.
- **Host Input Lockout**: Optional mode suppressing local physical pointer conflict while a remote client is actively controlling.
- **Spatial Display Arrangement Map**: Interactive visual display canvas allowing users to drag the virtual monitor to the **Left**, **Right**, **Above**, or **Below** primary screens with automatic coordinate translation.

### 📁 Productivity & Shell Integration
- **Secure Drag-and-Drop File Transfer**: Transfer files up to 250MB over the authenticated TLS control channel with directory traversal sanitization, recipient consent prompts, and SHA-256 integrity checks.
- **Encrypted Bidirectional Clipboard Sync**: Text clipboard exchange with anti-echo loop suppression, 1MB size clamping, and flood rate-limiting.
- **Audio Streaming & Jitter Buffer Health**: 16-bit 48kHz stereo PCM streaming with client volume scaling (0–150%), mute toggle, and live buffer health telemetry.
- **System Tray Minimization**: Background notification area integration (`QSystemTrayIcon`) with live status badges and Windows startup toggle (`HKCU\...\Run`).
- **Automated Network Reconnection**: Exponential backoff recovery worker (`ConnectionState.RECOVERING`) with in-viewport status banner.

---

## 🏗️ Architecture

> [!TIP]
> **Polished Interactive Diagrams**:
> - 🎨 **draw.io / diagrams.net**: [`docs/architecture.drawio`](docs/architecture.drawio) — Open in [draw.io / diagrams.net](https://app.diagrams.net) or the VS Code Draw.io extension for full interactive inspection and vector editing.
> - 📄 **D2 Declarative Source**: [`docs/architecture.d2`](docs/architecture.d2) & [`docs/quickstart.d2`](docs/quickstart.d2) — Declarative architecture and sequence specifications.

```d2
direction: right

host: "🖥️ PRIMARY PC (Host / Transmitter)" {
  style.fill: "#0B0F19"
  style.stroke: "#0284C7"

  dwm: "Windows Desktop Manager\n(DWM / Display Settings)"
  idd: "Native Windows IddCx Driver\n(Synthetic EDID 1.4 Virtual Monitor)"
  capture: "DXGI / GDI Capture Pipeline\n(IDXGIOutputDuplication)"
  encoder: "Hardware Video Encoder\n(NVENC / QuickSync / AMF / MFT)"
  transport_srv: "TLS 1.3 Transport Server\n(Ports 53892 & 53893)"
  injector: "Win32 Input Injector & Filter\n(Coordinate Clamping & Touch)"

  dwm -> idd -> capture -> encoder -> transport_srv
  transport_srv -> injector -> dwm
}

lan: "🔒 Encrypted Local Network (LAN)" {
  style.fill: "#0F172A"
  style.stroke: "#10B981"

  ctrl: "TLS 1.3 Control Channel (TCP 53892)\nPairing • Input • File Transfer"
  stream: "TLS 1.3 Media Channel (TCP 53893)\n60 FPS H.264 / JPEG Stream"
  beacon: "UDP Discovery Beacon (UDP 53891)\nPeer Presence Broadcast"
}

client: "💻 SECOND LAPTOP (Client / Receiver)" {
  style.fill: "#0B0F19"
  style.stroke: "#A855F7"

  client_engine: "TLS 1.3 Client Engine"
  decoder: "Video Decoder Engine\n(H.264 NAL / JPEG)"
  viewport: "PySide6 Render Viewport\n(StreamViewerWidget / Fullscreen)"
  input_cap: "Input & Gesture Capture\n(Mouse, Keys, Touch Panning)"
  escape: "Emergency Escape Hook\n(Ctrl+Alt+Shift+Esc)"

  client_engine -> decoder -> viewport -> input_cap -> escape -> client_engine
}

host.transport_srv -> lan.stream -> client.client_engine: "Video Frames"
client.client_engine <-> lan.ctrl <-> host.transport_srv: "Input & Control"
client.client_engine <-> lan.beacon <-> host.transport_srv: "Discovery"
```

---

## 📂 Project Structure

```
Twin-Desk/
├── run_host.bat                    # 1-Click launcher for Host (Primary PC)
├── run_client.bat                  # 1-Click launcher for Client (Second Laptop)
├── scripts/                        # Automated platform maintenance scripts
│   ├── configure_firewall.ps1      # Windows Defender Firewall configurator & diagnostics
│   └── build_driver.ps1            # Native IDD driver compilation & test-signing
├── packaging/                      # Production installer & distribution
│   ├── dualdesk_installer.iss      # Inno Setup 64-bit Windows installer specification
│   ├── build_package.ps1           # Packaging automation script with -DryRun & -Standalone
│   └── dualdesk.spec               # PyInstaller standalone executable specification
├── native/                         # Native C++ Windows display driver & capture
│   ├── idd_driver/                 # Microsoft IddCx Indirect Display Driver (UMDF 2.25)
│   │   ├── Driver.h/.cpp           # DriverEntry and EvtDeviceAdd lifecycle
│   │   ├── VirtualMonitor.h/.cpp   # Synthetic EDID 1.4 block & monitor arrival
│   │   ├── Direct3DDevice.h/.cpp   # Direct3D 11 swapchain device
│   │   ├── IddDriver.inf           # Windows Driver package installation manifest
│   │   └── idd_compat.h            # WDK IddCx cross-compilation shim
│   └── capture/                    # Low-latency DXGI desktop duplication capture
│       └── dxgi_capture.h/.cpp
├── src/dualdesk/                   # Core Python application package
│   ├── audio/                      # Low-latency PCM streaming & jitter buffer
│   ├── diagnostics/                # Redacted JSON diagnostic bundle generator
│   ├── display/                    # DXGI capture, GPU encoder (NVENC/QSV/AMF), multi-monitor
│   ├── network/                    # TLS 1.3 transport, UDP discovery, file transfer
│   ├── platform/                   # Windows notification area tray & autostart
│   ├── protocol/                   # Versioned message envelopes & typed schemas
│   ├── security/                   # SHA-256 identity, 6-digit challenge pairing & input filters
│   ├── storage/                    # SQLite repository, schema migrations & settings
│   └── ui/                         # PySide6 desktop dashboard, themes, and stream viewer
├── docs/                           # Architecture specifications & diagrams
│   ├── architecture.drawio         # Polished interactive diagram (draw.io / diagrams.net)
│   ├── architecture.d2             # Declarative system architecture model (D2)
│   └── quickstart.d2               # Declarative connection sequence model (D2)
├── tests/                          # Automated unit & integration test suite (136 tests)
└── pyproject.toml                  # Python project metadata and dependencies
```

---

## 🛠️ Setup & Connecting Two PCs

Twin Desk connects two Windows PCs over your local Wi-Fi or Ethernet LAN without any external cloud server or internet requirement.

### 1. Prerequisites
- **Operating System**: Windows 11 or Windows 10 (version 1809+) on both PCs
- **Network**: Both laptops connected to the **same Wi-Fi or Ethernet network**
- **Python**: 3.12 or 3.13 (64-bit)
- **Git**

---

### 2. Primary PC Setup (Host)

The Primary PC acts as the **Host**—generating the extended desktop screen and accepting remote mouse/keyboard inputs.

1. **Clone & Install Dependencies**:
   ```powershell
   git clone https://github.com/Gautamgiri798/Twin-Desk.git "C:\Projects\Twin Desk"
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

### 5. Automated Test Suite

Twin Desk includes a comprehensive 136-test automated verification suite covering protocol envelopes, SQLite migrations, cryptographic pairing challenges, input clamping, network discovery, DXGI capture, audio jitter buffers, and UI initialization:

```powershell
.\.venv\Scripts\pytest.exe -v
```

---

## ⚙️ Native Virtual Display Driver

True extended desktop mode requires Windows to enumerate a virtual display adapter at the OS level. The source files are provided in [`native/idd_driver/`](native/idd_driver):

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
*For detailed driver architecture and recovery instructions, refer to [`native/README.md`](native/README.md).*

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
