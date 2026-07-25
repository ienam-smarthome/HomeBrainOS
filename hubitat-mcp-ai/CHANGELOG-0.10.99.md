# Hubitat MCP AI 0.10.99

## Changed

- Room inventories now show multiple useful live states for a device.
- Temperature and humidity are presented together when both are available.
- Switch, motion, contact and presence states remain visible alongside sensor values.
- Battery remains the fallback when no more useful live state exists.

## Fixed

- Multi-attribute devices no longer lose secondary states in room listings.
- Hallway Meter now appears as `29.2°C, 36% humidity` instead of temperature only.

## Validation

- Focused room inventory suite passed: 7 tests.
- Room inventory selection passed: 16 tests.
- Blocking release gate passed: 272 tests.
