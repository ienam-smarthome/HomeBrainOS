# Hubitat MCP AI 0.10.336

- Reuse one authoritative Hubitat device snapshot across deterministic operations within the same observed request.
- Keep the snapshot isolated by request identity so concurrent and later requests cannot reuse another request's live state.
- Preserve fresh live reads between requests while removing duplicate `hub_list_devices` calls inside room-level capability resolution.
- Record one authoritative state-snapshot evidence receipt for the reused inventory.
- Add regression coverage proving reuse within a request and refresh across requests.
