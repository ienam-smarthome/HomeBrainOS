# Hubitat MCP AI 0.10.96

## Added

- Standalone explicit route-priority package.
- Immutable Route and RouteDecision models.
- Deterministic RouteRegistry ordered by priority and registration order.
- Observable route decision fields compatible with existing trace output.
- Duplicate-name protection, unregister support and registry descriptions.

## Architecture

This release adds routing primitives only. Existing application.ask wrapper
ordering and runtime route behaviour remain unchanged.

## Validation

- Repository layout validation passed.
- Python compilation passed.
- Route registry suite passed: 9 tests.
- Blocking release gate passed: 270 tests.
