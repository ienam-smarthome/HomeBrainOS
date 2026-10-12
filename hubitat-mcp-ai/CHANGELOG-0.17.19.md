# HomeBrain 0.17.19 — Evidence-driven causal answer composition

- Adds a typed, evidence-scoped OFF answer plan before the final model synthesis round. It ranks observed boundaries, correlated events, verified direct commands and unresolved explanations rather than asking the model to infer their proof status from raw output.
- Separates source coverage from causal certainty: a command-off read can return older events without identifying the particular requested OFF. A missing focal command does not prove that no Hubitat command was issued.
- Provides timer-feasibility results inline with the planned app/automation analysis, distinguishing a newly started timer from an earlier pending timer, and current configuration from verified historical execution.
- Demotes button/controller timing alignment to association unless direct initiating mapping is proven; state reporters and triggered downstream listeners are not command producers.
- Keeps synthesis to one model round when localized claim repairs suffice and adds cross-device regression tests for the planning contract, checked-source claims, and orchestration.
- Read-only reasoning change: no Hubitat devices, apps, rules or settings are modified.
