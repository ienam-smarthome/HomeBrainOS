# Hubitat MCP AI 0.10.106

## Changed

- Natural Octopus family queries now route directly to the grouped whole-house meter summary.
- Octopus discovery now starts with one filtered detailed inventory request.
- The complete device index is used only as a fallback.
- Device detail reads are limited to displays that do not already contain a valid live value.
- Octopus technical diagnostics now contain compact display summaries instead of full detailed device payloads.

## Fixed

- `show octopus` no longer attempts to find one device named `octopus`.
- `show octopus devices` no longer attempts to find one device named `octopus devices`.
- Placeholder identity strings are no longer treated as valid Octopus meter readings.
- Existing period queries continue to return verified values such as current power, today, yesterday, week and month.

## Validation

- Natural routing and efficiency tests passed: 4 tests.
- Octopus and energy test selection passed: 9 tests.
- Blocking release gate passed: 279 tests.
