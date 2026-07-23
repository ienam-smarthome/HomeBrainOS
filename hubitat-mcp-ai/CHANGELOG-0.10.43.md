# Hubitat MCP AI 0.10.43

## Natural deterministic measurement responses

- Bathroom humidity now reads as `Bathroom humidity is 66%.` rather than `Bathroom meter is 66 %.`
- Percent and Celsius values are formatted without a space before the unit.
- Power, energy and lux values keep their standard unit spacing.
- Added regression coverage for humidity, temperature, power and illuminance wording.
