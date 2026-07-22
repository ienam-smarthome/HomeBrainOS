# Hubitat MCP AI 0.10.39

## Deterministic named sensor reads

- Adds named-device reads for temperature, humidity, power, energy and battery.
- Resolves natural word orders including "What temperature is Bedroom 1?" and
  "How much power is the freezer using?".
- Reads the selected device through `hub_read_devices` instead of inferring a
  value from inventory metadata.
- Prefers a matching device that exposes the requested attribute when a room
  also contains unrelated devices.
- Preserves semantic routing for totals, comparisons and time-period questions.
- Corrects semantic comparison wording from "current current power" to
  "current power".

## Regression coverage

- Covers the real `Freezer (MQTT)` state shape where `switch` is `on` and live
  `power` is `77` watts.
- Covers humidity aliases, temperature aliases, zero values and list-shaped
  Hubitat state records.
