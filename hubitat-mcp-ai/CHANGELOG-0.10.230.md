# Hubitat MCP AI 0.10.230

## Deterministic live-read boundary

- Adds a pure presenter boundary for authoritative local-tool results.
- Returns device-filter, active-room, active-light, and active-switch answers
  directly from computed tool data without a second Ollama synthesis round.
- Adds `homebrain_active_lights` so exhaustive “which lights are on” requests
  use the same light classification as the dashboard.
- Preserves every returned match and derives displayed counts from the rendered
  result set rather than model-generated prose.
- Stops injecting the cached device identity/state manifest into live-read
  prompts. Live facts must come from successful tool receipts, reducing prompt
  size and preventing cached state from being treated as current evidence.
- Retains identity-manifest injection for write requests that require target
  resolution.

