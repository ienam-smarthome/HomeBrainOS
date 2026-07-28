# Hubitat MCP AI 0.10.201

- Prevent WebUI startup from failing on plain-HTTP Home Assistant installations
  where the secure-context-only `crypto.randomUUID()` API is unavailable.
- Add an HTTP-safe browser session identifier fallback so status and chat API
  requests can start normally.
