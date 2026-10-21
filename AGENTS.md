# Twin Desk Agent Guidance

## Project Overview
Twin Desk is a Windows-first extended desktop application connecting two PCs over LAN using TLS 1.3, DXGI capture, dynamic H.264/JPEG streaming, and input synchronization.

## Testing & Quality
- Test suite: `pytest` located in `tests/`.
- Linters: `ruff check src tests`.
- The native virtual display driver is located under `native/idd_driver`. When running without the driver installed, the software falls back gracefully to user-mode window streaming.
