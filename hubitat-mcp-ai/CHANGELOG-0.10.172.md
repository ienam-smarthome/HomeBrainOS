# Hubitat MCP AI 0.10.172

## Changed

- Migrated exact named Rule Machine status reads into the ordered
  `AnswerGuardRegistry` as a terminal route.
- Preserved exact matching, clarification choices, disabled and paused state
  reporting, deterministic wording and action buttons.
- Preserved the original route position after climate extrema handling and
  before execution-contract annotation.
- Retained the legacy named-rule status installer for standalone compatibility.

## Safety

- Unmatched queries do not trigger a Rule Machine inventory read.
- No rule write, pause, resume, enable or disable behaviour changed.
- No other answer guard or terminal route was migrated.

## Validation

- Focused unmatched delegation, matched terminal response and entrypoint-order
  tests.
- Existing named-rule status and registry tests.
- Repository validation, Python compilation and blocking release gate.
