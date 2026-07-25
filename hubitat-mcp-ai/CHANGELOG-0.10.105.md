# Hubitat MCP AI 0.10.105

## Changed

- Power-summary technical diagnostics now contain compact counts, totals and device labels.
- Full normalised, active and idle reading arrays are no longer duplicated in technical output.
- Structured power-reading fields remain available for cards and deterministic processing.

## Fixed

- HomeBrain Web UI no longer renders an identical structured result title twice.
- Room and power cards now show one heading followed by their subtitle, metrics and devices.

## Validation

- Focused compact-diagnostics and Web UI title tests passed: 2 tests.
- Power and control-focus test selection passed: 19 tests.
- Blocking release gate passed: 279 tests.
