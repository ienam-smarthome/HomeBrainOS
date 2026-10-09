# Hubitat MCP AI 0.16.124

## Changed

- Short, problem-first responses for explicit broken-automation inventory questions, without dumping every enabled app.
- Show exact IDs for flagged apps, while retaining detailed automation inventories for other status requests.
- Qualify empty Rule Machine results as unverified completeness; distinguish an empty result from tool failure and avoid claiming no Rule Machine rules exist.
- Clearly state that configuration markers do not verify runtime execution or device dependencies.

## Safety

- No Hubitat app or rule changes; read-only diagnostic inventory only.
- Broader action-level and dependency diagnostics remain future work in issue #725.
