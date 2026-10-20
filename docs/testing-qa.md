# Testing and QA

## Test levels

### Unit tests
- State transitions.
- Message schema validation.
- Device registry and settings.
- Coordinate mapping.
- Error-code mapping.
- Retry/backoff behavior.

### Integration tests
- Discovery and pairing on a controlled LAN.
- WebRTC negotiation.
- Capture/encode/decode pipeline.
- Virtual display lifecycle.
- Input routing.
- Disconnect and reconnect.

### System tests
- Install on a clean Windows machine.
- Reboot and resume from sleep.
- Switch resolution and refresh rate.
- Disconnect Ethernet or Wi-Fi during streaming.
- Close/crash client during held key/button.
- Remove driver and verify local display recovery.
- Test on multiple GPU vendors where available.

### Security tests
- Unknown peer attempts pairing.
- Revoked peer attempts reconnect.
- Invalid signature/identity.
- Oversized payloads.
- Invalid coordinates and key codes.
- Replayed and out-of-order messages.
- Local API called from another machine.
- Sensitive data absent from logs.

### Performance tests
Record:
- Capture-to-encode latency.
- Encode-to-network latency.
- Network-to-decode latency.
- Input-to-photon latency where measurement equipment is available.
- FPS and dropped frames.
- Bitrate and packet loss.
- CPU, GPU and memory use.
- Recovery time after packet loss/disconnect.

## Example manual test matrix

| Scenario | Expected result |
|---|---|
| Both PCs on same private LAN | Discovery works where multicast/broadcast is permitted |
| Guest Wi-Fi/client isolation | Clear connection failure and troubleshooting hint |
| Driver absent | Extended display marked unavailable |
| Unsupported resolution | Request rejected; existing mode remains stable |
| Client disconnects during key press | Host releases held input |
| Unpaired peer sends control message | Rejected |
| Network interruption | Input stops safely; bounded reconnect attempt |
| App exits | Resources and sessions are cleaned up |
| Virtual display fails | Host physical display remains usable or recovery guidance is shown |

## CI

Run Python unit tests and static checks on every commit. Native driver builds and hardware-dependent tests may require dedicated Windows runners and test machines; document them separately rather than pretending ordinary CI covers them.

## Release criteria

- All blocking security tests pass.
- No known issue can leave input stuck.
- Driver install/remove/recovery is tested.
- Supported OS and GPU matrix is documented.
- Performance results are measured on stated hardware.
- Installer provenance and signatures are verified.
