# Hubitat MCP AI 0.10.174

## Changed

- Migrated broad semantic whole-home summary and attention handling into
  `AnswerGuardRegistry` as a terminal route.
- Preserved semantic intent classification, verified evidence collection,
  synthesis and category-specific attention filtering.
- Preserved passthrough for write-like requests, direct device questions and
  failed evidence collection.
- Added an isolated compatibility adapter around the legacy installer.

## Safety

- No deterministic write, confirmation, named-rule, thermostat or climate route
  behaviour was changed.
- No other answer guard or terminal route was migrated in this release.

## Validation

- Focused passthrough, terminal-response and entrypoint-ordering tests.
- Existing semantic home query, answer-guard registry and request-layer tests.
- Repository validation, Python compilation and blocking release gate.
