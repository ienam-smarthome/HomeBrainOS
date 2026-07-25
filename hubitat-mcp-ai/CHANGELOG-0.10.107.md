# Hubitat MCP AI 0.10.107

## Changed

- Read-only metric queries now reuse capability-specific device snapshots.
- Power, energy, temperature, humidity, battery and illuminance comparisons no longer invalidate the complete device cache before every request.
- Metric metadata fallback now reuses the existing device-index snapshot.
- Existing capability TTL, locking and concurrent request coalescing are now effective for semantic metric reads.

## Performance

- The first metric request may refresh the relevant detailed capability snapshot.
- Repeated requests within the capability snapshot TTL can reuse the same authoritative evidence.
- Device control and other write operations continue to invalidate cached device evidence.

## Validation

- Shared metric snapshot tests passed: 3 tests.
- Power, metric, device-index and state-broker selection passed: 26 tests.
- Blocking release gate passed: 279 tests.
