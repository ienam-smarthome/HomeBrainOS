# Hubitat MCP AI 0.10.167

## Added

- An ordered `AnswerGuardRegistry` primitive for same-tier terminal routes and
  answer guards.
- A single published request wrapper while keeping small route and guard
  functions independently testable.
- Deterministic registration ordering with catalogue metadata for each
  registered step.

## Safety

- Rejects duplicate registry step names.
- Rejects late registration after the registry is installed.
- Detects untracked `application.ask` mutation before installation.
- Leaves existing runtime guards and terminal routes unmigrated, so routing
  behaviour is unchanged in this release.

## Validation

- Focused ordering, delegation, catalogue and safety regression tests.
- Existing request-composition and request-layer analyzer tests.
- Repository validation, Python compilation and blocking release gate.
