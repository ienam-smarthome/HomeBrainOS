# HomeBrainOS v0.18.449 — Focal event evidence integrity

## Why

The first source-real read-only test on installed v0.18.448 had a cleaner answer
but failed causal fidelity. It asserted that an OFF transition originated
outside Hubitat although its only focal producer was a state-reporting bridge
and no upstream command path was established. It described a recorded
`inactive` motion observation as activity. A downstream monitor named in the
answer had been attached to a *different, older* event. Its Technical JSON
showed an unsuccessful synthesis repair and incomplete history coverage.

## General correction

- Reconstruct a missing question from the verified focal transition direction
  (ON or OFF), not a hard-coded ON assumption.
- When a source-timed focal boundary is available, take triggered[] app
  identities only from that exact device, switch state and instant. Never
  select an arbitrary historical listener for a generic causal statement.
- Reapply the existing source-based upstream-initiator guard during final
  read-only causal serialization, including clauses that say "triggered
  externally" followed by a separate "actor unknown" caveat. A caveat does
  not prove the preceding unsupported positive claim.
- Protect named focal sensors' recorded `inactive` state from being presented
  as an activity report when the observation is uniquely source-qualified.
- Expose `evidence_validation.causal_initiator_claim_corrected` when the final
  publication stage corrects an unsupported causal verdict.
- Fictional cross-event, ON/OFF, source-role, alternate-hypothesis and
  approval-boundary regression tests; no live data in public fixtures.

## Safety and evidence limits

No newly authorised read tool, source-specific room/app rule, paid model route,
MCP permission, device action, confirmation or investigation timeout change.
These proof guards do not discover a missing external history or establish an
upstream initiator. Genuine live improvement and regression safety remain
pending the required exact-head CI gate and subsequent installed-model retest.
