# Hubitat MCP AI 0.14.7

## Clearer System Check findings

- Remove the redundant `WARNING:` / severity text prefix from System Check
  finding rows.
- Colour critical device states such as unavailable/offline devices and broken
  automations red.
- Colour warning states such as low battery, stale telemetry, paused items, and
  warning findings amber.
- Keep informational findings neutral and resolved findings green.
- Preserve the existing finding text, details, occurrence counts, grouping, and
  Pushover report behaviour.
