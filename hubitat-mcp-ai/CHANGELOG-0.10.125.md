# Hubitat MCP AI 0.10.125

## Fixed

- Power-accounting fallback now retains detailed device mode while removing only the fields projection.
- The fallback inventory therefore includes live device attributes required for power readings.
- Empty projected snapshots can now recover into a valid whole-house and monitored-device comparison.
- The Power breakdown tile is restored when the fallback returns active power readings.

## Validation

- Focused power-accounting and routing tests passed: 27 tests.
- Energy and power test suite passed: 55 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
