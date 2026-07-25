# Hubitat MCP AI 0.10.124

## Fixed

- Power accounting now retries once with the plain authoritative Hubitat inventory when a detailed projected device snapshot is empty.
- Empty device snapshots are no longer interpreted as 0 W monitored power.
- When both reads are empty, the interface shows Device snapshot unavailable instead of misleading power totals.
- Added diagnostics for projected row count, retry use and retry row count.

## Included

- Consolidated Power breakdown tile showing monitored total, active device count and the five largest loads.
- Separate meter-to-device comparison quality and active-reading timestamp spread.

## Validation

- Focused power-accounting and routing tests passed: 27 tests.
- Energy and power test suite passed: 55 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
