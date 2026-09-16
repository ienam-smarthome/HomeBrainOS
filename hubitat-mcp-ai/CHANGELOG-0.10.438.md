# Hubitat MCP AI 0.10.438

## Device-read contract hardening

- Strengthen projected live-state validation so every returned device record must contain the state container promised by the normalized `hub_list_devices` projection.
- Treat a mixed response where only some records contain `attributes`/`currentStates` as structurally incomplete instead of allowing missing records to be interpreted as inactive.
- Keep empty state containers valid for devices that legitimately have no reported state.
- Add regression coverage for mixed complete/missing projected records.

This is a correctness hardening release. It does not add prompt-keyword routing or change the `hubitat://context` fast path introduced in 0.10.437.
