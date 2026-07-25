# Hubitat MCP AI 0.10.119

## Fixed

- Terminal orchestrator diagnostics now reflect the actual deterministic route.
- Whole-house power accounting reports `deterministic-power-accounting`.
- Normal device entity reads continue to report `deterministic-entity-read`.
- Unknown terminal read types use the generic `deterministic-terminal-read` label.

## Validation

- Focused orchestrator-label and power-accounting tests passed: 10 tests.
- Add-on repository validation passed.
- Blocking release gate passed: 279 tests.
