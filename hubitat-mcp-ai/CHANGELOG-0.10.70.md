# Hubitat MCP AI 0.10.70

- `/api/ask` now resolves the current final `application.ask` handler when each request runs.
- Terminal thermostat, app and Hub-health routes can no longer be bypassed by an older captured handler.
- Includes an HTTP regression for `What is the thermostat setpoint`, requiring the deterministic thermostat route rather than `ollama+mcp`.
