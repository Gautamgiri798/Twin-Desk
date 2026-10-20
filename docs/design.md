# Design Specification

## Product design principles

- Desktop-native, calm, technical, premium.
- Status and safety are more important than decorative animation.
- Never imply a feature is active if the driver or connection is unavailable.
- Make host/client roles obvious.
- Keep dangerous actions (remove pairing, install driver, grant control) explicit.

## Information architecture

1. **Dashboard**
   - Role: Host / Client
   - Device name and OS
   - Pairing and connection state
   - Virtual display state
   - Streaming stats: FPS, latency, bitrate, dropped frames
   - Connect / Disconnect
2. **Devices**
   - Discovered devices
   - Paired devices
   - Fingerprint / trust state
   - Pair / revoke
3. **Display**
   - Virtual monitor on/off
   - Supported resolutions and refresh rates
   - Display orientation and placement
   - Fullscreen client option
4. **Performance**
   - Quality preset
   - Bitrate limit
   - Hardware/software encoding indicator
   - Network quality
5. **Diagnostics**
   - Driver availability
   - Capture/encoder state
   - Last connection error
   - Export redacted diagnostic bundle
6. **Settings**
   - Startup behavior
   - Private-network discovery
   - Security and trusted devices
   - Logs and privacy

## Dashboard layout

- Top bar: DualDesk logo/name, version, global status.
- Main status card: "Not connected", "Pairing", "Connecting", "Streaming", "Recovering", or "Error".
- Primary action: Connect / Disconnect.
- Two device cards: Host and Client.
- Display card: monitor name, mode, resolution, refresh.
- Performance strip: latency, FPS, bitrate, packet loss.
- Persistent warning when running a prototype without the virtual-display driver.

## Visual system

- Use a neutral dark/light system theme with one accent color.
- Use semantic status colors only for success, warning and error.
- Use consistent spacing tokens (4, 8, 12, 16, 24, 32).
- Typography: platform system font; clear hierarchy and accessible contrast.
- Icons: simple line icons; always pair critical icons with text.
- Motion: brief state transitions only; no animation during streaming that competes for attention.

## Required UI states

- First launch / no devices
- Discovery in progress
- Pairing code awaiting confirmation
- Paired / disconnected
- Connecting
- Streaming
- Reconnecting
- Driver missing or unsupported
- Capture unavailable
- Permission denied
- Firewall/network blocked
- Session rejected
- Client disconnected
- Error with retry and diagnostic details

## UX requirements

- Explain that host applications still execute on the host.
- Distinguish "Screen preview" from "Extended display".
- Never show "Extended desktop ready" until OS monitor enumeration confirms the virtual display.
- Provide an emergency shortcut to return pointer control to the local display.
- Avoid storing pairing secrets in plain text.
