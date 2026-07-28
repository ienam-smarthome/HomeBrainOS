# Hubitat MCP AI 0.10.207

- Use the server-supported `room` device projection instead of invalid
  `roomName`.
- Degrade dashboard enrichment gracefully instead of returning HTTP 500.
- Isolate status and dashboard refreshes so a dashboard error cannot hide
  healthy MCP and Ollama status.
