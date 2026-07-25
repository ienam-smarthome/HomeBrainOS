# Hubitat MCP AI 0.10.117

## Added

- Deterministic whole-house power accounting using the Octopus current-power meter.
- Comparison between whole-house demand and individually monitored device readings.
- Calculated unaccounted power and monitored-device coverage percentage.
- Largest monitored loads included in the result.
- One canonical detailed Hubitat device read is used for the complete calculation.

## Routing

The following requests now use the verified power-accounting route:

- `How much power is unaccounted for?`
- `Compare whole-house power with monitored devices`
- `Why is my electricity usage high right now?`
- `Show power coverage`

Broader advice requests such as `How can I reduce my electricity bill?` continue to use AI analysis.

## Validation

- Focused routing and accounting tests passed: 13 tests.
- Energy and power test suite passed: 43 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
