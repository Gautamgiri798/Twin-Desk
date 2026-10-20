# Debugging and Troubleshooting

## Diagnostic bundle

A diagnostic bundle should include:
- App version and build ID.
- Windows version/build.
- GPU and driver versions where available.
- Driver availability/status.
- Selected display mode.
- Connection state and sanitized peer identifier.
- WebRTC statistics (RTT, packet loss, bitrate, frames decoded).
- Redacted error logs.

Never include raw screen frames, keystrokes, clipboard content, passwords or private keys.

## Common problems

### No devices discovered
- Confirm both PCs are on a trusted LAN.
- Check guest Wi-Fi or client isolation.
- Confirm local firewall rules.
- Try manual address entry if supported.
- Verify discovery is enabled on the intended network interface.

### Pairing fails
- Check that the confirmation code has not expired.
- Compare peer identity/fingerprint on both devices.
- Check system clock only as a diagnostic aid; do not use clock alone for replay protection.
- Clear stale pairing only through the app's explicit revoke/unpair flow.

### Driver not detected
- Confirm supported Windows/WDK combination.
- Inspect Device Manager and driver logs.
- Verify package signature and installation status.
- Do not disable driver-signing protections on a daily-use system to work around the issue.

### Virtual monitor appears but no video
- Confirm the selected display is the virtual monitor.
- Verify capture adapter supports the actual driver frame path.
- Check encoder initialization and GPU compatibility.
- Compare captured-frame counters with encoded-frame counters.

### Video is choppy
- Prefer Ethernet.
- Check CPU/GPU usage and hardware encoder status.
- Reduce resolution, frame rate or bitrate.
- Inspect packet loss, jitter and frame queue depth.
- Discard stale frames rather than allowing latency to grow without bound.

### Mouse/keyboard does not respond
- Confirm session is paired and authenticated.
- Check client focus and pointer-boundary configuration.
- Validate coordinate mapping and display scaling.
- Verify input authorization is enabled for the session.
- Check logs for rejected or out-of-range events.

### Input remains stuck after disconnect
Treat as a release-blocking bug. Ensure session teardown triggers `release_all`, clears local held-state tracking and revokes the client's control token.

## Debugging principles

- Reproduce with a minimal test case.
- Capture timestamps and correlation IDs.
- Separate driver, capture, encode, transport, decode and render errors.
- Never log sensitive content to make debugging easier.
- Record environment details and exact steps.
