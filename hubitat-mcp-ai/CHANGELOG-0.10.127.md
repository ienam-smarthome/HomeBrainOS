# Hubitat MCP AI 0.10.127

## Added

- Added a transparent 120-second freshness-aligned power comparison.
- Raw monitored-device totals remain unchanged and fully visible.
- Fresh monitored power includes only active readings within 120 seconds of the whole-house meter timestamp.
- Added fresh unaccounted power and fresh coverage values.
- Added warning tiles for stale readings and readings with unavailable timestamps.
- Added meter-to-device skew details for excluded readings.

## Behaviour

- Raw totals remain the primary accounting figures.
- Fresh figures are shown only as an additional timestamp-aligned comparison.
- Stale readings are never silently discarded.
- Readings without usable timestamps remain included in raw totals but are excluded from the fresh comparison.

## Validation

- Focused power-accounting and routing tests passed: 30 tests.
- Energy and power test suite passed: 58 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
