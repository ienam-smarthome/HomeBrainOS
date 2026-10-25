# HomeBrainOS 0.18.122 — Investigation V2 evidence foundation

## Scope

First implementation of the approved Investigation V2 RFC, without enabling
the new investigation runtime, replacing V1 or changing any Hubitat automation.

- Adds an isolated, read-only `investigation_v2` package containing a typed
  case file, timestamped evidence records and source-coverage contracts.
- Separates command dispatch, reported device state and app log statements.
  A command to switch OFF is not proof of a physical OFF transition.
- Retains producer IDs only when the source explicitly identifies them; triggered
  listeners are not promoted to command issuers.
- Preserves original clock offsets while ordering events by absolute UTC time.
- Distinguishes historical pagination reach, retention, integrity, truncation and
  source completeness. Neither a page boundary nor requested history duration
  certifies completeness.
- Adds a sanitized replay fixture of the 24–25 October incident and 15 focused
  regression tests, plus initial unrelated MQTT/temperature coverage.
- Leaves the existing planner, V1 final-answer validators, write permissions and
  confirmation/reconciliation paths unchanged.

## Deployment and status

The new package is inert until future read-only V2 shadow integration.
This release is **not** a claimed improvement to live answer reasoning yet.
CI release gates must pass before merge.
