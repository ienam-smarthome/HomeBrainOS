# Hubitat MCP AI 0.10.97

## Fixed

- Renamed the new route-priority package from `routing` to `route_registry`.
- Prevented the package from shadowing the existing `routing.py` runtime module.
- Restored imports of `dedupe_current_query` and `is_fast_path_query`.
- Added a regression test for the module-name collision.

## Validation

- Existing routing module import verified.
- Route registry package import verified.
- Focused route registry suite passed: 10 tests.
