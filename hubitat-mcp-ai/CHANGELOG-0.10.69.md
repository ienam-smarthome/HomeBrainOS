# Hubitat MCP AI 0.10.69

- Reads thermostat temperature and setpoints from a fresh `hub_read_devices` call.
- Reports room temperature, heating setpoint and cooling setpoint as separate live attributes.
- Corrects **What's happening?** summaries using the same authoritative live thermostat state.
- Falls back to device-index metadata only if the live MCP read is unavailable.
