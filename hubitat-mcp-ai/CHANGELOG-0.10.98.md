# Hubitat MCP AI 0.10.98

## Changed

- Exact-room metric questions now collect all valid readings from bounded matching devices.
- Multiple humidity, temperature or illuminance sensors in one room are reported together.
- Named-device metric questions remain singular and probe only the resolved device.
- Structured metric responses now include a `readings` collection.

## Fixed

- Hallway humidity questions no longer stop after the first valid sensor.
- Multi-attribute devices such as Hallway Meter can contribute their requested attribute.
- Additional exact-room sensors are no longer silently omitted.

## Validation

- Focused deterministic entity-read suite passed: 36 tests.
- Blocking release gate passed: 272 tests.
