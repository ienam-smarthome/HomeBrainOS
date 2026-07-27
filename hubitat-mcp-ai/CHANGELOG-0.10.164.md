# Hubitat MCP AI 0.10.164

## Added

- An **Active rooms** dashboard tile showing rooms with current motion and/or
  lights switched on.
- A **Power** dashboard tile showing whole-house demand alongside the total and
  count of active monitored-device readings.

## Changed

- Dashboard summaries now use a balanced three-column desktop grid and retain
  the existing two-column mobile layout.
- Dashboard room and power sources fail independently, preserving all other
  live summary data when either source is unavailable.

## Validation

- Active-room classification and room deduplication regressions.
- Dashboard API power-accounting and fail-open regressions.
- Rendered desktop and mobile dashboard checks.
- Add-on validation, import and cluster analysis, compilation and release gate.
