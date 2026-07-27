# Hubitat MCP AI 0.10.168

## Changed

- Migrated execution-contract annotation into the ordered
  `AnswerGuardRegistry`.
- Preserved the existing execution-lane and verification-state response fields.
- Preserved the surrounding request-wrapper order by installing the registry at
  the former execution-contract layer position.
- Kept the legacy execution-contract installer for standalone compatibility.

## Safety

- No deterministic write, confirmation, semantic evidence or terminal-route
  logic was changed.
- No other answer guard was migrated in this release.

## Validation

- Focused guard behaviour, single-delegation and entrypoint-wiring tests.
- Existing answer-guard registry and request-composition tests.
- Repository validation, Python compilation and blocking release gate.
