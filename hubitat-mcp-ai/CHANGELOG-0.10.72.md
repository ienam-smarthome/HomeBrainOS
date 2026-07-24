# Hubitat MCP AI 0.10.72

- Moves direct thermostat temperature and setpoint interception into the final `/api/ask` HTTP boundary.
- Prevents direct thermostat questions from falling through to `ollama-verified` or inventory-only `hub_list_devices` searches because of wrapper composition order.
- Uses the authoritative live thermostat reader before invoking the replaceable `application.ask` chain.
- Adds `http_boundary_guard: true` to successful direct thermostat responses for runtime verification.
