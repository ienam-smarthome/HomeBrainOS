# HomeBrainOS v2 — Experimental generic source ledger (not promoted)

**Prepared:** 9 November 2026  
**Status:** Prospective-candidate code and synthetic unit tests only. **Production v2 agent remains unchanged.** No new source-real or cloud-model test has run for this candidate.

## Purpose

The frozen six synthetic A/B results showed no improvement in causal calibration (both arms 7/12) or strict required-source retrieval (both arms 10/23). The later ten real-source answer receipts identified over-counting/under-counting returned inventory attributes, converting bounded logs into comprehensive diagnostic claims and confusing a related app with an exact target. Those **ten cases are now exposed** and may be used for diagnosis only, not as fresh acceptance evidence.

This next candidate changes **one general evidence-presentation mechanism** instead of adding another prompt instruction, incident phrase, retry sequence, fixed source checklist or deterministic answer rewrite:

- Production `Agent.present_native_result` returns exactly the preexisting `model_result_with_scope` event-history annotation. The production app imports and constructs `Agent`, **not** the experimental subclass.
- `SourceLedgerExperimentalAgent` extends only that presentation method. It preserves all original native MCP tool payloads, available tools, model-selected read strategy, upstream schema discovery, token permissions, confirmation gates, native deadline and original model answer.
- An additional `client_collection_source_ledger` contains **only observational metadata** for native returned `devices`, `apps` or `entries` collections. For every collection it reports the number of actual returned rows, any upstream-reported match/total counts, the supported request filters, whether matching rows exceed the number returned, and **explicitly does not assert completeness of the source**.
- For a device collection, it generically counts fields *actually present* in each returned `currentStates` mapping, e.g. `X` rows with field `attr`, `Y` without. Field names are drawn from the source, not hard-coded to battery/temperature or particular devices. It does not decide that a missing field means an absent capability, no older readings or broken sensor.
- This ledger **does not grant authority to the metadata**: the original native receipt remains the source of truth, and counts do not determine causal validity.
- The candidate does not inspect a result if the server reported `isError` or if it is not a single unambiguous JSON object; it does not combine unrelated messages into invented results. The metadata does not include device labels, event text, room IDs, tool arguments, source attribute values, tokens or credential fields.
- There is **no automatic follow-up** based on the annotation and no extra cloud inference. The model alone decides what more it needs and how to explain the evidence.

## Evaluation protocol

**No effect sizes are claimed by CI.** The structural tests use invented sources and scripted responses, without any Ollama, Hubitat, Home Assistant or internet calls. They establish only that source payloads are preserved, counts computed correctly, baseline remains unchanged, and server calls are not added by the presentation variant.

**Prospective acceptance (NOT YET RUN):**

1. Confirm the target MCP client's server-side **Read ON / Write OFF** scope through the hub's per-client token management; global `writeEnabled: true` is insufficient to establish token write scope.
2. Freeze a **new set** of permission-verified, real-source questions and evidence receipts that neither arm nor reviewer has seen, separate from `hold-01..06` and `sr-01..10`. Preflight device/app capability and exact name matching so flawed question subjects do not get misclassified as reasoning failures.
3. Use **the same model and same source/tool conditions** for baseline and candidate. Apply exactly one intervention: candidate uses `SourceLedgerExperimentalAgent.present_native_result`, baseline uses unchanged `Agent`. Randomise and blind the arm labels, save original source/response metadata privately and no raw PII in GitHub.
4. Independently grade **first-answer factual grounding, source completeness, causal calibration, command/outcome honesty, usefulness, server/client contract errors and latency**, including whether the candidate materially improves the primary cause/coverage problem. Do not count source-ledger presence itself as a success.
5. Promote only after independently verified real first answers improve causality/coverage without overclaiming, excessive latency or permission regression. Otherwise leave the candidate unpromoted and document the negative result.

**No live MCP tools, devices, rules, HA settings or cloud models were called by creating this code.** No repository version bump or installation requirement until the candidate is approved for use. Existing source-real capture and private-review tools remain independent.
