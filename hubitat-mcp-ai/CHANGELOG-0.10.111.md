# Hubitat MCP AI 0.10.111

## Added

- Compact MCP event details in request performance diagnostics.
- Safe read-argument reporting for device, capability, format and projection requests.
- Cache hit, miss, age, duration and gateway information for each logical MCP call.

## Security

- Only an allowlisted set of non-sensitive MCP arguments is exposed.
- Unknown or potentially sensitive tool arguments remain hidden.

## Validation

- MCP observability and live metric tests passed: 7 tests.
- Blocking release gate passed: 279 tests.
