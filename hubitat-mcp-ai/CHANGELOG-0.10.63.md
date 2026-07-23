# Hubitat MCP AI 0.10.63

- Removes the stale startup hook in `mcp_tool_catalogue.py` that reset the running application and FastAPI versions to `0.10.56`.
- Makes the version baked into `/app/.homebrain-build-version` the sole runtime authority.
- Adds a regression proving the MCP tool catalogue installer cannot mutate version state during startup.
- Retains `/api/runtime-version` for direct baked/application/API/rendered version comparison.
