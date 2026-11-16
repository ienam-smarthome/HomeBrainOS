# HomeBrainOS V2 alpha.129 — scoped causal-publication source integrity

**Status:** merged [PR #1694](https://github.com/ienam-smarthome/HomeBrainOS/pull/1694) at `63fd6f81ee2744521ab3aaf0566b7330cdf9cd0c` after all four exact-head CI workflows passed. V2 Preview only.
No V1, scheduler, smart-home device, model-provider, native command, approval or
authorisation changes. The installed first-answer score is NOT established by CI.

## Why this follow-up is needed

Alpha.128 introduced a conservative fail-closed causal-publication floor and
a smaller model inventory. A review of that code identified two GENERAL
coverage gaps (no private first-answer transcripts are committed):

1. A definite claim such as "The output turned on today because the
   controller ..." bypassed the narrow immediate "turned on because" regex.
2. Any app's successful nonempty log could satisfy the original
   `_has_event_time_execution_source` category check, even if the app had
   no relationship to an observed device event. A `triggered[]` listener
   also must never be mistaken for the initiating controller.

## Implementation

- Generalize the causal assertion detector to allow a short intervening
  phrase between a historical state/action verb and "because".
- For the *necessary* log-source-category check, collect validated numeric
  app IDs only from original successful device-event `producedBy.appId`
  values; do not infer issuer/decision from this identity, and never use
  `triggered[]` subscribers. Only an app-scoped nonempty execution-log
  receipt for an observed producer can satisfy the category floor.
- If no relevant producer identity or execution log was returned, the
  publication path continues to withhold unsupported definite controller
  cause claims, preserving original read-only observed facts through
  the existing source-only PARTIAL result.
- Add fictional regression cases for intervening words, unrelated logs,
  listener-only IDs, and a genuinely matching app-log source type.
- Preserve original MCP receipts unmodified, native tool selection entirely
  model-led, and the read-only versus write boundary exactly as before.

## Deliberate limits and live acceptance

A nonempty related app log is necessary evidence **type**, not proof that its
contents verify a particular event, input, rule execution, or causal claim.
This change does not invent an app/event linkage, time correlation, or a
physical state. It cannot by itself deliver reliable event-specific reasoning.
The existing final model audit and user review remain necessary.

After full exact-head CI passes, install alpha.129 in V2 Preview and run new
uncoached read-only WHY investigations in different device domains. Assess
original output history, timing, command/report/decision distinction, model
normal completion, any publication fallback, source counts, rounds, tokens and
latency. Do not claim 8/8 or faster response until verified live.
