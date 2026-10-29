# HomeBrain V2 — general-purpose reasoning architecture and acceptance plan

Updated: 29 October 2026. The opt-in Native MCP V2 remains READ-only; Main Ask has a separate confirmation/write lane.

## Intended outcome

HomeBrain should answer **any supported Hubitat information question**: live state, devices, apps, rules, history, automation causes, system diagnostics, logs, energy, grouped questions and comparisons. A new device, verb, app or incident must not require new keyword routing. The model determines what the user needs to know; host code checks source identities, permissions, evidence receipts and assertion limits. The system must also know when the evidence is incomplete.

## Separation of responsibilities

1. **Admission and authorization:** Reject only independently requested Hubitat write actions in the V2 panel. Distinguish positive imperatives from prohibitions and historical descriptions. This is a negative-only boundary, never a selector for a specific investigation or tool. Every MCP read is separately checked against a live manifest, effect classification, required fields and verified source IDs; V2 never gains Hubitat write access from classification.
2. **Task interpretation:** Model identifies objective, entities, time range, requested specificity, ambiguities and initial hypotheses. These are proposed task-scoping decisions, not device identity proof or permission. Avoid a device-focused incident workflow for a whole-hub summary or energy comparison.
3. **Model-selected read tools:** Live read-only tool manifest, operation contracts and source-attested identifiers. Prefer small independently discriminating reads and stop when additional reads would repeat evidence.
4. **One evidence case:** Normalize source observations with original timestamp offsets, exact target/issuer IDs, command versus state versus config versus execution provenance, returned window, truncation, failures and missing source classes. Capture evidence with no template tied to one room, device or automation.
5. **Reasoning:** Model compares plausible explanations against verified observations and counterevidence. Do not conclude physical state from a command or time proximity from causation. Report probable hypotheses **only with a transparent evidence basis and uncertainty**.
6. **Answering and verification:** Lead with a direct, concise answer. Verify the material factual/causal claims against receipts; retain supported evidence and model reasoning rather than falling back to opaque generic caveats or unsupported confidence. Keep source/uncertainty detail in collapsible technical diagnostics where practical.
7. **Evaluation:** Replay *diverse* prompts and evidence fixtures, including straightforward status questions, history, app/rule context, system-wide problems, cross-device comparisons, energy and ambiguous cases. Evaluate whether the result answered the requested question, retrieved relevant evidence, preserved source truth, used correct permissions and avoided unnecessary reads. Timing alone is not reasoning quality. Use challenging independent external answers only as reference, not as authority.

## v0.18.211 implemented in this stage

- Shared read-only clause logic now understands negative action objects (e.g., "change nothing", "create no rules") and distinguishes text reports/analysis from hub state changes. A later independently **affirmative** write remains a refusal in V2 and is still subject to production write permissions/confirmations.
- V2 admission no longer invokes the production immediate-control classifier for every general question. It uses a narrowly scoped negative-only gate; the MCP READ permission boundary remains independent and unchanged.
- V2 page and native model objective describe general Hubitat questions, not just the previous device-focused incident sample.
- 0.18.211 regression matrix tests read and control prompts across domains plus the exact failed 29 October browser request end-to-end, with no actual Hubitat or model writes.

## Next architectural stages (not implemented by this release)

- **Objective-preserving read planner:** track what is necessary to answer an open-ended question across reads, without per-question phrase routing or preselected diagnostic recipes.
- **Universal evidence claim and synthesis contract:** retire special-topic answer rewrites after equivalent generic source receipt validation is available; allow useful model-authored natural language with bounded independently verifiable assertions, not model-as-authority.
- **Coverage-aware stopping:** avoid repeated reads and useless final model turns while retaining room for independent discriminators, using recorded marginal information gain across time windows and source classes.
- **Diverse end-to-end replay scorecard:** compare directness, accuracy, faithfulness to returned evidence, causal reasoning, speed and task fulfilment across dozens of unrelated questions. Deploy only after real Hubitat live-read acceptance.

This document is a development decision and roadmap, not proof of model parity with Claude or completion of the pending general reasoning stages.
