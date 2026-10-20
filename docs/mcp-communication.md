# MCP Communication

## Purpose

Model Context Protocol (MCP) is an optional integration for AI assistants and developer tooling. It is not required for DualDesk's core display, streaming, pairing or input functionality.

## Recommendation

Do not put MCP in the critical path between the two PCs. Display frames and input events need predictable, low-latency transport; use WebRTC and a narrow application protocol for that.

If MCP is added, use it only for optional, explicitly authorized actions such as:
- Read sanitized connection status.
- Read performance metrics.
- Retrieve redacted diagnostics.
- Start a non-privileged diagnostic collection.
- Query supported display capabilities.

Do not expose tools to:
- Inject arbitrary keyboard/mouse input.
- Execute shell commands.
- Install/remove drivers.
- Read screenshots, clipboard contents or arbitrary files without explicit user consent.
- Pair devices or grant trust silently.

## Proposed MCP server design

- Local stdio transport for a developer-only MCP server is the safest initial option.
- If HTTP transport is needed, bind to loopback and require authentication.
- Define a strict allowlist of tools.
- Validate parameters and redact results.
- Require explicit user confirmation for consequential actions.
- Keep MCP credentials separate from DualDesk device keys.

## Example read-only tools

- `get_connection_status()`
- `get_display_capabilities()`
- `get_performance_metrics()`
- `get_redacted_diagnostics()`

These are proposed interfaces, not implemented tools.

## MCP security rules

- Treat tool input as untrusted.
- Do not let prompt content override application authorization.
- Enforce permissions in the service layer, not only in the AI agent.
- Log tool invocation metadata without capturing sensitive content.
- Version the tool schema and test authorization failures.

## Integration acceptance criteria

MCP is considered integrated only when tool schemas, authorization, tests, user-consent flow and documentation exist. A placeholder document or sample tool does not constitute an implementation.
