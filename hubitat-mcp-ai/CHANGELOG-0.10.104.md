# Hubitat MCP AI 0.10.104

## Changed

- Room inventory enrichment now supports additional empty-state device types.
- Added room presentation for power, energy, thermostat, lock, valve, water and smoke states.
- Detailed device responses now preserve common thermostat, metering and safety attributes.
- Room inventory technical diagnostics now use compact counts instead of embedding the full selected-device inventory.

## Fixed

- Empty thermostat and power-meter summaries can now be completed by bounded detail reads.
- Locks, valves, water sensors and smoke sensors can now show meaningful live states.
- Large room-inventory technical responses no longer include the full 100+ device inventory.

## Safety and performance

- Detail enrichment remains capped at four devices per room request.
- Only devices assigned to the matched room are considered for detail enrichment.
- Existing lux and fan enrichment remains unchanged.

## Validation

- Focused parser and room inventory suite passed: 18 tests.
- Room inventory selection passed: 23 tests.
- Blocking release gate passed: 279 tests.
