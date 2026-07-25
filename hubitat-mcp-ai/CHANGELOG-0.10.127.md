# Hubitat MCP AI 0.10.127

## Added

- Added a consolidated Power summary tile.
- Added a 120-second freshness-aligned power comparison.
- Added fresh monitored power, fresh unaccounted power and fresh coverage.
- Added warnings for stale readings and missing timestamps.
- Preserved the full raw monitored-device total.
- Kept the Power breakdown and active-device tiles.

## Display order

1. Power summary
2. Power breakdown
3. Freshness warnings, when applicable
4. Active monitored-device tiles

## Validation

- Focused power tests: 31 passed.
- Energy and power tests: 59 passed.
- Release gate: 279 passed.
