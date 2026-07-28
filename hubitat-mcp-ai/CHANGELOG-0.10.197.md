# Hubitat MCP AI 0.10.197

## Add optional Gemini reasoning and qualify firmware channels

- Adds an optional Google Gemini reasoning provider for evidence planning,
  grounded summaries and unified open-ended answer synthesis.
- Keeps MCP tool execution and controls local, redacts the Gemini API key, and
  falls back through Ollama Cloud and local Ollama on quota or transport errors.
- Stops an MCP `available: false` result with no release-channel metadata from
  claiming the hub is fully up to date; beta/preview availability is now
  explicitly qualified against the Hubitat admin UI.
