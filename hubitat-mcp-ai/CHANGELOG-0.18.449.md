# HomeBrainOS v0.18.449 — Source-bound focal causal answer integrity

## Live evidence motivating this release

A v0.18.448 read-only lighting investigation retrieved a source-reported OFF
transition and independently recorded command history. Its final answer
incorrectly asserted an external cause and a definite lack of a Hubitat
command, despite incomplete upstream evidence. It also described an inactive
motion event as "activity" and carried a downstream app listener from a
different historical switch event into the focal-event conclusion.

This was a **failed real-source answer-quality acceptance**, even though the
final repeated-paragraph safeguard worked. The 6-round model completion
reported one failed synthesis repair and unresolved causal provenance; neither
a bridge state report nor an absence in bounded command rows establishes
external control. The precise upstream cause remains unverified.

## General correction

- Recover the documented OFF/ON direction from the verified host causal
  correlation receipt; do not silently construct an ON investigation.
- Restrict downstream-listener attribution to the actual focal state event.
  Do not select an arbitrary older event's listener as a substitute.
  Corrections to previously inserted listener assertions are event-scoped.
- Reapply the existing model-agnostic unverified-initiator checks at the
  final read-only API publication boundary, including after failed model
  synthesis repair. A firm external-origin assertion is still unsupported
  when the same sentence adds that its actor is unknown.
- Distinguish a bounded search with no focal command receipt from proof
  that no Hubitat or external command occurred. Source claims remain
  source/clock/target scoped.
- Prompt policy requires exact observed sensor attribute/value and focal
  timestamp for every event-related claim. A motion=inactive event must
  not be described as active motion.
- Technical JSON emits audit flags only for corrections actually made:
  unverified_causal_origin_corrected, focal_listener_scope_corrected.
- Synthetic cross-event, negative-command, write/confirmation exemption
  and API end-to-end regression tests. No incident-specific actor IDs or
  room-specific production rules.

## Release gate

All four mandatory workflows passed on exact tested PR head
`dcf50f86381f959c9cde8eda5287f1da27d08a34`; PR #1503
squash-merged to main as `5ff4c1127b54a85afc7b5c53386dd4e8e97d0980`.
The first CI run failed five existing regressions; the revised code passed
the complete second run. This code-level protection is not proof of improved first-pass model
reasoning, complete historical source retention or discovered causality.
Post-installation verify an unfamiliar read-only incident with full
Technical JSON. No live device, Hubitat or HA state was changed by this PR;
model provider, billing policy, MCP read permissions and adaptive watchdogs
are unchanged.
