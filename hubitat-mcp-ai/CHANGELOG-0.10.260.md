# Hubitat MCP AI 0.10.260

- Extract pure local MCP tool schema builders into `tool_registry.py`.
- Extract prompt-only request classification helpers into `request_classification.py`.
- Keep `UnifiedMCPAgent` as the coordinator while preserving existing class-level compatibility shims.
- Reduce the size and change surface of `mcp_agent_orchestrator.py` without changing stateful transport, confirmation, or mutation-safety behaviour.
- Add regression coverage for the extracted helper modules and compatibility surface.
