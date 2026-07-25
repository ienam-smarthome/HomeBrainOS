# Hubitat MCP AI 0.10.94

## Fixed

- Natural room metric questions no longer produce truncated targets such as `in the bathr`.
- Room clauses are removed using the already-normalised target rather than an index from the original query.
- Complete room names ending in `Room`, including `Living Room`, are preserved.
- Questions such as `What is the humidity in the bathroom?` now retain the room as the deterministic metric target.
- Exact-room metric routing continues to restrict authoritative reads to devices assigned to that room.

## Validation

- Repository layout validation passed.
- Python compilation passed.
- Focused entity-read suite passed: 52 tests.
- Blocking release gate passed: 265 tests.
