# Hubitat MCP AI 0.10.165

## Changed

- Dashboard power values below 1,000 watts remain displayed in watts.
- Dashboard power values at or above 1,000 watts are displayed in kilowatts.
- Compact formatting preserves useful precision, including `3.19 kW` for
  `3,190 W` and `160.9 W` for a sub-kilowatt monitored-device total.

## Validation

- Power-unit threshold and rendered-dashboard regressions.
- Desktop and mobile dashboard visual checks.
- Add-on validation, compilation, architecture analysis and release gate.
