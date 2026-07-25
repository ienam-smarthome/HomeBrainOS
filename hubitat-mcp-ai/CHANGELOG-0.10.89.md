# Hubitat MCP AI 0.10.89

## Improved

- Deterministic entity reads now use the shared confidence-based resolver.
- Ambiguous device names return a clarification instead of guessing.
- Exact and confidently resolved device reads remain bound to one authoritative device ID.
- Room-level metric questions such as `bathroom humidity` retain bounded attribute-capable probing.
- Entity-resolution diagnostics now expose confidence, candidates, match reasons, and resolution status.

## Validation

- Repository layout validation passed.
- Python compile validation passed.
- Blocking release gate passed: 248 tests.
