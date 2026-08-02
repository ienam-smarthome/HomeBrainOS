# Hubitat MCP AI 0.10.300

## Added

- Recorded `tool_discovery_calls` at the exact `hub_search_tools` execution boundary.
- Recorded cumulative `tool_discovery` duration for successful and failed discovery calls.
- Added request-local active metric helpers so deep execution components can report fixed metrics without prompt-derived labels.
- Added focused success, failure, and non-discovery regression tests.

## Safety

- Only the fixed metric vocabulary is accepted.
- Search queries, tool arguments, device names, credentials, and session identifiers are never stored as metric labels.
- Failed discovery attempts are measured without changing their execution or grounding behaviour.
