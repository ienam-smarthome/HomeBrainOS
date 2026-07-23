# Hubitat MCP AI 0.10.52

- Fixes disabled rules being displayed as Active when `paused: false` is also present.
- Uses authoritative `disabled`, `paused`, and `status` fields in safe precedence order.
- Adds regression coverage for mixed active and disabled rule inventories.
