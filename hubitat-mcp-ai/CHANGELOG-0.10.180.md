# Hubitat MCP AI 0.10.180

## Changed

- Consolidated the exact thermostat live-state terminal route, home-summary
  consistency guard and thermostat summary guard into one ordered
  `AnswerGuardRegistry`.
- Preserved thermostat-first routing followed by home-summary consistency and
  thermostat-summary post-processing.
- Removed one redundant `application.ask` wrapper.

## Safety

- Thermostat evidence reads, summary corrections, semantic-home exemptions,
  deterministic writes and confirmations are unchanged.
- Runtime HTTP route rebinding remains outside `AskCompositionBuilder.capture()`.

## Validation

- Added focused ordering, wrapper-removal and neighbouring-layer wiring tests.
- Existing thermostat and home-summary consistency tests remain applicable.
