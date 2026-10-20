# AI Coding Agents and Vibe-Coding Rules

This file defines how AI coding tools should work on DualDesk. Copy or adapt the rules into `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md` or the instruction file supported by your coding environment.

## Project context

DualDesk is a Windows-first virtual extended-display application. The core challenge is a real virtual monitor, frame capture and low-latency transport. A screen preview is not equivalent to an extended desktop.

## Mandatory agent rules

1. Read `README.md` and relevant docs before changing architecture.
2. Never claim a feature is implemented unless code and tests demonstrate it.
3. Never replace virtual-display functionality with mirroring while labeling it "extended desktop".
4. Keep UI, protocol, native driver, capture, transport and input modules separate.
5. Make small, reviewable changes with explicit acceptance criteria.
6. Run tests and static checks after each meaningful change.
7. Do not invent Windows API methods or driver capabilities. Verify against Microsoft documentation and the official IDD sample.
8. Do not add dependencies without explaining why and pinning a compatible version.
9. Never hard-code secrets, signing certificates, pairing keys or credentials.
10. Do not weaken authentication to make a demo work.
11. Do not enable remote input until the peer is paired and the session authenticated.
12. On disconnect, release held input and revoke control authority.
13. Do not run destructive commands or install drivers without explicit user confirmation.
14. Do not expose local control APIs to all interfaces.
15. Keep logs free of keystrokes, screenshots, clipboard contents and secrets.
16. Add tests for bugs and new protocol behavior.
17. Update documentation and `.env.example` when configuration changes.
18. Clearly label stubs, mocks, TODOs and unimplemented native functionality.

## Recommended agent roles

- Product agent: requirements, acceptance criteria and scope control.
- UI agent: PySide6 views and accessibility.
- Windows-native agent: IDD/IddCx and C++ integration; must cite authoritative APIs.
- Streaming agent: WebRTC, capture, codec and performance measurements.
- Security agent: threat model, pairing, protocol validation and dependency review.
- QA agent: test plans, reproducibility and regression tests.
- Documentation agent: keep setup, API and troubleshooting aligned with implementation.

One agent should own architecture decisions and merge coordination. Avoid multiple agents editing the same core files simultaneously.

## Definition of done

- Requirement is traceable to a test or manual validation.
- Tests pass.
- Failure behavior is handled.
- Security implications are reviewed.
- Documentation is updated.
- The implementation status is accurate.
