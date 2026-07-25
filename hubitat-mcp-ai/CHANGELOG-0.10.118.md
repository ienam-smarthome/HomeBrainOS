# Hubitat MCP AI 0.10.118

## Fixed

- Whole-house power-accounting queries now run before generic device-attribute entity resolution.
- `How much power is unaccounted for?` is no longer interpreted as a request for a device named `unaccounted for`.
- Verified power accounting remains deterministic and uses one detailed Hubitat device read.
- Normal named-device power questions such as `How much power is Fridge using?` continue through the device-reading route.

## Validation

- Focused routing and accounting tests passed: 15 tests.
- Energy and power test suite passed: 45 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
