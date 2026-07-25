# Hubitat MCP AI 0.10.90

## Fixed

- Shared room words no longer make unrelated devices appear ambiguous.
- Named-device resolution now requires matching descriptive tokens such as `meter`, `light`, or `FP1`.
- `Bedroom 2 Meter` no longer suggests `Bedroom 2 Light` or `Bedroom 2 FP1`.
- Exact device labels continue to override broader room matches.

## Validation

- Repository layout validation passed.
- Python compilation passed.
- Blocking release gate passed: 250 tests.
