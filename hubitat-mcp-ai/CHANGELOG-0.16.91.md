# Hubitat MCP AI 0.16.91

## Deterministic relative one-time schedules

- Extends `RuleAuthoringService` to handle relative one-time controls such as `block X after 1 minute`, `turn on X in 30 mins`, and `turn off X 2 hours later`.
- Relative requests are converted directly into a dated `Certain Time (and optional date)` trigger using the host clock. The requested delay is represented by the trigger time itself; HomeBrain does not add a second Rule Machine `Delay` action.
- The resulting one-time rule continues to use the existing self-pause follow-up so it cannot re-fire after its scheduled execution.
- Straightforward relative schedules remain outside the model-authored Rule Machine JSON path, eliminating the 0.16.90 live failure where a correct future trigger was rejected because proposal validation expected a separate one-minute action delay.
- Duration wording such as `turn on X for 30 minutes` is deliberately not treated as a delayed start and remains outside this bounded grammar.
- Immediate controls, absolute clock schedules, recurring schedules, and the 0.16.89 Internet-group access semantics remain unchanged.

## Regression coverage

- `after 1 minute` resolves to exactly `now + 1 minute` with second precision.
- `in 30 mins` and `2 hours later` cross the same deterministic path.
- Parsed relative schedules are non-recurring one-time intents.
- Duration requests are not silently reinterpreted as relative-delay schedules.
- Existing immediate-control and absolute-clock handoff regressions remain in place.