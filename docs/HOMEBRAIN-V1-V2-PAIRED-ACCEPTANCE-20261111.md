# V1 versus V2 — paired source-real first-answer acceptance pack

**Created:** 11 November 2026
**Status:** Evaluation-only. Does not install, update or control Hubitat or Home Assistant.
**Installed baseline shown in screenshots:** V1 `0.18.459`; V2 `2.0.0-alpha.51`. Recheck actual installed UI/server versions for each run. The V2 screenshot shows a populated, reconciled overview, but does not independently verify each device state or show V1/V2 answer parity.

This document executes **Gate B** from [V1/V2 capability gap and stages](HOMEBRAIN-V1-V2-CAPABILITY-GAP-PLAN-20261111.md). It does not port V1's scheduled audit or patch V2's causal model. The already-exposed PC/power/TV/monitor examples are positive controls, **not new held-out cases**. An experiment screen or automatic polling is not being restored to V2.

## Reproducible read-only protocol

1. Verify the **installed** V1 and V2 versions, server readiness, model/provider labels, and source connections. Do not assume GitHub's packaged version equals the installed runtime. Prefer matching model/provider for inference, and mark a mismatch if it is not feasible.
2. Select fresh target devices/rules *locally*, not in this public document. The benchmark questions below are **templates**; replace placeholders with private, unexposed targets and keep the same completed wording for both systems. Do not create or modify a rule or device to set up a test.
3. Use **new conversations** with both assistants; ask the **exact same question** once on each, without follow-up hints. Alternate which system goes first. For live state and current system health, capture within five minutes if feasible; live differences can still occur.
4. For historical questions, use **one absolute start/end with explicit timezone** in both arms. Avoid relying on relative "yesterday"/"last 12 hours" at slightly different moments. Note returned source boundaries, the source's own reporting window, missing bins and sampling provenance separately.
5. Keep the **original first answer**, raw tool/Technical JSON if available, elapsed time, errors and subsequent user corrections in a PRIVATE local folder. V1 and V2 may have different receipt/export contracts; absence of a comparable export is a **source-completeness limitation**, not proof that the system did no read. Do not paste private tokens or device identifiers into a public repository.
6. Independently compare each consequential claim to successful original receipts, not summaries of an answer. Distinguish a bridge state reporter from command issuer, app triggered listener, command acceptance and confirmed actual state. A successful/empty bounded read is not proof the complete native history is empty.
7. Manually record 0/1/2 per applicable criterion using the definitions below. Only causal calibration may be N/A when the task has no causal attribution. Record all missing discriminating sources, unknowns, tool errors and unexpected mutations separately. **Do not score unexecuted preflight as a failed answer.**
8. Use the offline local ledger tool if desired; it never contacts Hubitat, Home Assistant, the LLM, GitHub or any website. It records SHA-256 for each raw file without reading its content into the report; scores are supplied by the human reviewer.

## Twelve held-out read-only case families

Choose actual targets and absolute windows locally. For each case **do not change anything** and ask both V1 and V2 in fresh chats.

| Pair | Domain | Exact question template | What source evidence must discriminate |
|---|---|---|---|
| 01 | system_health | "Check whether the hub or devices need attention right now. Separate confirmed critical alerts, explicit offline states, low battery and unknown/unchecked sources. Do not change anything." | Scope of inventory, what was actually read, evidence for "offline", report freshness, whether logs/automation health were checked |
| 02 | system_health | "Review hub memory, five-minute load, recent reboots and critical hub warnings during [absolute interval]. Distinguish logged causes from unknowns. Do not change anything." | Native reboot markers vs firmware update, recorder retention/gaps, sample times, five-minute load vs CPU utilisation |
| 03 | current_state | "Which currently reported battery sensors have battery below 20%, and what devices did not report a valid battery percentage? Do not change anything." | Battery threshold, reporting denominator, excluded unknown attributes, not all unreported equal healthy |
| 04 | current_state | "Compare the current switch and level values of [device A] and [device B], including when those values were reported. Do not change anything." | Target ID/label, exact attribute values, timestamp freshness, cached level vs physical switch state |
| 05 | causal_transition | "Why did [unexposed device C] most recently turn OFF? Separate the state reporter, command issuer, rule decision and any unknown source. Do not change anything." | Correct most recent OFF time, history window, native command stream, producedBy vs initiatedBy, rule/log discriminators |
| 06 | causal_transition | "Investigate whether [unexposed device D]'s last change was caused by an automation or another controller. State only verified evidence and remaining alternatives. Do not change anything." | Multiple plausible initiators, triggered[] listeners, native logs/app history, attribution uncertainty |
| 07 | rule_machine | "Inspect native Rule Machine [existing rule E]. Identify its verified parent/type, paused state, triggers and actions. Do not edit anything." | Native parent identity, app type/namespace, source pages and configured vs effective state |
| 08 | rule_machine | "Read-only: determine whether [existing dated rule F] has a verifiable native dated trigger and evidence of actual execution, not merely a saved configuration. Do not change anything." | Dated trigger contract, persisted fields, rule app events/logs, configuration is not proven execution |
| 09 | historical_measurement | "Show [monitored power device G]'s saved watts between [start] and [end]. Give report-containing extrema, held values and unknown intervals. Do not change anything." | Source monitor/native distinction, same interval, watts not kWh, saved-bin vs real peak, null/held |
| 10 | comparison | "Compare power for [two previously untested monitored devices H and I] between [start] and [end], with extrema and longest missing runs. Do not change anything." | Common absolute window, per-device source, missing vs measured zero, reporting provenance |
| 11 | threshold_timing | "When did [unexposed humidity sensor J] last have a saved reading above [threshold], and when was it first later observed below [threshold]? State any unobserved crossing time. Do not change anything." | Source samples by exact attribute, first observed times, no interpolation of exact crossing between discrete reports |
| 12 | historical_measurement | "Check whether [monitored device K] has saved history for [precisely chosen sparse period]. Say which sources and windows were actually queried, and distinguish no returned sample from no stored sample. Do not change anything." | Negative control for empty but bounded native history, monitor availability, archive coverage |

**Target-selection rule:** New devices/rules or windows should not replicate those already used in recent developer-facing evaluation. If no suitable dated native rule exists, use an existing native rule without a dated trigger and score the accurate "not established" answer; never create a new rule merely for the benchmark.

## Manual scoring rubric

Score each answer separately using the **original successful receipts**, not how confident it sounds.

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Factual grounding | Unsupported or contradicted material facts | Key correct facts but material overclaim/omission | All material claims supported with correct attribution/units/times |
| Source completeness | Obvious discriminating source omitted or wrong scope | Partial source search or coverage qualified | Relevant accessible sources checked, or missing access explicitly qualified |
| Causal calibration | Unsupported definite initiator or causal leap | Acknowledges some uncertainty but unjustified likelihood remains | Distinguishes observation, command and causal decision; unknowns correctly bounded |
| Usefulness | Doesn't answer the asked question | Partially answers or misses essential gap/timing | Direct, task-complete, actionable read-only explanation |

Only **causal calibration** may be N/A where inapplicable; totals are out of 6 for ordinary noncausal questions or 8 when causal calibration applies. **N/A is not zero.** No scores may be assigned to an execution blocked before any model answer. Do not use safety as an implicit score: record unexpected writes/approval issues independently and treat them as serious release blockers.

## Private file layout and offline report

Place this layout on **your own Windows machine/private folder**, outside the public repository:

```
private-v1-v2/
  paired_manifest.json
  pair-01-v1.json
  pair-01-v2.json
  pair-02-v1.json
  pair-02-v2.json
  ...
```

Use `hubitat-mcp-ai-v2/evaluation/v1_v2_pairs.py` against the private manifest:

```powershell
python hubitat-mcp-ai-v2/evaluation/v1_v2_pairs.py private-v1-v2/paired_manifest.json --output private-v1-v2/paired_summary.md
```

The example below is **fictional** and illustrative. Actual captures must exist before running the script; the output never embeds raw receipts, answer text, questions, private device labels or file paths.

```json
{
  "schema": "homebrain-v1-v2-first-answer-pairs.v1",
  "cases": [
    {
      "id": "pair-01",
      "domain": "system_health",
      "question": "Read-only system-health question copied verbatim to both apps",
      "read_only": true,
      "arms": {
        "v1": {
          "installed_version": "0.18.459",
          "model": "explicitly verified model",
          "provider": "explicitly verified provider",
          "captured_at_utc": "2026-11-11T12:00:00Z",
          "first_answer_capture": "pair-01-v1.json",
          "elapsed_ms": 12000,
          "scores": {
            "factual_grounding": 1,
            "source_completeness": 1,
            "causal_calibration": null,
            "usefulness": 2
          },
          "human_review": {
            "supported_facts": ["Supported fact checked in private receipt"],
            "unsupported_definite_causes": [],
            "unknowns": ["Question-specific unverified evidence"],
            "tool_errors": [],
            "missing_sources": []
          },
          "unexpected_mutations": [],
          "tool_attempt_errors": []
        }
      }
    }
  ]
}
```

Add the **V2 arm** only after its untouched first answer has been captured and reviewed. The tool supports partial pairs, marks them *unpaired* and does not mis-score missing arms as zero. Once both are present, it reports manual totals, exact SHA-256 capture hashes, provider/model comparability and if current-state capture times are more than five minutes apart. It is **not an autonomous causal judge**.

## Review and go/no-go

- The most important criteria are unsupported definite causes, missing discriminating sources, incorrect absolute windows, and any unapproved action. **Test count and CI pass are not proof of source-real success.**
- At least twelve *new* source-real first answers across at least six domains are proposed. Do not use this as automatic statistical proof. Evaluate outliers and hidden-source limitations before V2 feature changes.
- For each repeated failure, identify a **general capability gap** in retrieval, source contract, app authorisation, model selection or explanation. Develop a reusable fix, not a controller- or device-specific answer patch.
- After evaluating system health and automation/Rule Machine questions, decide whether to add a limited on-demand system check, typed native Rule Machine read guide or provider fallback. Keep V1 stable and do not enable new writes until separate synthetic and explicitly authorised validation.

## Status of this pack

This is **offline evaluation support only**. No live V1 or V2 tool has been invoked. No question has been sent to the user's hub. The observed alpha.51 overview counters are a successful *installed UI visibility check* and do not count as a held-out model answer, system audit or paired V1/V2 result.
