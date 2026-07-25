# Hubitat MCP AI 0.10.116

## Fixed

- Explicit attention-category questions now return only the requested category.
- `offline devices` returns offline devices without unrelated low-battery warnings.
- `stale devices`, `low batteries`, `warnings`, and `updates` are scoped independently.
- Broad questions such as `what needs attention?` continue to return all current issue categories.
- Unrelated open contacts and lights-on state are excluded from category-specific attention responses.

## Validation

- Scoped semantic-attention tests passed: 13 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
