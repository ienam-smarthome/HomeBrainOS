# Hubitat MCP AI 0.10.120

## Improved

- Whole-house power accounting now preserves fractional watt precision.
- Structured Octopus power attributes are preferred over display-text parsing.
- Duplicate Octopus current-power devices are selected by exact label, enabled state, structured evidence and newest activity timestamp.
- All Octopus whole-house power rows are excluded from individual-device totals.
- Power readings now retain activity timestamps and evidence-source metadata.
- Results report timestamp quality and maximum reading skew.
- Historical usage and billing questions no longer route to live power accounting.
- Power-accounting Python and test files are normalized to plain UTF-8 without BOM.

## Validation

- Focused power-accounting and routing tests passed: 21 tests.
- Energy and power test suite passed: 49 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
