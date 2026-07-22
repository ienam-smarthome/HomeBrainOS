# Hubitat MCP AI 0.10.36

- Makes explicit `find`, `locate`, and `search for` requests deterministic.
- Reports matched device identity, room, type, and availability.
- Prevents sensor names such as `Lux` from being misread as value requests.
- Adds regression coverage for lookup-versus-value semantics.
