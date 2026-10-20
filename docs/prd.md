# Product Requirements Document (PRD)

- **Product:** DualDesk
- **Version:** 0.1 draft
- **Primary platform:** Windows 11; Windows 10 compatibility must be validated
- **Product category:** Local-network extended display and input-sharing utility

## 1. Summary

DualDesk aims to make a second computer's physical monitor function as an additional display for a primary Windows PC. The primary PC creates a virtual monitor; its rendered frames are sent to a client running on the second PC. Applications remain running on the primary PC. The client may send authorized keyboard and mouse events back to the host.

This is different from mirroring the primary physical display in a window.

## 2. Problem

Users with two PCs may want more workspace without a direct video cable from the primary PC to the second monitor. Existing screen-sharing tools often show a remote desktop but do not expose a true additional display to the operating system.

## 3. Goals

1. Provide a genuine virtual extended display on the host.
2. Stream that display to the client over a trusted LAN.
3. Support usable interactive input with clear focus and escape behavior.
4. Pair devices securely and require explicit approval.
5. Recover safely from disconnects and driver errors.
6. Make installation, diagnostics and limitations understandable.

## 4. Non-goals for MVP

- Combining CPU, RAM or GPU resources across PCs.
- Using the client PC's GPU to accelerate applications running on the host automatically.
- Internet-wide remote access or a mandatory cloud relay.
- Mobile clients.
- Guaranteed compatibility with all graphics drivers and hardware.
- Clipboard/file transfer until the core display path is reliable.

## 5. Personas and use cases

- Developer: code on the main display, browser/docs on the remote display.
- Designer: reference panels on a second screen.
- Student/researcher: dashboards and documentation on extra workspace.
- Multi-PC user: move mouse and keyboard between the host and client.

## 6. MVP features

| ID | Feature | Priority | Acceptance |
|---|---|---:|---|
| PR-01 | Host/client desktop UI | Must | User can select role and see state |
| PR-02 | LAN discovery | Must | Devices can find each other on a permitted LAN |
| PR-03 | Secure pairing | Must | Both sides explicitly approve and authenticate |
| PR-04 | Virtual display | Must | Windows recognizes an additional monitor |
| PR-05 | Display capture | Must | Frames from that virtual monitor are available |
| PR-06 | Video transport | Must | Client receives and renders frames |
| PR-07 | Input forwarding | Must | Authenticated input affects host apps on virtual display |
| PR-08 | Display mode settings | Should | Supported resolution/refresh can be selected |
| PR-09 | Reconnect handling | Should | Temporary network loss can recover safely |
| PR-10 | Diagnostics | Must | Driver/network/streaming failures are actionable |
| PR-11 | Clipboard sync | Could | Deferred until core is secure |
| PR-12 | File transfer | Could | Deferred until core is secure |

## 7. User journey

1. Install DualDesk on both computers.
2. Install the signed virtual display driver on the host (during development, use only a test environment).
3. Open DualDesk on both PCs.
4. Discover and pair devices using an out-of-band confirmation code.
5. Enable the virtual monitor.
6. Select a supported resolution.
7. Connect the client and display the stream.
8. Move an application window onto the virtual display.
9. Interact using supported input routing.
10. Disconnect and verify the host display returns to a usable state.

## 8. Non-functional requirements

- Performance: initial baseline 1080p/60 FPS where hardware/network permit; measure rather than promise.
- Latency: target sub-50 ms input-to-photon on a suitable wired LAN, subject to hardware and capture pipeline.
- Security: authenticated pairing, encrypted transport, message validation, least privilege.
- Reliability: no stuck input after disconnect; driver lifecycle must recover.
- Accessibility: keyboard navigable UI, readable status, clear error messages.
- Compatibility: define and test an explicit Windows/driver/GPU matrix.

## 9. Out of scope / product boundary

The MVP does not merge two computers into one hardware system. Apps displayed on the remote monitor still execute on the host PC. Screen streaming in a window is a prototype milestone, not acceptance of true extended desktop.

## 10. Risks

- IDD/IddCx and graphics-resource integration is the highest technical risk.
- Driver signing and installation complicate distribution.
- Video capture APIs may not capture a virtual display through the same path as a physical monitor.
- Wi-Fi multicast may be blocked by AP isolation or VLANs.
- Input injection must be carefully restricted to paired, authorized sessions.

## 11. Success metrics

Measure pairing success, connection time, frame rate, frame drops, input-to-photon latency, CPU/GPU usage, reconnect success, driver recovery and user setup success. Final thresholds must be agreed after a baseline prototype.

## 12. Release gates

- Gate A: local UI and unit tests pass.
- Gate B: authenticated pairing works.
- Gate C: a prototype stream is stable.
- Gate D: Windows recognizes a virtual monitor.
- Gate E: app windows can be moved to that monitor and rendered on client.
- Gate F: input, security, recovery and packaging tests pass.
