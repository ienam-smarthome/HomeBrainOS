# Hubitat MCP AI 0.10.108

## Fixed

- Live semantic metric reads no longer invalidate the shared device cache before every request.
- The live metric executor no longer forces a fresh capability catalogue fallback.
- Repeated power, energy, temperature, humidity, battery and illuminance reads can now reuse broker and device-index evidence within their configured TTL.
- Device writes continue to invalidate cached device evidence.

## Validation

- Live and shared metric cache tests passed: 5 tests.
- Power, metric, device-index and state-broker selection passed: 28 tests.
- Blocking release gate passed: 279 tests.
