# Hubitat MCP AI 0.10.122

## Improved

- Added a consolidated Power breakdown tile to whole-house power accounting.
- The tile shows total monitored power, active monitored-device count and the five largest loads.
- Individual monitored-device tiles remain available below the consolidated breakdown.
- Whole-house comparison quality now uses the meter and active-device timestamps.
- Idle zero-watt readings no longer make the main comparison appear stale.
- Active-reading and all-reading timestamp spreads are reported separately.

## Validation

- Focused power-accounting and routing tests passed: 25 tests.
- Energy and power test suite passed: 53 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
