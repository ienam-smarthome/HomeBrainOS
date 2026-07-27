# Hubitat MCP AI 0.10.179

## Changed

- Consolidated named Rule Machine status reads and climate extrema reads into one
  ordered `AnswerGuardRegistry`.
- Preserved named-rule-first precedence and the existing position between the
  thermostat registry and execution-contract guard.
- Removed one redundant `application.ask` wrapper.

## Safety

- Route implementations, exact matching, climate filtering, evidence reads,
  deterministic writes and confirmations are unchanged.
- Runtime HTTP route rebinding remains outside `AskCompositionBuilder.capture()`.

## Validation

- Added focused ordering, wrapper-removal and neighbouring-layer wiring tests.
- Existing named-rule and climate-extrema route tests remain applicable.
