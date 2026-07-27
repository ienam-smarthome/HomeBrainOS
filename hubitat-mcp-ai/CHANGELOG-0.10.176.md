# Hubitat MCP AI 0.10.176

## Changed

- Migrated exact whole-home summary phrases into `AnswerGuardRegistry` as a
  terminal route.
- Preserved verified semantic evidence collection, required-fact validation,
  synthesis fallback and response metadata.
- Preserved passthrough when the query does not match or evidence collection
  fails.
- Retained the legacy installer for standalone compatibility.

## Safety

- The broader semantic home query route remains unchanged.
- Deterministic writes, confirmations, thermostat handling, climate handling,
  named-rule handling and answer guards are unchanged.

## Validation

- Focused terminal-answer, passthrough and entrypoint-ordering tests.
- Existing registry, request-layer and blocking release validation suites.
