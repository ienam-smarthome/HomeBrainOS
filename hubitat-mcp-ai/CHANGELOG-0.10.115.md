# Hubitat MCP AI 0.10.115

## Fixed

- Merged the authoritative live device-health reader into semantic whole-home attention summaries.
- Devices reporting `healthStatus: offline` are no longer omitted when low batteries are also present.
- Added compatibility with structured and display-item health response formats.
- Prevented duplicate offline or stale entries when evidence sources overlap.

## Expected live result

- Tuya Remote (bedroom 3) is reported offline when Hubitat exposes `healthStatus: offline` and `rtt: timeout`.
- Roborock Q7 Max is reported offline when Hubitat exposes `healthStatus: offline` or a Wi-Fi-offline health detail.
- Livingroom TRV and Fridge Door remain listed separately as low-battery devices.

## Validation

- Semantic attention device-health regression tests passed.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
