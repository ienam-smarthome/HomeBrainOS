# Hubitat MCP AI 0.10.101

## Changed

- Room inventory now performs bounded detail reads for empty fan summaries.
- Fan speed is preserved and presented as a live room state.
- Top-level detailed fan attributes now include `speed` and `supportedFanSpeeds`.

## Fixed

- Fans with empty compact `currentStates` no longer show only `Available`.
- Standing Fan now appears as `Off`, `Low`, `Medium`, `High` or `Auto` when Hubitat detail data exposes its speed.
- Empty-device fallback now supports both illuminance sensors and fan-control devices.

## Validation

- Focused room inventory suite passed: 9 tests.
- Room inventory selection passed: 18 tests.
- Blocking release gate passed: 274 tests.
