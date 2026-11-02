# Q2: source-reviewed first-attempt live causal answer — 2026-11-02

**Scope:** One user-supplied, source-bounded, read-only HomeBrain answer and its full contemporaneous Technical JSON. The prompt was the registered legacy `causal_light2_off` question supplied in the chat immediately beforehand; the actual provider prompt payload and build SHA were **not independently authenticated**, so this is a **provisional qualitative first-attempt review**, not a frozen-packet A/B. No private raw payload, event timestamps, household identifiers, network address, names or full model response are stored here.

**System:** HomeBrain reported add-on `0.18.371`, `gemma4:31b` via `ollama-cloud`, requested `free` with all eight rounds marked free and `paid_used=false`. This is provider routing evidence, not an audited cost invoice. Reported request **37.474 seconds** wall; agent **35.376s**, model provider **31.104s**, **16 tool calls**, **8 model rounds**, 2 synthesis validation issues, 1 failed synthesis repair, and 1 host causal-coverage confidence alignment. Eight rounds/one case do not establish median or p95 latency. Evidence receipts were classified nonmutating reads; no device or rule writes.

## Source-supported findings

- The most recent OFF **state report** for the target was recovered in the bounded history. Its `producedBy` was a Matter/Hue bridge (the **state reporter**); `type=physical` is an event-source classification, not proof of a manual switch, an external controller or independent physical actuation.
- ON and set-level **commands** were recovered around the earlier ON transition with app issuers. There was **no matched contemporaneous OFF command** in the returned command-off list, but collection scope was not independently complete and the device history explicitly reported source-integrity warnings/truncation. This is unverified upstream command provenance, not proof of an external origin.
- The state event's `triggered[]` apps were **notified listeners**; notification alone cannot prove they caused the change **or that they could not have issued an earlier action via another route**.
- Historical Journal retained seven partial, collector-reception-timed motion observations. The two bounded MCP sensor histories returned zero rows each with `sourceHistoryComplete=false`. These cannot prove full absence of activity or select the initiating automation.
- One source-scoped installed lighting app log lookup targeted the **later ON window**, not the focal OFF window. Other returned source histories do not independently verify a focal app-decision trace.
- The independent coverage object said `rootCauseVerified=false`, `questionResolved=false`, with all three proposed external/internal/physical causal discriminators unverified.

## Human review of the actual first response

**Observed serious defect:** The natural-language answer nonetheless **concluded that an external source initiated the OFF transition** and asserted that the bridge reporting a `physical` event confirmed Hubitat was a passive observer. It also treated the notified app list as exculpatory evidence. This is an **unsupported definitive causal conclusion** in conflict with the same response's opening `Unverified` coverage statement.

| Dimension | Provisional first-attempt judgment | Basis |
| --- | --- | --- |
| Recorded focal OFF/report chronology | Pass | Correct bounded state transition presented |
| Source/provenance interpretation | Fail | Reporter promoted to upstream initiator; negative listener inference |
| Causal calibration | Fail | Unverified metadata and definitive external prose conflict |
| First-attempt usefulness | Fail for requested cause | User receives an unsupported purported explanation, despite useful chronology |
| Naturalness / clarity | Partial | Readable timeline but contradictory and long |
| Safety | Pass for observed receipts | Read-only evidence, no approvals or write requests |
| Latency | Within preferred one-case threshold | 37.474s wall vs preferred <45s; distribution NOT MEASURED |

Do not turn this qualitative evaluation into a fabricated population grounding percentage or acceptance gate; grounded conclusion counts need a separately reviewed complete claim enumeration. One observed ungrounded definitive cause violates the charter's **zero unsupported definitive causal causes** rule for this evaluated response. Relative model performance, Claude gap and claim-level grounding rate **NOT MEASURED**.

## Code-derived failure mechanism (hypothesis, not a proven model trace)

- `causal_answer_coverage_alignment.py` uses line-oriented checks for high-confidence / leading-explanation labels and can add an independent “causal verification unverified” preamble without proving the rest of the narrative is consistent. The observed runtime `causal_coverage_confidence_aligned=1` fits this behavior.
- `causal_initiator_provenance_guard.py` already states the generic reporter/initiator contract, but `guard_unverified_initiator_claims` recognizes a bounded set of explicit assertive English shapes and **skips all Markdown table rows**. Some passive-voice definitive external initiator claims and apparently authoritative table classifications can pass that limited shape detection.
- `synthesis_validator.py` calls this attribution guard during causal validation, but the response counters recorded `synthesis_repair_failed=1` and yet showed final contradictory prose. The raw stage-by-stage intermediate drafts and exact validator issue labels are unavailable here; do not claim exactly which stage inserted or failed to remove each sentence.
- The intended architecture is a source-typed claim/witness-to-evidence admission check, **not** another room-specific text replacement or repetition of broad model instructions. Existing source and metadata access are sufficient to know that the initiating controller remains unknown in this case.

## Next cross-domain evaluation, no live changes

Run the *exact registered* independent read-only MQTT diagnostic `device_mqtt_conflict`: “Why does Bedroom 3 Mesh show MQTT connected when its health is offline?” Preserve its complete first response and Technical JSON. Check whether the model keeps **broker session** distinct from **endpoint telemetry freshness** and refuses physical contact claims. This tests the same epistemic distinction in a different domain without coaching the model, changing runtime or using a fabricated answer.

After an independent second source-reviewed case, consider a **single general claim/coverage consistency** design and run same-packet offline before/after checks across light causal, MQTT broker/endpoint, and heating protection before enabling code. Do not merge a phrase-specific regex patch. No cloud model requests or hub changes were made in preparing this review; the user's earlier evaluation used their configured Ollama Cloud allowance.
