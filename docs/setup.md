# Development Setup

## Supported development environment

- Windows 11 recommended.
- Python 3.12+.
- Git.
- Visual Studio 2022 with Desktop development with C++ for native work.
- Windows SDK and a compatible Windows Driver Kit for IDD/IddCx.
- CMake for native projects.
- VS Code or Visual Studio.

Driver development should be performed on a test machine or VM when feasible. Test-signing and driver installation can affect system security and boot behavior. Follow Microsoft's current driver-development guidance.

## Python scaffold

From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m dualdesk
```

If PowerShell blocks activation, use a permitted shell or invoke the venv interpreter directly:
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m dualdesk
```

## Tests

```powershell
pytest
```

## Native setup (later milestone)

1. Install Visual Studio C++ workload.
2. Install Windows SDK and a WDK version compatible with the selected Windows target.
3. Review Microsoft's Indirect Display Driver sample.
4. Create a separate native solution/CMake project.
5. Build and test using Microsoft's current driver-development instructions.
6. Sign test packages appropriately for the isolated development environment.
7. Validate install, removal, sleep/resume and crash recovery.

Do not use production machines as the first test target for an experimental display driver.

## Environment variables

No secrets are needed for the initial scaffold. Never put private keys, signing certificates or pairing secrets in `.env` or source control. If future integration credentials are required, document secure OS storage instead.
