# Hubitat MCP AI 0.10.121

## Fixed

- Whole-house power accounting now merges duplicate nested representations of each Hubitat device.
- Sparse duplicate records no longer overwrite complete detailed device evidence.
- Live Octopus power and individual monitored-device readings are preserved from detailed MCP snapshots.
- Technical diagnostics now report the extracted merged-device row count.

## Validation

- Focused power-accounting and routing tests passed: 22 tests.
- Energy and power test suite passed: 50 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
