# Hubitat MCP AI 0.10.171

## Changed

- Migrated deterministic highest and lowest room temperature and humidity reads
  into `AnswerGuardRegistry` as a terminal route.
- Preserved room-only filtering, valid measurement ranges, deterministic wording
  and no-reading responses.
- Preserved fail-open delegation when the query does not match or live evidence
  collection raises an exception.
- Retained the legacy installer for standalone compatibility.

## Safety

- No write, confirmation, thermostat, semantic home-summary or named-rule logic
  was changed.
- No other answer guard or terminal route was migrated in this release.

## Validation

- Focused terminal-route match, delegation, selection and entrypoint-wiring tests.
- Existing answer-guard registry and climate extrema regressions.
- Repository validation, Python compilation and blocking release gate.
