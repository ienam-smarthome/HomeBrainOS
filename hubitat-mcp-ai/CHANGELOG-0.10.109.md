# Hubitat MCP AI 0.10.109

## Changed

- Live semantic metric reads now use the shared capability snapshot as the primary evidence source.
- Valid compact current-state measurements return immediately without running detailed or all-device fallbacks.
- Direct capability queries remain available only as compatibility fallbacks.
- Repeated power, energy, temperature, humidity, battery and illuminance reads can reuse the same capability snapshot within its configured TTL.

## Validation

- Single-pass, live-cache and shared-snapshot tests passed: 8 tests.
- Power, metric, device-index and state-broker selection passed: 31 tests.
- Blocking release gate passed: 279 tests.
