# Hubitat MCP AI 0.10.338

## Changed

- Removes `request_lifecycle_context.py`: a request-scoped `ContextVar`
  lifecycle helper added on its own commit and never imported anywhere.
  Confirmed via `scripts/analyze_imports.py` orphan-module detection. Its
  intended purpose is already covered by `DirectOutcomeContext`'s more
  specific multi-`ContextVar` handling.
- Extracts local-tool catalog assembly out of
  `mcp_agent_orchestrator.UnifiedMCPAgent._process_user_request` into a new
  `tool_catalog_assembly.py` module (`build_request_tool_catalog`). Behavior
  is unchanged — same tools, same order — this only removes eleven local
  variable bindings and their imports from the main request loop.
  `mcp_agent_orchestrator.py` drops from 1,026 to 999 lines.

## Validation

- Adds `tests/test_tool_catalog_assembly.py` covering local-tool inclusion,
  remote-tool preservation, and the full assembled tool count.
- Removes the now-stale `request_lifecycle_context.py` row from
  `docs/RUNTIME-MODULE-MAP.md`; adds a row for `tool_catalog_assembly.py`.
- `python3 -m pytest -q` (502 passed).
- `python3 scripts/analyze_imports.py` reports zero orphan modules.
- `python3 scripts/validate_addon.py` (repository layout and version
  alignment OK).

## Note

This is a first, low-risk extraction from `mcp_agent_orchestrator.py`, not a
full decomposition. The core `_process_user_request` loop (confirmation flow,
rule-authoring proposal handling, the provider tool-calling loop, and outcome
construction) is still one method and is the next, higher-risk target —
each of those seams is more deeply coupled to `self` state and needs its own
focused extraction with dedicated tests, similar to how
`direct_outcome_context.py` was pulled out previously.
