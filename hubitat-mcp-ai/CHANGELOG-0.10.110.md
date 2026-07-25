# Hubitat MCP AI 0.10.110

## Changed

- Live metric summaries now use the shared compact all-device snapshot as their primary evidence source.
- Power, energy, temperature, humidity, battery and illuminance values are filtered locally from live current-state data.
- Capability-filtered and detailed reads remain compatibility fallbacks only.
- Repeated power summaries can reuse the shared device snapshot within its configured TTL.

## Validation

- Shared-summary, live-cache and snapshot tests passed: 8 tests.
- Power, metric, device-index and state-broker selection passed: 31 tests.
- Blocking release gate passed: 279 tests.
