# Hubitat MCP AI 0.10.93

## Changed

- Deterministic room-level attribute reads no longer use fuzzy device-label ranking.
- Room metric candidates are confined to exact room membership.
- Attribute-compatible and attribute-supporting devices are selected in deterministic order.
- Named-device resolution remains handled by the shared confidence resolver.
- The legacy fuzzy ranker is no longer called from deterministic room reads.

## Validation

- Repository layout validation passed.
- Python compilation passed.
- Focused resolver suite passed: 40 tests.
- Blocking release gate passed: 259 tests.
