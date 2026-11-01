# Q1 — source-bounded device telemetry response review (2026-11-01)

**Source:** full privately supplied HomeBrain natural answer, complete technical JSON, and UI screenshot. Raw household event histories, exact labels, IP addresses, device IDs and private driver source are **not** included in this repository.

**Registered case:** `device_mqtt_conflict` (legacy inventory); the question was supplied by the assistant verbatim, but the technical JSON does **not independently attest the literal actual user prompt** or deployed Git SHA. Therefore this is one real **source-bounded qualitative diagnostic**, **not** an eligible first-attempt frozen benchmark score.

## Observed run (model/user reports; not independently authenticated)

- Maintained add-on release: **0.18.331**; model **gemma4:31b**, provider **Ollama Cloud**, free allowance.
- Wall elapsed **43.533s**; agent phase **40.246s**, provider aggregate **36.016s**; **13 tool calls**, **10 model rounds**. Single observed investigation is just within preferred <45s target; no median, p95 or A/B performance can be inferred.
- All 13 returned tool receipts were labelled read-only. That classifies recorded receipts, not the absence of external side effects.
- `outcome=unresolved`, `questionResolved=false`, `rootCauseVerified=false`, `evidenceComplete=false` with `sourceChecksComplete=true`; source-class coverage is not physical or causal proof.
- A targeted device read retained `healthStatus=offline`, `mqttStatus=connected` and an old `lastSeen` plus a stored `dataAgeSeconds`. The two metadata age clocks differed by roughly **452.5 hours**. **Neither establishes a fresh packet from the endpoint**.
- A 24h bounded history returned **11 device-health state events**, primarily alternating `stale`/`unknown`, not source-verified physical telemetry or breaker/plug activity; no commands were returned in that bounded history.
- One full driver-source read was recorded but its code ID was **not verified as the installed driver**, and source-method behavior was not traced. No independently corroborated upstream MQTT broker/device observation.
- Host finaliser unconditionally overwrote model prose with a large `render_target_device_evidence_answer` report; the user-facing output also displayed internal source offsets, missing-discriminator checklist and empty command header. The question about distinct status semantics was answered only in general cautionary phrasing.

## Human assessment (not a quantitative score)

| Dimension | Review |
| --- | --- |
| Fact grounding | **Mostly supported for bounded state and source receipt metadata.** No independent live physical packet evidence. |
| Causal calibration | **Appropriate caution:** the system did not declare unverified source of an outage. |
| First-answer usefulness | **Partial.** It did not lead with the likely distinction between broker/client session and endpoint telemetry; implementation semantics were not independently verified. |
| Clarity | **Poor.** Extensive duplicated proof-limit paragraphs, internal source bookkeeping, and empty command heading obscured an otherwise simple status distinction. |
| Read-only safety | **No write receipts observed**; no device mutation requested; complete live safety cannot be independently established from recorded receipts. |

A **possible** explanation is that one attribute reports an MQTT driver/broker client session while device-health depends on separate endpoint messages. The retrieved source was not linked to the actual installed driver, so this packet **cannot prove** those exact status paths, whether a device is powered, or what stopped telemetry.

## General failure class and next milestone

**Problem:** a generic finalisation layer replaces even a valid model-led answer with a lengthy hardcoded telemetry report; then duplicates machine-readable technical details into the natural answer. This affects device-health questions generally, not a specific plug or room.

**Small reversible v0.18.332 change:** technical-only appendices remain in `investigation_coverage`, clock warning follows the diagnosis, empty command sections are omitted, and connection/health interpretation is framed as a provisional layer distinction. This **does not restore unconstrained model publication**, does not prove a source-backed driver mechanism, and is not a measured same-packet AI-quality gain.

**Next Q1/Q2:** independently authenticate actual first-attempt prompt and deployed build for this case or a future one; retain raw evidence privately, then compare unchanged source packets with blinded source review. Inspect model-output/publication handoff before attempting to remove any larger rewrite gate. Do not infer a score from regression-test or CI success.

**Programme denominator:** 31 case definitions, **0 independently authenticated frozen first-attempt live reviews**, **2 full source-bounded cross-domain diagnostics** (lighting and device telemetry). Earlier unrelated hallway sample also exists as an exploratory trace; never combine these as same-input A/B comparisons.
