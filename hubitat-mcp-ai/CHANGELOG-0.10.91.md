# Hubitat MCP AI 0.10.91

## Fixed

- Missing descriptive device tokens now produce a hard entity mismatch.
- Room overlap and fuzzy similarity can no longer restore an unrelated candidate.
- `Bedroom 2 Meter` no longer suggests `Bedroom 2 TRV` or `Bedroom2 (MQTT)`.
- Exact meter labels still resolve correctly when present.

## Validation

- Repository layout validation passed.
- Python compilation passed.
- Blocking release gate passed: 252 tests.
