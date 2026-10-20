# Integrations

## Core integrations

### Windows IDD / IddCx
Required for true virtual-monitor functionality. Build and test separately from the UI. Reference Microsoft's official Indirect Display Driver sample and current WDK docs.

### Windows Graphics APIs
Use a capture path that is experimentally verified for the chosen virtual display implementation. Do not assume a physical-display capture API automatically captures the virtual monitor.

### WebRTC
Use for real-time video and control data after validating direct LAN connectivity, hardware decode/encode support and latency. Keep signaling separate from the media pipeline.

### Windows Credential Manager / DPAPI
Use for protected local secrets. Store only public fingerprints and non-secret metadata in SQLite.

## Optional integrations

- Windows startup integration.
- System tray controls.
- Clipboard synchronization (disabled by default until reviewed).
- File transfer (separate explicit user action).
- GitHub Releases for update metadata.
- Crash-report export, local by default and opt-in if uploaded.

## Integration rules

- Integrations must fail closed for privileged capabilities.
- Optional integrations must not block basic local use.
- No mandatory cloud account for the LAN MVP.
- Do not silently upload telemetry or diagnostics.
- Pin dependencies and review licenses.
- Provide capability detection and clear UI states when a dependency is missing.

## GitHub update integration

If implemented:
- Fetch only release metadata from the official repository.
- Verify downloaded installer/driver signatures and checksums where provided.
- Do not auto-install a driver without explicit user approval.
- Do not run arbitrary scripts from release metadata.
