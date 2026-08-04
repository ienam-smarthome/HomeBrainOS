# Hubitat MCP AI 0.10.330

## Changed

- Added deterministic current-attribute follow-ups for a selected clarification device.
- Added deterministic active/inactive motion-sensor aggregation.
- Bypassed provider and tool-discovery rounds for those bounded live reads.
- Removed presentation-only leading articles from clarification choices.

## Validation

- Added parser and presenter regression coverage for humidity, temperature, battery, power, and motion queries.
- Explicit historical wording remains outside the current-state fast path.
