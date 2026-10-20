# API and Protocol Specification

## Important distinction

The MVP is a peer-to-peer desktop application, not a public web service. Its first API is an internal typed protocol between app modules and paired devices. Do not add a cloud REST backend unless a concrete product requirement appears.

## Transport

- WebRTC media track: encoded screen video.
- WebRTC data channel: authenticated control and telemetry messages.
- Signaling: a local authenticated channel or carefully designed in-band pairing handshake.
- Discovery: UDP multicast/broadcast only on supported trusted LANs; allow manual address entry as fallback.

## Message envelope

Use a versioned schema, for example:

```json
{
  "version": 1,
  "message_id": "random-uuid",
  "session_id": "random-uuid",
  "sequence": 42,
  "type": "input.pointer",
  "sent_at": "2026-01-01T00:00:00Z",
  "payload": {}
}
```

Rules:
- Reject unknown protocol versions and unknown critical message types.
- Enforce message-size limits.
- Validate every field and enum.
- Enforce sequence/replay policy.
- Authenticate before accepting control messages.
- Treat timestamps as diagnostic, not as sole replay protection.

## Message types

### Discovery
- `discovery.announce`
- `discovery.query`
- `discovery.response`

Only announce non-secret metadata. Do not send pairing tokens or keys over unauthenticated discovery.

### Pairing/session
- `pairing.request`
- `pairing.challenge`
- `pairing.confirm`
- `pairing.reject`
- `session.start`
- `session.accept`
- `session.stop`
- `session.error`

Pairing must bind approval to the displayed peer identity/fingerprint and expire quickly.

### Display capability
- `display.capabilities`
- `display.mode.request`
- `display.mode.accept`
- `display.mode.reject`
- `display.state`

Only advertise modes supported by the actual driver.

### Input
- `input.pointer`
- `input.button`
- `input.key`
- `input.release_all`

Input messages must only be accepted from the active authenticated session. Validate coordinate bounds, key/button enums, event rate and sequence. On disconnect, synthesize release of any held keys/buttons.

### Telemetry
- `telemetry.stats`
- `telemetry.warning`
- `telemetry.error`

Telemetry must not contain screen pixels, key contents, clipboard text or secrets.

## Proposed internal HTTP endpoints (optional local service only)

If an internal localhost API is needed for UI/native-helper coordination:
- `GET /health`
- `GET /v1/status`
- `POST /v1/session/connect`
- `POST /v1/session/disconnect`
- `GET /v1/display/capabilities`
- `POST /v1/display/mode`

Bind to loopback only, require an ephemeral session token, enforce request-size limits and reject cross-origin requests. Do not expose these endpoints on the LAN by default.

## Error model

Use stable error codes:
- `PAIRING_REQUIRED`
- `PAIRING_REJECTED`
- `UNSUPPORTED_PROTOCOL`
- `DRIVER_NOT_INSTALLED`
- `DISPLAY_MODE_UNSUPPORTED`
- `CAPTURE_UNAVAILABLE`
- `ENCODER_UNAVAILABLE`
- `NETWORK_UNREACHABLE`
- `AUTHENTICATION_FAILED`
- `SESSION_EXPIRED`
- `INPUT_REJECTED`

Do not expose stack traces or secrets to the client UI.
