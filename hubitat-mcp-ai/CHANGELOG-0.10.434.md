# 0.10.434

- Centralize `hub_list_devices` projection semantics in a protocol-level device-read contract instead of fixing individual prompts or intents.
- Fix the live 0.10.433 false-zero root cause: Hubitat MCP detailed mode exposes live state as `attributes`, while summary mode exposes `currentStates`; mixed `capabilities + currentStates` projections are now normalized before they reach the server.
- Validate projected live-state response shape at the MCP boundary. A non-empty device result that omits the promised state container is treated as a projection failure so callers can fall back rather than report a confident empty state.
- Keep the existing active-room fallback to the full authoritative inventory, which now also covers structurally incomplete projected results.
- Build the cached detailed device manifest from the same shared read contract so dashboard/manifest and query code cannot drift onto different state-field conventions.
- Add `MCP shared-read wait` timing so time spent awaiting an already-running manifest/snapshot is visible separately from MCP lock wait and HTTP time.
- Add regression coverage for summary-vs-detailed projection rules, the exact 0.10.433 mixed projection, response-shape validation, and the false-zero fallback path.
