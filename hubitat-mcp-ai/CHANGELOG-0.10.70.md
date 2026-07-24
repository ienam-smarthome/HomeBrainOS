# Hubitat MCP AI 0.10.70

- Installs the deterministic thermostat controller at the final `/api/ask` composition point.
- Ensures **What is the thermostat setpoint** uses a live `hub_read_devices` read instead of generic AI inventory search.
- Reports room temperature, heating setpoint and cooling setpoint separately.
- Adds regressions for the exact reported phrase and final route installation order.
