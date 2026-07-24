# Hubitat MCP AI 0.10.68

- Corrects AI home summaries that confuse a thermostat's measured room temperature with its heating setpoint.
- Uses authoritative device-index attributes to distinguish `temperature`, `heatingSetpoint`, `thermostatSetpoint`, and `coolingSetpoint`.
- Rewrites only the proven contradiction where the claimed setpoint equals the measured temperature but differs from the actual heating setpoint.
- Adds diagnostics and regression coverage using temperature 24°C, heating setpoint 12°C, and cooling setpoint 35°C.
