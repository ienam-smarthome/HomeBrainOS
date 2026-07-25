# Hubitat MCP AI 0.10.122

## Improved

- Whole-house comparison quality now depends on the whole-house meter timestamp and active monitored-device timestamps.
- Stale zero-watt devices no longer make the main accounting comparison appear stale.
- Active-reading timestamp spread is reported separately from all-reading spread.
- Missing Octopus meter timestamps now produce an explicit unknown comparison-quality reason.
- Meter-to-device comparison skew is reported when authoritative timestamps are available.

## Validation

- Focused power-accounting and routing tests passed: 24 tests.
- Energy and power test suite passed: 52 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
