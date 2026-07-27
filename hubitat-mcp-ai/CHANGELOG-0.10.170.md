# Hubitat MCP AI 0.10.170

## Changed

- Split thermostat handling into a registry terminal route for direct live-state
  reads and a registry answer guard for summary correction.
- Installed both steps through `AnswerGuardRegistry` at the former thermostat
  wrapper position.
- Preserved live Hubitat evidence reads, deterministic direct answers and
  thermostat correction metadata.
- Retained the legacy combined installer for standalone compatibility.

## Safety

- No thermostat matching, evidence, correction or user-facing response logic was
  changed.
- No other answer guard or terminal route was migrated in this release.

## Validation

- Focused terminal-route, answer-guard, ordering and entrypoint-wiring tests.
- Existing thermostat, answer-guard registry and request-composition tests.
- Repository validation, Python compilation and blocking release gate.
