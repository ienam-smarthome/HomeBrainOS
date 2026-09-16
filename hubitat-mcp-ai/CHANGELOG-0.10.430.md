# 0.10.430

- Reuse a freshly fetched dashboard/device manifest as the bounded whole-home live snapshot within the existing two-second freshness window, avoiding an immediate duplicate `hub_list_devices` read for aggregate queries such as active rooms, lights, and switches.
- Keep mutation safety intact: every write attempt still invalidates the shared live snapshot before and after execution.
- Add `MCP lock wait` and `MCP HTTP` timings to Technical details so a slow request can be separated into queueing behind the client lock versus actual Hubitat/MCP transport time.
- Preserve the existing request-local snapshot and nested MCP timing behaviour introduced in 0.10.429.