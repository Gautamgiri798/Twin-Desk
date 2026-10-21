# Windows Indirect Display Driver (IDD) Compilation, Test-Signing & Installation Guide

This document details the end-to-end process of building, signing, installing, and validating the native Windows Indirect Display Driver (`IddCx`) for DualDesk.

---

## 1. Architecture Overview

DualDesk relies on Microsoft's **Indirect Display Driver Class eXtension (IddCx)** introduced in Windows 10 (1607+) and enhanced in Windows 11.

- **Execution Environment**: Runs in user mode inside the Windows Driver Foundation host process (`WUDFHost.exe`).
- **Safety Isolation**: User-mode execution ensures that driver errors or crashes never produce a blue screen (BSOD) or destabilize the operating system kernel.
- **Hardware Integration**: Creates a virtual display adapter (`Root\DualDeskDisplay`) that registers virtual monitors directly with the Windows Display Subsystem (DWM).
- **Desktop Extension**: Windows recognizes the virtual monitor in **Settings > System > Display** as a real monitor, enabling true extended-desktop mode where windows, cursors, and hardware acceleration operate natively across hosts.

---

## 2. Prerequisites

To build and package the native driver:

1. **Operating System**: Windows 11 (recommended) or Windows 10 Version 1809+ (64-bit).
2. **Visual Studio**: Visual Studio 2022 (Community, Professional, or Enterprise) with:
   - **Desktop development with C++**
   - **MSVC v143 build tools (x86/x64)**
   - **Windows 11 SDK (10.0.22621.0 or higher)**
3. **Windows Driver Kit (WDK)**:
   - Download the WDK matching your installed Windows SDK version from [Microsoft WDK Downloads](https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk).
   - Install the WDK Visual Studio Extension when prompted.
4. **CMake**: Version 3.20 or newer.

---

## 3. Test-Signing Configuration

Windows enforces digital signature verification on all driver packages. To test a self-compiled driver without purchasing an EV hardware security module (HSM) certificate:

### Step 1: Enable Test-Signing in Windows
Open an **Administrator PowerShell** prompt and execute:
```powershell
bcdedit.exe /set testsigning on
```
> [!IMPORTANT]
> You **must restart your computer** after running `bcdedit` for test-signing mode to take effect. A "Test Mode" watermark will appear in the lower-right corner of the Windows desktop.

To revert test-signing at any time:
```powershell
bcdedit.exe /set testsigning off
```

---

## 4. Automated Build & Test-Signing Script

DualDesk includes an automated build script: [`scripts/build_driver.ps1`](file:///scripts/build_driver.ps1).

### Dry Run (Validate Toolchain Without Modifications)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_driver.ps1 -DryRun
```

### Build Only (Compile C++ Binaries)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_driver.ps1 -BuildOnly -Configuration Release -Platform x64
```

### Full Build & Sign (Produces Tested Package in `native/dist`)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_driver.ps1 -Configuration Release -Platform x64
```
This performs:
1. CMake configuration and MSBuild compilation into `native/build`.
2. Creation or discovery of a local self-signed code-signing certificate (`Cert:\CurrentUser\My`).
3. Export of public certificate (`native/dist/DualDeskTestCert.cer`).
4. Generation of security catalog file (`IddDriver.cat`) via `Inf2Cat.exe`.
5. Signing of `dualdesk_idd.dll` and `IddDriver.cat` via `signtool.exe`.

---

## 5. Driver Installation

### Automated Installation via Build Script (Administrator Required)
From an elevated Administrator PowerShell prompt:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_driver.ps1 -Install
```

### Manual Installation via Windows Tools

1. **Install Test Certificate into Local Machine Stores**:
   ```powershell
   Import-Certificate -FilePath native\dist\DualDeskTestCert.cer -CertStoreLocation "Cert:\LocalMachine\TrustedPublisher"
   Import-Certificate -FilePath native\dist\DualDeskTestCert.cer -CertStoreLocation "Cert:\LocalMachine\Root"
   ```

2. **Add Driver Package to Windows Driver Store**:
   ```powershell
   pnputil.exe /add-driver native\dist\IddDriver.inf /install
   ```

3. **Create the Virtual Display Device Node**:
   Using `devcon.exe` (from WDK `C:\Program Files (x86)\Windows Kits\10\bin\<version>\x64`):
   ```powershell
   devcon.exe install native\dist\IddDriver.inf Root\DualDeskDisplay
   ```

---

## 6. Verification

1. **Device Manager**:
   - Open `devmgmt.msc`.
   - Expand **Display adapters**.
   - Verify `DualDesk Virtual Display Adapter` is listed with no warning icons.
2. **Windows Display Settings**:
   - Open **Settings > System > Display**.
   - Verify Display #2 is detected.
   - Select **Extend desktop to this display**.
3. **DualDesk Application**:
   - Launch DualDesk (`.venv\Scripts\python -m dualdesk.ui.app`).
   - The Dashboard **Virtual Display** status card will display **Active: Windows IDD virtual display driver detected and active.**

---

## 7. Uninstallation & Removal

To completely remove the virtual display driver:

```powershell
# 1. Remove the virtual device node
devcon.exe remove Root\DualDeskDisplay

# 2. Delete driver package from system store
pnputil.exe /delete-driver oem<N>.inf /uninstall /force
```
*(Run `pnputil.exe /enum-drivers` to locate the assigned `oem<N>.inf` published name for `IddDriver.inf`)*.
