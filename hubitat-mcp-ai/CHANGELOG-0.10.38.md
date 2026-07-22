# Hubitat MCP AI 0.10.38

- Reads Hubitat sensor attributes when `currentStates`, `attributes`, or `states`
  are returned as lists of `{name, currentValue}` records.
- Recognises common Hubitat aliases such as `lux` and `illuminanceLevel` while
  preserving valid zero readings.
- Keeps dictionary-shaped current-state responses fully compatible.
- Adds deterministic regressions for the FP2 Bedroom 3 Lux response shape.
