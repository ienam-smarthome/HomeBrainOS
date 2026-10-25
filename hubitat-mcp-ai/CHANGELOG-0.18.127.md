# HomeBrainOS 0.18.127 — source-linked narrative and replay scorecards

## Added

- An opt-in **general-purpose evidence narrative** that connects two verified
  same-device observations in strict UTC order. The model may propose a
  `later_command` or `later_report` link; the host verifies record IDs,
  target equality, chronology and observation stages before rendering.
- The short interpretation explains the order of recorded commands and later
  reported states without claiming that a command physically executed,
  caused a state report or proved the root cause.
- Host-only automatic fallback from adjacent command records. Rejected
  links never replace source-backed evidence, and cross-device/fabricated/
  reversed-time link proposals are rejected.
- A no-extra-model-round `narrative_links` property on the opt-in atomic
  synthesis request. Existing structured synthesis remains the default.
- An **offline replay scorecard** for actual canonical command/state
  retention, invalid source IDs, validator flags and optionally measured
  read count/latency. V1 and third-party answers are explicitly unavailable
  until their actual captured text is supplied. Mere timestamp mentions
  are not scored as causal reasoning correctness.
- Regression coverage: the 24–25 October light incident, UK BST/GMT
  repeated-hour chronology, unrelated MQTT device history, malformed model
  output, unsafe links and no-flag execution.

## Safety and limitations

This release does not validate arbitrary model-generated causal prose, claim
physical execution from issued commands or grade third-party models.
The feature requires explicit V2 evaluation opt-in **and** the atomic claim
guard. It has no production routing hook, Hubitat writes, or automatic shadow
reads. Real V1/V2/Claude comparisons and controlled rollout follow after
captured evidence and scorecards are collected.
