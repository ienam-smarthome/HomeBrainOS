# Hubitat MCP AI 0.16.103

## Open temporal-history semantics

- Preserves a definite observed active transition even when the device-event stream has not been independently verified as complete.
- Reports an open active span separately from completed bounded intervals with `openActiveSeconds`, `openActiveDuration`, `activeSecondsSoFar`, and interval-count metadata.
- Keeps completed-pair totals distinct so an unverified open span is not promoted to an exact historical total.
- Distinguishes an in-window active transition from a verified active state that already existed when the requested window began.
- Prevents the final duration guard from rewriting a real open ON interval as “No bounded on interval”.
- Retains source-integrity caveats: absence of a later inactive event in the available rows does not prove uninterrupted physical state or complete event history.
- Adds regression coverage for open intervals, ongoing windows, predecessor-state clipping, final-answer correction, and evidence-field retention.