# Hubitat MCP AI 0.10.127

## Added

- Added a consolidated Power summary tile.
- Added a 120-second timestamp-aligned fresh power comparison.
- Added fresh monitored power, fresh unaccounted power and fresh coverage.
- Added warning tiles for stale and missing-timestamp readings.
- Preserved the complete raw monitored-device total.

## Display order

1. Power summary
2. Power breakdown
3. Freshness warnings, when applicable
4. Active monitored-device tiles

## Validation

- Focused tests: 31 passed.
- Energy and power tests: 59 passed.
- Release gate: 279 passed.
