# 0.10.428

- Add an opt-in ChatGPT-facing Streamable HTTP MCP endpoint at `/mcp`.
- Expose a deliberately small HomeBrainOS tool surface: health, dashboard state, and confirmation-aware smart-home requests through the existing `UnifiedMCPAgent`.
- Preserve MCP session IDs as HomeBrainOS session IDs so confirmations and device-disambiguation context remain isolated to one MCP conversation.
- Mark read-only tools and the write-capable HomeBrainOS request tool with MCP safety annotations.
- Add optional bearer authentication, required by default when ChatGPT MCP support is enabled.
- Keep the existing Home Assistant ingress WebUI and `/api/*` endpoints unchanged.
