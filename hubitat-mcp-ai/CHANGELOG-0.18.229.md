# Hubitat MCP AI v0.18.229 — Question-relevant evidence, not command counts

## Problem confirmed by independent live regression

The user asked why Livingroom Light 1 stayed ON overnight 24–25 October.
The Native V2 model collected commands largely from 28–29 October, a
24–25 October event page containing only device network-status records
and one Google Home refresh, and two app-configuration metadata reads.
The system called that evidence "multi_source_factual_brief_ready" and
presented button and app IDs instead of answering.

The completed evidence acquisition was real, but not relevant to the
requested cause. Many unit tests passing did not measure this.

## Architectural first stage

- Introduce a **generic dated-incident evidence-relevance contract**:
  for a uniquely verified device and explicit historical incident period,
  classify material state/actuation events *within the user period*
  separately from events and command counts outside it. Telemetry and
  a broad app-count catalog do not automatically become a causal explanation.
- Use the user-specified incident bounds to correct a model-selected
  `hoursBack` history read when its relative lookback cannot reach the
  incident. Preserve an explicit absolute source window and all existing
  identity, schema, effect and READ-only execution guards.
- Expose the real event relevance result to the already operating
  model planning loop, so it can choose a more relevant source rather
  than treat the first returned page as success.
- Make the host "multiple verified facts" completion shortcut conditional
  on actually returning material incident evidence. This is **not**
  proof of causal correctness when evidence exists; it only blocks
  obvious unrelated-evidence success.
- If the dated incident read has **no relevant returned actuation/state
  evidence**, use a brief **human-readable, name-first answer** explaining
  what remains undetermined and the specific missing sources.
  Do not publish device IDs, command counts or verbose claim-validation
  headings as the user-facing answer. Preserve receipts for technical use.
- No changes to Main Ask, production controls, permissions, external
  devices, AI model selection, cloud costs or V2's read-only boundary.

## Tests

`pytest -q tests/test_investigation_v2_incident_relevance_0_18_229.py`

The suite replays the independent light incident, ensures 28–29 October
button counts cannot answer the 24–25 October question, tests a
contemporaneous on/off event, unsupported or ambiguous identity, and
the real model-proposed `hoursBack=96` error.

Full repository tests, container smoke checks and release metadata
must pass before merge.

## What this does not yet solve

This is the **first general reasoning-quality gate**, not Claude-level
autonomous causal analysis. When there *is* sufficient incident evidence,
V2 still needs a richer model-directed evaluation of sensor activity,
automation execution, competing hypotheses and independently supported
natural-language conclusions. It must not infer a physical cause from
mere command proximity or hallucinate missing histories.

## Next live acceptance

Repeat the Livingroom Light 1 24–25 October investigation. If event
retention still returns no relevant switch/motion/automation data, the
answer should explicitly say it cannot identify the overnight cause
and indicate the missing evidence, without displaying internal
ID/count summaries as a conclusion. If new relevant historical data is
returned, V2 must use it rather than claim the period is empty.
