# Hubitat MCP AI 0.10.309

## Fixed

- Preserves explicit measurement units from Hubitat when resolving a named device.
- Adds conservative standard units for temperature, humidity, battery, and power only when the gateway reports the attribute but omits its unit.
- Prevents answers such as `27.0°` when the structured resolver evidence can state `27.0°C`.
- Keeps gateway-provided units such as `°F` authoritative over defaults.
- Does not mutate cached inventory records while enriching a resolved target.

## Validation

- Covers exact named-device resolution with standard units.
- Covers gateway-provided unit precedence.
- Covers non-measurement devices and inventory immutability.
