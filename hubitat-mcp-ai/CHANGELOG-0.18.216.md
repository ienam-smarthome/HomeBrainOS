# Hubitat MCP AI v0.18.216 — Single-pass model explanation and latency-aware fallback

## Live v0.18.215 result (29 October 2026)

An unchanged broad general health question took **72.148 seconds**, versus 33.947 seconds in v0.18.214. Native V2 completed **9/9 successful source READs** with no malformed requests, retaining 29 Bedroom 3 Mesh WARNs and source-reported offline/stale health, 10 Matter Zemismart bridge WARNs with disagreeing healthStatus=online/networkStatus=offline, and 39 SenseCap app WARNs. The separate *model-only explanation* was not accepted: `verified_narrative_result=model_unavailable`, `verified_narrative_ms=6001`. HomeBrain correctly preserved the prior static source-connected brief. The nine Hubitat READs totalled ~8.45 seconds of 72.15 seconds, leaving ~63.70 seconds outside these tool calls (including 6 seconds on the failed narrative). No evidence supports a device root-cause conclusion.

## General architectural improvement

- **Reuse in-loop model-authored findings.** The Native V2 planning model may now supply optional `findings` in the JSON content of an existing final response or tool-calling response. Its `claims` list retains its independent strict claim-validation shape when both fields are present. No extra model call is needed if the independent source-attested narrative verifier accepts these findings after the READ loop.
- **Model-latency-aware optional pass.** If no verified in-loop draft exists, a separate tools-free narrative attempt is allowed only if real planning-model latency averaged **at most 3 seconds per call** and at least 8 seconds remain under the execution deadline. If the current model is slow, the host skips the doomed extra 6-second call and retains its previously source-verified answer. This depends on measured latency, not any question keywords or device-specific rules.
- **Independent host facts and safety remain unchanged.** No model prose is published unless the same strict source ID, warning-count, severity, status, lexical and nonwrite validation passes. The source-connected fallback and full technical evidence report remain available, including when the model does not produce a draft.
- **Make slowness visible.** Add planning-model time, number of planning-model calls, mean model latency, draft reuse and narrative-skip reason to diagnostics. A reduced model-call count, better wording acceptance and actual V1/V2 result quality can now be assessed separately from MCP read times.
- Regression tests prove final and tool-call draft reuse with **zero additional inference requests**, claim-ID validation with combined content, slow-provider fallback policy, normal fast-provider eligibility and rejection of unsupported cause/unsafe modification proposals.

## Limits and next steps

This does not solve all general reasoning gaps. In current V2 the model can still exhaust its planning budget without offering a narrative, so the host must retain its safe factual answer. Without live model-supported in-loop findings, the latency-aware policy may improve speed **without increasing model-authored answer acceptance**; these two results must be measured independently. A broader objective-driven answer contract and multi-query evaluation remain important. All V2 operations are strictly READ-only, with production Main Ask and device automations unchanged.
