# Hubitat MCP AI 0.10.212

- Loads the device manifest only for device and whole-home state requests.
- Uses lean domain-specific gateway sets instead of declaring the full MCP
  registry for unmatched questions.
- Expands the declared gateway set dynamically when `hub_search_tools`
  identifies a relevant gateway.
- Bounds large MCP result payloads and directs the agent to use narrower
  queries or pagination.
- Adds prompt, Ollama round, MCP call, and registry-expansion timing logs.
