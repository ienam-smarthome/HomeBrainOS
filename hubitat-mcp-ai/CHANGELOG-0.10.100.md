# Hubitat MCP AI 0.10.100

## Changed

- Room inventory now performs bounded detail reads for empty illuminance sensor summaries.
- Detailed illuminance values are merged into the room item when available.
- Illuminance is displayed using `lx`.

## Fixed

- Lux child devices no longer show only `Available` when Hubitat detail data contains a live illuminance value.
- Hallway FP300 Lux can now appear as `3 lx` in the Hallway room inventory.
- Detail probing is limited to likely empty lux sensors and capped at four devices per room request.

## Validation

- Focused room inventory suite passed: 8 tests.
- Room inventory selection passed: 17 tests.
- Blocking release gate passed: 273 tests.
