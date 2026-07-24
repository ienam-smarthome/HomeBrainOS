# Hubitat MCP AI 0.10.70

- Resolves the current `application.ask` handler when each `/api/ask` request executes.
- Prevents the cancellable HTTP route from bypassing terminal controllers installed after route creation.
- Ensures direct thermostat setpoint questions reach the deterministic live thermostat reader instead of inventory-only AI synthesis.
- Adds regression coverage for handler replacement after cancellable-route installation.
