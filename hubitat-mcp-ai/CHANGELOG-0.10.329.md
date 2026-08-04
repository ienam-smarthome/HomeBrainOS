# Hubitat MCP AI 0.10.329

## Changed

- Added `request_lifecycle_context.py` as the request-scoped ContextVar lifecycle boundary.
- Documented the new runtime module in the canonical runtime module map.
- Kept request metrics, outcomes, evidence, and tool execution outside the lifecycle-context boundary.

## Validation

- Runtime module-map drift remains enforced by the blocking release gate.
- The add-on version is bumped because the shipped runtime changed.
