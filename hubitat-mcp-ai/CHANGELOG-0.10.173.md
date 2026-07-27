# Hubitat MCP AI 0.10.173

## Changed

- Migrated Hubitat health display enrichment into `AnswerGuardRegistry`.
- Preserved installed firmware, software-update and database-size metrics.
- Preserved the guard's original request-stack position before semantic home
  summary handling.
- Retained the legacy installer for standalone compatibility.

## Safety

- Non-hub-health answers remain unchanged.
- No MCP reads, deterministic writes, confirmations, terminal routes or other
  answer guards were changed.

## Validation

- Focused hub-health enhancement, pass-through and entrypoint-wiring tests.
- Existing answer-guard registry and request-layer analyser tests.
- Repository validation, Python compilation and blocking release gate.
