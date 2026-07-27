# Hubitat MCP AI 0.10.187

## Serialized power-summary diagnostics hotfix

- Fixes `show power devices` crashing with `AttributeError: 'str' object has no attribute 'get'` after monitored-device detail discovery.
- Decodes the serialized `safe_debug()` technical payload before reading idle values and fallback diagnostics.
- Accepts dictionary and JSON-string payloads and safely ignores malformed diagnostics.
- Keeps the shared monitored-power discovery introduced in 0.10.186 unchanged.
