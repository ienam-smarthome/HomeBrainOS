# Hubitat MCP AI 0.10.103

## Changed

- Multi-word room names are preserved when followed by `devices`.
- Explicit phrases ending in `room devices` remain supported.
- Room inventory response text now uses the natural room title.

## Fixed

- `Show living room devices` no longer searches for a device named `living room devices`.
- `Show the Livingroom room devices` correctly resolves to `Livingroom`.
- Room inventory messages no longer say `Living Room room`.

## Validation

- Focused parser and room inventory suite passed: 15 tests.
- Room inventory selection passed: 20 tests.
- Blocking release gate passed: 276 tests.
