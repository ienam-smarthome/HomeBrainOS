# Hubitat MCP AI 0.10.238

- Resolves routine light and switch targets from the known identity index before
  attempting a live label-filter search.
- Reuses identity metadata without forcing an expired live-state cache refresh.
- Combines device commands and resulting-state confirmation through
  `hub_call_device_command.waitFor`, removing a separate verification request.
- Keeps controls fail-closed when the command response does not confirm the
  requested switch state.
- Presents motion and battery filter results in concise natural language without
  adding another model round.
- Shows a consistent dashboard loading state instead of briefly reporting zero
  active rooms while other live counters remain unavailable.
