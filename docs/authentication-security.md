# Authentication and Security

## Threat model

Protect against:
- Unknown devices on the LAN.
- Spoofed discovery announcements.
- Pairing-code interception or reuse.
- Replay and malformed input messages.
- Unauthorized keyboard/mouse control.
- Malicious or compromised client.
- Local API misuse.
- Secrets leaking through logs or database files.

## Trust model

- LAN discovery is untrusted.
- Device names and IP addresses are not identities.
- A pairing code is a short-lived user-verification mechanism, not a permanent credential.
- Only cryptographically authenticated paired devices can start sessions.
- User approval is required for initial pairing and sensitive capabilities.

## Pairing requirements

1. Generate a cryptographically secure, short-lived challenge.
2. Display matching confirmation information on both devices.
3. Bind confirmation to the peer's public-key fingerprint/session.
4. Expire challenges quickly and rate-limit attempts.
5. Persist trust metadata; store private keys in Windows Credential Manager/DPAPI-backed storage.
6. Provide revoke/unpair.
7. Never transmit private keys or long-lived secrets through discovery.

## Transport security

- Use WebRTC's established security mechanisms and authenticated signaling.
- Validate peer identity before enabling input.
- If a separate control service exists, use TLS and explicit authentication.
- Do not invent a custom cryptographic protocol.
- Verify certificates/identity; do not disable validation to "fix" connection errors.

## Input security

- Input messages are allowed only in an active authenticated session.
- Apply strict schema, range, size and rate validation.
- Reject out-of-order/replayed commands where applicable.
- Do not accept commands that launch processes or execute shell commands.
- On disconnect, release all held keys/buttons and revoke control.
- Provide a local escape shortcut that cannot be overridden by the remote peer.

## Privileges

- Keep the UI unprivileged.
- Separate driver installation from normal runtime.
- Use the minimum privileges required for any helper/service.
- Authenticate IPC between UI and helper.
- Never expose a privileged helper on the LAN.

## Logging and privacy

- Do not log raw keystrokes, screenshots, clipboard data, file contents or secrets.
- Redact tokens and pairing information.
- Allow local diagnostic-log deletion.
- Keep logs bounded and local by default.

## Security checklist

- [ ] Pairing expiry and rate limit
- [ ] Identity-bound user confirmation
- [ ] Revocation works
- [ ] Unpaired client rejected
- [ ] Malformed and oversized messages rejected
- [ ] Replay/stale input rejected
- [ ] Held input released after disconnect
- [ ] No secret in logs or database
- [ ] Local-only API binding
- [ ] Dependencies reviewed and pinned
- [ ] Driver package provenance/signing verified
