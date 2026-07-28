# 0.10.198

- Replaced manual request routing and entity-resolution middleware with one native
  Gemini function-calling agent driven by live Hubitat MCP schemas.
- Added a cached live device manifest to the agent system instruction.
- Routed both `/api/ask` and `/api/chat` through the unified agent.
- Removed the legacy router, resolver, arbiter, and control-rescue modules.
