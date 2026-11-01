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

## v0.18.332 read-only follow-up — later live evidence, not a frozen same-packet pair

The user supplied the full natural answer and diagnostic JSON for an actual v0.18.332 Free Ollama Cloud Gemma run. This document deliberately does **not** reproduce household-private source records, target names, identifiers or raw responses.

- **Observed performance:** 55.132 seconds wall, 53.632 seconds agent phase, 49.049 seconds provider aggregate, **13 tool calls and 11 model rounds**. Compared with the v0.18.331 live sample above: **+11.599 seconds wall**, one extra model round, unchanged tool-call count. These are successive live investigations, **not identical source packets**; do not attribute the elapsed difference to the code revision or compute a regression p95 from two runs.
- **Supported domain interpretation:** the answer now leads with the distinction between reported driver/broker connectivity and physical endpoint health, explicitly as an unverified implementation hypothesis; current offline status and stale metadata remain source-scoped. Neither the upstream physical cause nor current packet reception was established.
- **Observed content improvement:** raw source offsets and long missing-discriminator ledger are absent from natural prose; the empty command-source heading is absent. However, the user-facing answer **repeats the same timestamp discrepancy twice**, once by the typed-history renderer and once by the shared completion layer. Large source bookkeeping sections remain.
- **Remaining investigation inefficiency:** after target history and logs, the model performed a 207-record whole-hub context read and progressed through an unsuccessful app-source lookup for a driver-code identifier. The diagnostics show one evidence checkpoint retry, one incident-depth retry, one progress retry, and finalisation; source lookup failure does not prove a nonexistent tool or imply source-method analysis. The model spent most time in provider rounds. These are observed leads for **cross-domain** tool-selection/stop analysis, not evidence that cutting required reads improves quality.
- **Coverage:** `outcome=unresolved`, `rootCauseVerified=false`, `questionResolved=false`, `evidenceComplete=false`, with self-reported source class checks complete and historical integrity unverified. The full input prompt and deployed Git commit are not included in this JSON, so the formal independent frozen-run grade remains **NOT MEASURED**.

**Scoped next improvement:** remove the **structural duplicated clock paragraph** by using the same typed clock check in a single rendering location; keep the complete structured `telemetryClockConsistency` record, existing direct-renderer fallback and unresolved causal verdict unchanged. Test unrelated synthetic devices and missing/matching clock cases. This is a presentation/grounding invariant, **not** a measured latency, first-attempt, or model-reasoning improvement.

Next compare genuinely identical evidence packets and inspect checkpoint retry policy before risking changes to the model's read-time budget. No household source logs are committed.
