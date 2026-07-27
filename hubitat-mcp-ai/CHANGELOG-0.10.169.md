# Hubitat MCP AI 0.10.169

## Changed

- Migrated the home-summary consistency check into `AnswerGuardRegistry`.
- Preserved its exact request-stack position before thermostat and climate
  handlers.
- Kept semantic home evidence and attention routes exempt from rewriting.
- Retained the legacy installer for standalone compatibility.

## Safety

- No deterministic write, confirmation, semantic evidence or terminal-route
  logic changed.
- No other answer guard was migrated in this release.

## Validation

- Focused home-summary guard and entrypoint-wiring tests.
- Existing answer-guard registry and request-composition tests.
- Repository validation, Python compilation and blocking release gate.
