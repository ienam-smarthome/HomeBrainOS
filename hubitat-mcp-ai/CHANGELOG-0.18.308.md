# HomeBrainOS v0.18.308 — Stage 7.6 cross-scenario evidence and follow-up calibration

**Synthetic benchmark only.** Production publisher, device commands/reads, live Hubitat/HA integrations, general assistant routing and normal cloud account settings are unchanged. No extra model calls or automatic retries.

## Motivation
The actual v0.18.307 Gemma Cloud conflicting-command test correctly identified E1 OFF, E2 setLevel(40), and I1 OFF report, with source types 3/3, declared labels 2/3 and nine correct atomic values. Three issues remained: the host diagnostic listed command IDs in source catalog order (E2 then E1), the model's proposed telemetry follow-up overclaimed what device data can attribute, and old warnings made appropriately scoped uncertainty look like a factual citation error.

## Implementation
- Stage 7.5 source-only evidence ledger now displays comparable canonical HH:MM:SSZ **recorded command time-of-day** entries in ascending order. It keeps timestamp and clock-basis metadata and explicitly refuses to infer physical execution, cross-day absolute chronology or clock accuracy. Invalid/missing/mixed clocks preserve unranked source order. No synthesis change, language classifier or hidden chronology invention.
- Device state reports preserve separate device source-time, collector receipt-time and their clock-basis fields, even for seemingly device-origin timestamps. Source timestamps alone do **not** create independent telemetry. Driver-to-broker sessions are recorded separately and never prove device connectivity.
- The **fictional Stage 6 prompt only** now asks for causally discriminating follow-up evidence: a device packet may confirm an observed state but cannot identify an initiating app without a verifiable command-to-outcome relationship. It retains model-authored natural language; no hardcoded incident answer or routing keywords.
- Stage 7 packet includes an independent, not-reviewed human verdict on whether Gemma's proposed next evidence could actually prove what is suggested. Phone UI exposes this and exports the verdict with the rest of the optional human review.
- Legacy dashboard diagnostics clearly differentiate unsupported typed annotations (not a false-fact count) and missing exact-value atoms for an uncertainty claim from independently disproven factual content.

## Adversarial and compatibility coverage
- Mock-only Stage 6 runs for `clock_conflict`, `competing_commands`, and `stale_connectivity`; each uses exactly three source choices and one final answer, no new/cloud model inference and no real device calls.
- The expected E1/E2 recorded time-of-day display, missing/malformed timestamps, mixed clock bases, separate OFF source/receipt clocks, broker session versus independent telemetry, reviewer defaults, human export UI and production-module isolation all have regressions.
- Existing Stage 7.5 output schema and v1/v2/v3 model answer compatibility remain unchanged. Additive diagnostic fields do not provide semantic certification or publisher approval.

## On-phone acceptance
After installing **v0.18.308**, run **Stage 6 → Late bridge report versus earlier device time**, followed by **Offline plug despite connected MQTT driver**. Each independent run may use up to four requests on the currently configured Ollama Cloud account, requires explicit consent and reads no actual hub/device data. Review the model-authored explanation, the new command/source clock diagnostics and the follow-up evidence quality selector. The real-model outcomes of these two cases remain untested in this PR.

Rollback: revert the Stage 7.6 PR and restore v0.18.307.
