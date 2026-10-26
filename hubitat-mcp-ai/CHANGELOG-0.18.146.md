# HomeBrainOS v0.18.146 — Safe semantic-timeout evidence recovery

The v0.18.145 V2 test retrieved a complete 204-device Hubitat inventory in
22.785 seconds but stopped after a 25-second semantic AI planning timeout.
The user had named a real, independently verifiable device, so the hard
failure prevented any evidence reads.

- If the initial semantic planner times out, returns an invalid plan, or
  suffers a provider failure, attempt exact/whole-name host verification of
  the actual question against the live inventory.
- **Only one independently verified target** permits the fallback. It runs
  the already introduced manifest-verified, read-only context and history
  preflight, with no additional provider calls or fabricated causal synthesis.
- The output explicitly identifies the recovery as partial, reports
  `semantic_plan_<reason>`, and marks semantic intent interpretation
  unverified. Current snapshots cannot be presented as historical evidence.
- A broad inventory question, a question without a device name, or duplicated
  live device names continues returning `semantic_unavailable`, with no
  guessed targets. An explicit Advanced ID override retains its existing
  independently verified read-only path.
- The duration now measures inventory retrieval, intent planning and
  investigation together, so slow early stages aren't excluded from metrics.

Regression coverage exercises an unavailable AI provider (which must not
be called again), typed current-source evidence, redaction of hidden
credentials, unique-name recovery, broad-query failure and label collisions.

**Limitations:** This is a degraded safety fallback, not semantic-intent
equivalence or full causal-analysis parity. It does not enable extra tools,
make device changes, alter production V1, or infer a verified root cause.
