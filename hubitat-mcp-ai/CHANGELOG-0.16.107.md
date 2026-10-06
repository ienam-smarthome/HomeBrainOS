# Hubitat MCP AI 0.16.107

## Retained history-window coverage

- Fixes a semantic-window completeness bug exposed by the live Bathroom Light 1 history where HomeBrain requested 50 events but Hubitat's retained native history returned only 11.
- Stops treating a short returned event list as proof that the requested window start was reached; page coverage now requires an observed event timestamp at or before the semantic boundary.
- Prevents sourceCompleteToStart and sourcePageCompleteToStart from being marked true merely because the retained native list is shorter than the requested limit.
- When a duration answer is based on a retained page that does not reach the window start, the deterministic duration guard now states that earlier in-window transitions may be missing.
- Preserves the existing unverified-event-stream rule: paired durations are estimates from recorded rows, not exact physical-history totals or mathematical lower bounds.
- Adds regression coverage for the exact 11-row Bathroom Light rolling-history shape and for timestamp-proven boundary coverage.
