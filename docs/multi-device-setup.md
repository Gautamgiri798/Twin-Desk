# DualDesk Multi-Device Setup & LAN Connection Guide

This guide provides end-to-end instructions for establishing a high-performance, encrypted virtual display session between two Windows computers over a local area network (LAN).

---

## 🏗️ Architecture & Roles

DualDesk operates in a peer-to-peer relationship across two distinct device roles:

| Role | Device Type | Purpose | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **Host** | Primary PC / Workstation | Work environment source | Generates virtual display frames, encodes video stream (H.264/JPEG), and accepts remote input. |
| **Client** | Second Laptop / Auxiliary PC | Remote monitor surface | Decodes and renders video frames in fullscreen, captures local mouse/touch/keyboard inputs, and forwards them to the Host. |

```
┌─────────────────────────────────────────┐               ┌─────────────────────────────────────────┐
│           PRIMARY PC (Host)             │               │       SECOND LAPTOP (Client)            │
│                                         │               │                                         │
│  - Virtual Display / DXGI Capture       │               │  - PySide6 Fullscreen Render Viewport   │
│  - Hardware Encoder (NVENC/QSV/AMF)     │               │  - Pointer, Keyboard & Gesture Capture  │
│  - Authenticated Input Injector         │               │  - Emergency Escape Monitor             │
│  - TCP/TLS Control Server (Port 53892)  │◄─────────────►│  - TCP/TLS Control Client               │
│  - TCP/TLS Media Server (Port 53893)    │               │  - Video Decoder (H.264 / JPEG)         │
│  - UDP Discovery Beacon (Port 53891)    │               │  - UDP Discovery Receiver               │
└─────────────────────────────────────────┘               └─────────────────────────────────────────┘
```

---

## 📋 Network & Environmental Prerequisites

Before connecting, verify the following prerequisites:

1. **Local Network Connectivity**:
   - Both devices must be on the **same subnet** (e.g., both connected to `192.168.1.0/24`).
   - **Important**: Avoid using *Guest Wi-Fi* networks, as many consumer routers enable *Client Isolation* (AP Isolation) on guest networks, which prevents devices from communicating directly with each other.
   - For optimal streaming performance (sub-16ms latency), 5GHz Wi-Fi 6 or a direct Gigabit Ethernet connection is strongly recommended.

2. **Network Port Allocation**:
   Ensure the following ports are open between the two machines:
   - **UDP 53891**: Peer Presence Discovery Beacon
   - **TCP 53892**: Authenticated TLS 1.3 Control Channel, Pairing & Input Forwarding
   - **TCP 53893**: Authenticated TLS 1.3 Media & Video Stream Channel

---

## 🖥️ Step 1: Host Machine Setup (Primary PC)

### 1.1 Configure Windows Firewall
Windows Defender Firewall must allow inbound traffic on DualDesk communication ports.

Open PowerShell as **Administrator** in the project directory and execute:
```powershell
.\scripts\configure_firewall.ps1
```
*(To verify the firewall status without making changes, you can run `.\scripts\configure_firewall.ps1 -CheckOnly`)*.

### 1.2 Identify Host IP Address
To support manual connection if router multicast is restricted:
```powershell
ipconfig
```
Note the **IPv4 Address** of your active network adapter (e.g., `192.168.1.50`).

### 1.3 Launch DualDesk in Host Mode
```powershell
.\.venv\Scripts\python.exe -m dualdesk
```
1. Verify on the **Dashboard** that **Current Role** is set to **Host (Primary PC)**.
2. The dashboard status indicator will show **Ready for connection**.

---

## 💻 Step 2: Client Machine Setup (Second Laptop)

Choose one of the two deployment methods below:

### Option A: Running from Python Environment (Developer Mode)

1. Clone or copy the repository onto the second laptop:
   ```powershell
   git clone <repository-url> "C:\Projects\Twin Desk"
   cd "C:\Projects\Twin Desk"
   ```
2. Initialize the Python virtual environment and install dependencies:
   ```powershell
   # 1. Create isolated virtual environment
   py -3.12 -m venv .venv

   # 2. Activate virtual environment
   .\.venv\Scripts\Activate.ps1

   # 3. Upgrade pip and install package
   python -m pip install --upgrade pip
   pip install -e .
   ```
3. Launch the application:
   ```powershell
   python -m dualdesk
   ```

### Option B: Standalone Portable Binary (No Python Required)

1. On your build machine, package DualDesk into a standalone executable:
   ```powershell
   .\packaging\build_package.ps1 -Standalone
   ```
2. Copy the resulting `dist\DualDesk` directory (or installer executable) to the second laptop.
3. Double-click `DualDesk.exe` to run.

---

## 🔐 Step 3: Peer Discovery & Cryptographic Pairing

DualDesk uses zero-trust identity-bound pairing with TLS 1.3 mutual authentication to prevent unauthenticated access.

1. **Select Client Role**:
   - On the second laptop, toggle the role selector on the **Dashboard** to **Client (Display / Receiver)**.

2. **Discover the Host**:
   - Navigate to the **Devices** tab.
   - Click **Scan LAN** to trigger a local UDP discovery broadcast.
   - Your Primary PC will appear in the **Discovered Devices** list.
   - *Manual Fallback*: If your router blocks UDP broadcast packets, enter the Primary PC's IP address (from Step 1.2) into the **Manual IP** input and click **Add Device**.

3. **Initiate Pairing**:
   - Click **Pair** next to your Primary PC's entry.
   - Both screens will present a **Cryptographic Pairing Challenge**:
     - The Host generates and displays a time-limited **6-digit confirmation code** (valid for 60 seconds).
     - Enter or verify the matching 6-digit code on the Client laptop.
   - Once verified, both machines store the cryptographic public-key fingerprint (`SHA-256`) in their local SQLite database (`DualDeskDB`). Future connections will authenticate automatically without re-entering codes.

---

## 🚀 Step 4: Starting the Extended Desktop Stream

1. **Connect**:
   - On the second laptop, click **Connect** on the Dashboard or Stream View page.
   - The TLS 1.3 handshake will complete and initiate the high-speed video stream.

2. **Maximize / Fullscreen**:
   - The `StreamWindow` viewport will launch on the second laptop.
   - Click the **Fullscreen** button in the top overlay or press **F11** to eliminate window borders.
   - The second laptop now operates as an active extended display.

3. **Spatial Display Alignment**:
   - On the **Primary PC**, go to the **Display** tab.
   - In the **Display Arrangement Canvas**, drag the virtual display box to match where your laptop physically sits relative to your primary screen (**Left**, **Right**, **Above**, or **Below**).
   - Pointer transitions will cross the boundary smoothly at the exact physical edge.

---

## 🎮 In-Session Controls & Hotkeys

| Action | Control / Shortcut | Description |
| :--- | :--- | :--- |
| **Emergency Escape** | <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>Esc</kbd> | Immediately revokes remote control authority, centers cursor on host, and releases all keys/buttons. |
| **Toggle Fullscreen** | <kbd>F11</kbd> | Switches client viewport between windowed and borderless fullscreen. |
| **Drag-and-Drop File Transfer** | Drag file into viewport | Sends files up to 250MB over TLS channel with SHA-256 verification and recipient confirmation. |
| **Multitouch Gestures** | Two-finger pan / pinch | Client trackpad gestures translate dynamically to Windows wheel scrolling and pinch-to-zoom. |
| **Audio Volume Adjust** | Preferences > Audio Slider | Scales remote audio playback volume between 0% and 150% with decibel curve. |

---

## 🔧 Troubleshooting & Diagnostics

### Symptom: "Scan LAN" does not find the Primary PC
- **Cause**: Router AP / Client isolation is active, or Windows Firewall blocked UDP port 53891.
- **Resolution**:
  1. Ensure network profile is set to **Private** (not Public) in Windows Settings on both PCs.
  2. Use **Manual Connect** by entering the Primary PC's local IPv4 address directly.
  3. Re-run `.\scripts\configure_firewall.ps1` as Administrator on both machines.

### Symptom: High Latency or Dropped Frames
- **Cause**: Wi-Fi 2.4GHz channel interference or socket buffer backpressure.
- **Resolution**:
  1. Switch both laptops to a 5GHz Wi-Fi band or use an Ethernet cable.
  2. In DualDesk **Performance** tab, check the **Adaptive Bitrate Indicator**:
     - If status indicates `Congested` or `Backpressure`, the adaptive rate controller will automatically lower compression quality to recover latency.
  3. Change the Performance Preset from *Ultra Low Latency* to *Balanced* or *Smooth*.

### Exporting Diagnostics
If you encounter persistent connection issues, click **Export Bundle** on the **Diagnostics** tab. DualDesk generates an anonymized, redacted JSON system report containing:
- Display driver enumeration status
- Network interface bindings
- Scrubbed event logs (IPs, MAC addresses, and tokens stripped)
- Hardware encoder availability
