# v0.18.340 — restore source-attested model-plan handoff for "why" telemetry questions

## Production finding (user's read-only v0.18.339 run)
The user supplied a complete 48-hour Bedroom 3 Mesh trace with **12 returned Hubitat driver health events, no commands**, `healthStatus=offline`, `mqttStatus=connected`, and a `lastSeen` vs `dataAgeSeconds` inconsistency (**501.2 vs 45.1 hours**). Physical state and root cause remain unverified. **11 Gemma Cloud rounds, 9 model tool calls, 45.291s provider, 51.152s overall**; no 74-second whole-hub inventory (unlike v0.18.338), though a one-second loosely scoped Tasmota peer search still appeared. The first no-tools draft was captured and remained unchanged across coordinator and author, but `authorAnswerUnchangedAtSharedBoundary=false`, `answerPublicationDecision.mode=concise`, and `replacementPerformed=true`; the model-directed claim plan was never published.

## Verified architecture defect
The new source-proof plan was only offered when `contract.domain == device_telemetry and not causal`. The broad historical/causal grammar considers a user's ordinary `Why does MQTT show connected while device health is offline?` a causal question, so it suppressed the model-plan prompt **in the exact documented target case**. Generic post-synthesis prose calibration could then alter a model response before the existing strict claim-plan publication gate could inspect it.

## Fix
- Use the **typed objective domain** for the prompt; the proof adapter already refuses command-rich, truncated or unsupported device histories. "Why" alone cannot suppress a bounded telemetry source-proof plan. No additional provider/model or MCP call is introduced.
- Add `eligible_model_claim_handoff`: require independently normalized, verified single-target read evidence and an exact unchanged `raw_first == coordinator_result == final_author_answer == current_message` machine plan before preserving that candidate across **prose-only** causal guard transformations. Do not bypass the guard for ordinary narrative answers, history timelines, cross-source input/off correlations, writes or source-unverified plans.
- Retain a **second independent typed source check** in shared publication: same claim-ID grammar, strict root-cause uncertainty and mandatory clock conflict, no model-written prose, no implicit physical causality, still fail closed if an actual post-model guard changes the content. Public privacy-safe metadata/metrics remain unchanged.
- Add tests ensuring a *why-worded* telemetry objective reaches optional claim-plan selection on the **existing no-tools final call**, and source-verified model handoff rejects drift, altered drafts and the wrong domain. Full safety suite must pass before merge.

## Scope / limits
This is a narrow, general architecture correction, **not** a room-specific keyword patch, raw free-form prose entitlement, or verified end-to-end speed improvement. Model rounds may remain high because incident/depth follow-ups are independently configured. Source-authorized plans still publish only host-rendered, independently verified claim text; causal confidence remains unresolved absent independent driver/broker proof. Lighting and heating remain under their prior source gates. Quality scorecard still **NOT MEASURED**.

Rollback: revert the telemetry prompt eligibility and the one narrow source-certified machine-handoff preservation branch. Model/prose claim validation remains unchanged.
