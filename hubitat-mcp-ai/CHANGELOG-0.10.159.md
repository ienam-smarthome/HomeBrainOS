# Hubitat MCP AI 0.10.159

## Removed

- Removed `humidity_home_insight.py`, `thermal_home_insight.py` and
  `named_rule_match_guard.py`, which had no production importers.
- Removed the implicitly loaded `sitecustomize.py` compatibility hook after
  verifying its structured-result behavior is owned directly by
  `mcp_client.py`.
- Removed the test-only suites that kept the three dead helper modules alive.

## Changed

- Migrated structured MCP response tests to exercise
  `HubitatMCPClient.call_tool` directly.
- Added structural coverage pinning the zero-orphan module boundary.

## Validation

- Focused structured-result and orphan-removal tests.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
