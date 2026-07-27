# Hubitat MCP AI 0.10.178

## Changed

- Consolidated the exact semantic home summary route and the broader semantic
  home query route into one ordered `AnswerGuardRegistry`.
- Preserved summary-first precedence and the existing registry position between
  hub-health display enrichment and home-summary consistency handling.
- Removed one redundant `application.ask` wrapper.

## Safety

- Route implementations, verified evidence collection, synthesis, passthrough
  behaviour, deterministic writes and confirmations are unchanged.
- Runtime HTTP route rebinding remains outside `AskCompositionBuilder.capture()`.

## Validation

- Added focused registry-order, wrapper-count and runtime-startup wiring tests.
- Existing semantic home summary and semantic query route tests remain applicable.
