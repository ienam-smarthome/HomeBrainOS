# Hubitat MCP AI 0.10.185

## Power device discovery fallback

- Expands targeted detail probing when projected Hubitat inventory returns no
  usable power rows.
- Prioritises explicit power meters, metering plugs, MQTT/Tasmota devices and
  likely monitored appliances such as fridges, freezers, washing machines and
  dehumidifiers.
- Excludes virtual network-block switches and sensor-only devices from the
  bounded probe set.
- Keeps unavailable power data separate from genuine 0 W idle readings.
- Adds candidate labels, scores and numeric-reading counts to diagnostics.
