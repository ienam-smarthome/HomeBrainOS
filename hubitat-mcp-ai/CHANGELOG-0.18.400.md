# HomeBrainOS v0.18.400 — Q1 current-state comparison scope

## Real observed before (installed v0.18.399)

The registered read-only comparison of two named light states gave the
source-reported correct values (OFF, level 50; OFF, level 60), but
expanded into a 24-hour investigation of only one light. The model
made unnecessary automation/transition assertions and the host marked
historical scope incomplete even though the question requested **only
current states**. Single observed wall time **19.409 seconds**, six
Gemma free rounds, seven tool calls, provider 14.568 seconds.

## General correction

- Distinguish comparisons of present retained switch/level/brightness
  values from comparisons of history, events, changes, timing and causes.
- Do not activate historical-investigation skills and target history-
  scope retries solely because a user said 'compare' when the requested
  objective is a current-state snapshot.
- Keep the model as the natural-language answer author. Give general
  grounded guidance to answer current-state comparisons directly
  using independently read per-device attributes, without decorative
  history, app trigger speculation or claims of physical light output
  from stored dimmer levels.
- Historical/causal comparisons still retain target-scoped event reads,
  uncertainty calibration, receipt coverage and all write safety gates.

## Test, measurement and limits

Added synthetic regression cases for current vs. historical comparisons,
two-target evidence with one historical read, source-scope follow-ups,
unchanged ordinary controls and prompt safety boundaries.

Expected after installation: a concise two-device current state answer,
no unrequested history reads or false missing-target-history coverage,
and preferably under 15 seconds. **After real answer quality/latency:
NOT MEASURED.** The previous 19.409 s is one observed sample, not an
estimated p95. The API's first_attempt_verified=false does not certify
a first-attempt benchmark. No Claude model A/B was performed.

No Hubitat, router, Home Assistant, automation, driver or device state
was changed by this GitHub release.

Full source-review and rollback: see
`docs/ANSWER-QUALITY-Q1-SNAPSHOT-COMPARISON-20261104.md`.
