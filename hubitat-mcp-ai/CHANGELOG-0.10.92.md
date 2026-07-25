# Hubitat MCP AI 0.10.92

## Fixed

- Named-device NOT_FOUND results are now terminal and no longer fall back to unrelated room devices.
- Room prefixes such as `Bedroom 2` are inferred from the authoritative Hubitat inventory before confidence scoring.
- Sparse MCP inventory aliases such as `deviceId`, `displayName`, and `deviceLabel` are supported by the shared resolver.
- Exact named reads continue to work with sparse inventory payloads.
- Room-level metric probing remains available only for verified room queries.

## Validation

- Repository layout validation passed.
- Python compilation passed.
- Blocking release gate passed: 256 tests.
