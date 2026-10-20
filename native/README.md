# DualDesk Native Components: Windows Indirect Display Driver (IDD) & DXGI Capture

This directory contains the native C++ components for DualDesk:
1. **Windows Indirect Display Driver (`idd_driver`)**: A Windows Driver Framework (WDF) driver using the Microsoft Indirect Display Driver Class eXtension (`IddCx`) to create a real virtual monitor recognized by Windows Display Settings.
2. **DXGI Desktop Duplication Capture (`capture`)**: Low-latency native frame-capture pipeline acquiring frames directly from the display adapter swapchain.

---

## 1. Prerequisites for Building Native Driver

To build the native driver:
- Windows 11 (or Windows 10 version 1809+)
- Visual Studio 2022 with:
  - **Desktop development with C++**
  - **MSVC v143 build tools**
  - **Windows 11 SDK (10.0.22621.0 or higher)**
- **Windows Driver Kit (WDK)** compatible with your installed Windows SDK version:
  - Download and install the WDK from Microsoft: [Download the Windows Driver Kit](https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk)
  - Ensure the Visual Studio WDK Extension is enabled.

---

## 2. Driver Architecture (IddCx)

Windows Indirect Display Drivers run in user mode under the `WUDFHost.exe` process (UMDF 2.x). 
The driver interacts with the Windows OS display subsystem through `IddCx`:
- `Driver.cpp`: Defines `DriverEntry` and `EvtDeviceAdd`. Configures device capabilities and registers the IddCx device.
- `VirtualMonitor.cpp`: Implements `IddCxMonitorCreate` and `IddCxMonitorArrival`. Provides synthetic EDID data declaring standard desktop resolutions (1920x1080 @ 60Hz, 2560x1440 @ 60Hz, etc.).
- `Direct3DDevice.cpp`: Creates the Direct3D 11 / DXGI device required for frame rendering and swapchain buffer access.
- `IddDriver.inf`: Driver package description file specifying the device hardware ID `Root\DualDeskDisplay`.

---

## 3. Development & Testing Safety Notice

> **IMPORTANT**:
> - Never install test-signed drivers on a mission-critical primary machine without understanding recovery steps.
> - Use a virtual machine (Hyper-V) or an isolated test computer for initial testing.
> - Enable test signing on the test machine via an Administrator command prompt:
>   ```powershell
>   bcdedit /set testsigning on
>   ```
>   Reboot the test system afterwards.

---

## 4. Building the Driver

Using CMake and MSBuild:
```powershell
mkdir build
cd build
cmake -G "Visual Studio 17 2022" -A x64 ..
cmake --build . --config Release
```

Or open `CMakeLists.txt` directly in Visual Studio 2022.

---

## 5. Installing the Driver

Using `devcon.exe` (from the Windows Driver Kit):
```powershell
devcon.exe install IddDriver.inf Root\DualDeskDisplay
```

To remove the virtual display driver:
```powershell
devcon.exe remove Root\DualDeskDisplay
```

After installation, Windows will recognize a new monitor in `Settings > System > Display` which can be set to **Extend these displays**.
