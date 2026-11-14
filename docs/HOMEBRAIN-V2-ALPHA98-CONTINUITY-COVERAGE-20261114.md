# HomeBrainOS V2 alpha.98 — historical state-continuity evidence

**Date:** 14 November 2026. **Scope:** V2 Preview only; no real Hubitat call, private technical receipt or device-specific patch in this repository increment.

## Hypothesis and source-real evidence

A first-answer alpha.97 power investigation independently selected the separate Hub & Device Monitor saved history plus native Hubitat event history. The returned six-hour Monitor source contained 72 five-minute positions, 70 saved values, three carried-forward bins and two explicit null bins; the native request was filtered to `power` and returned only a narrow recent interval. The model accurately described sampled power history but could not establish uninterrupted device ON state or exclude off/on transitions during the unobserved interval. This is an **evidence completeness** issue, not proof the device switched off, failed or experienced an outage. Source-real acceptance here is a single unblinded exploratory case, not a baseline accuracy percentage. Original private device/source JSON is intentionally excluded.

The standing answer-quality charter says source completeness and useful causal uncertainty precede raw speed. It prohibits adding incident-specific gates or mandating extra read/model rounds to salvage isolated examples.

## General design change

1. In the existing measurement source-review instruction, distinguish a requested interval-wide device/state continuity conclusion from an observed series of power, temperature or setpoint samples. A current `on`/online snapshot is not the historical state. Even a full saved-bin grid cannot prove continuous physical observation, and held/cached, explicit null and absent bins have different meanings.
2. If a proportionate additional **read-only** history of relevant state transitions or connectivity would materially resolve the user's original continuity question, the model can independently choose it in its **existing** source-review round; there is no automatic new read, mandatory tool, fixed planner, retry or extra model pass. If the source remains missing or bounded, preserve the positive sampled measurements while explicitly leaving continuity unverified.
3. The existing tool-free final source-to-claim audit now receives already-returned safe scalar Monitor history metadata: requested/returned clock windows, metric/unit, number of expected, reported, held, saved, explicit-null and absent bins, plus source-verified continuity/completeness booleans. Source metadata is **navigation**, not independent physical proof. It must not be used to infer that no unobserved interruption occurred, especially when the native device-event read is attribute-filtered.
4. No change to MCP catalog, provider routing, cloud billing consent, monitoring configuration, polling, write permissions or V1.

## Regression and measurement

Fully fictional tests check precise Monitor coverage metadata retention, explicit `false` for verified continuous observation, sanitised missing-field handling, rejection of secret/raw sample replay, failed receipts never promoted to successful empty reads, and incomplete native filtered history remaining distinct from a current snapshot. Existing source-claim and approval regression suites remain active.

Expected qualitative effect: the model's response to an interval-wide state question should say *observed measurements are consistent with continuity but the available sources cannot establish it* unless event-specific state evidence genuinely supports a stronger claim. We should not presume a quantitative improvement until a **new, uncoached source-real first answer** is reviewed against its original receipts. Watch total model rounds, tokens, read count and elapsed time for regression; no new compulsory reads or rounds are introduced. The extra bounded audit metadata may modestly increase existing final-audit prompt tokens.

Rollback: revert alpha.98 to alpha.97 if prompt/token use or model behaviour regresses without improved evidence calibration; native write path and separate installed Monitor archive are unchanged.

## Next acceptance

Install V2 Preview alpha.98 only after hub stability checks. Use a new read-only cross-domain historical continuity question, not the already exposed PC benchmark, and capture full PRIVATE original receipts. Verify which sources actually returned state events vs stored measurement bins, per-source start/end and row caps, missing windows, whether a complementary read was justified, source provenance, no unsupported claims about uninterrupted activity and no writes. Retain the alpha.97 test as explanatory evidence but not a fresh blind pass.

Other open gates: alpha.96 deadline finalisation has not been observed in source-real runs; independent baseline and paired model quality remain unmeasured.
