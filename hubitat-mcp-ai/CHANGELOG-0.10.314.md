# Hubitat MCP AI 0.10.314

## Changed

- Replaces the production-wide `GroundingPolicy` module monkey-patch with a request-local grounding-policy factory.
- Selects `LiveEvidenceAuthority` only inside the active production request context.
- Keeps direct base-agent callers on the original deterministic `GroundingPolicy` implementation.
- Makes the live authority compatible with the base orchestrator signature while continuing to ignore stale external evidence flags.

## Safety

- Removes shared mutable grounding selection across concurrent requests.
- Keeps evidence recorders and request metrics isolated through `ContextVar` state.
- Adds concurrent-task tests proving one production request cannot receive another request's evidence recorder.

## Validation

- Adds production factory selection, base-agent isolation, stale-flag, and concurrency regression tests.
