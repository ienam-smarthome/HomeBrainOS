# Hubitat MCP AI 0.10.208

- Reduce Ollama prompt/tool payload to the gateways relevant to app/rule or
  device requests.
- Cache a compact live app manifest for five minutes and omit the large device
  manifest from app-management requests.
- Provide the exact Rule Machine pause/resume gateway call shape.
- Limit confirmation synthesis to the tool being confirmed.
