# Hubitat MCP AI 0.10.181

## Changed

- Consolidated named-rule status, climate extrema and execution-contract handling
  into one ordered `AnswerGuardRegistry`.
- Preserved terminal-route precedence followed by execution-contract annotation.
- Removed one redundant `application.ask` wrapper.

## Safety

- Read routing, evidence access, response annotation, deterministic writes and
  confirmations are unchanged.
- Runtime HTTP route rebinding remains outside `AskCompositionBuilder.capture()`.

## Validation

- Added focused ordering, wrapper-removal and runtime-wiring tests.
