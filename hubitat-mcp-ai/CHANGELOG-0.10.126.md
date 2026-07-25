# Hubitat MCP AI 0.10.126

## Fixed

- Added a bounded targeted-device fallback for live power accounting.
- When bulk detailed inventory is empty, HomeBrain now reads the plain inventory and probes only likely power-capable devices.
- Targeted detail reads use hub_get_device with deviceId.
- Added normalized PowerMeter capability matching.
- Whole-house, monitored, unaccounted and coverage values can now recover even when bulk detailed inventory is unavailable.
- The Power breakdown tile is restored from targeted live readings.

## Safety

- Targeted detail probing is capped at 32 devices.
- Non-power devices are excluded from the fallback.
- Power totals remain unavailable when no authoritative detail readings can be recovered.

## Validation

- Focused power-accounting and routing tests passed: 28 tests.
- Energy and power test suite passed: 56 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
