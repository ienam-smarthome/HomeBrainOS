# Hubitat MCP AI 0.10.213

- Stops read questions such as "Which switches are on?" from being treated as
  device mutations.
- Restores weather-device discovery for weather questions.
- Requires live app/rule reads when reporting automation state instead of
  treating the cached app identity manifest as current status.
- Includes available enabled, paused, active, broken, and status fields in the
  app identity manifest.
- Removes write gateways from read-only device, room, and automation requests.
