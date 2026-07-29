# Hubitat MCP AI 0.10.221

## Streaming and repository hygiene

- Streams Ollama chat rounds with configurable idle-stall detection.
- Enforces canonical Python module names through repository hygiene tests.
- Exposes `stream_idle_timeout_seconds` in Home Assistant add-on options.
- Integrates streaming with the v0.10.220 session coordinator so supersede,
  disconnect, and shutdown cancellation keep a single task owner.
