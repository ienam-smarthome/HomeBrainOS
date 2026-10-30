# v0.18.261 — Causal Investigator V3 Stage A: shadow publication measurements

**Type:** observability-only release; existing model output/safety fallback unchanged.

## Motivation

The current `unified_incident_synthesis.reconcile_ledger_if_needed` replaces even a well-grounded native model explanation with `source_incident_digest` when a target's native history has a gap and independently source-timed journal state observations exist. This makes it impossible to compare native reasoning quality with the final published text.

The independent Claude and Gemini architecture reviews support eliminating the unconditional replacement eventually, but **disagree on the safe order**. The next step is a measurable shadow baseline, not removal of the hard-earned causal safety guard.

## Implementation

- Pure function `publication_shadow_assessment(draft, facts)` counts independent source-clock transition tokens that occur in the *pre-finalization draft*, records the number of existing contradiction flags, and source/gap availability.
- Request-scoped, allowlisted aggregate counters in `request_metrics`: `v3_shadow_publications_seen`, `v3_shadow_legacy_digest_replaced`, `v3_shadow_legacy_ledger_replaced`, `v3_shadow_legacy_draft_preserved`, `v3_shadow_history_gap`, `v3_shadow_draft_contradiction`, `v3_shadow_draft_mentions_source_time`, and `v3_shadow_source_time_token_matches`.
- No raw model draft, device names, timestamps, tokens, prompts or credential-bearing MCP result data are copied into telemetry.
- No model call, new MCP tool, altered read/write permission, changed prompt, changed output, or forced new investigation round.
- Timestamp-token coverage is **only an observability hint**, not a witness verifier or proof of causal accuracy. A clock reference can be present alongside false attribution.

## Baseline acceptance tests

1. An evidence-qualified draft overwritten by the old digest remains overwritten **in Stage A**, and its override is counted.
2. Contradictory draft remains safely replaced; contradiction flag counted.
3. A source-supported no-gap draft remains unmodified.
4. An incomplete non-archive history still falls back to a verified ledger.
5. Empty history does not produce synthetic source-time mentions.
6. Reception-only times are excluded from source-time mentions.
7. Request metrics do not persist narrative/device identifiers and reset between calls.

## Next staged steps

Stage B: source/role coverage ledger with a **positive issuer-verification fixture**, then model-selected source feasibility and stopping. Stage C: conditional, evidence-validated publication via opt-in/shadow replay, never publishing an unverified draft on a parsing failure.

The baseline should be measured before setting hard call limits. Neither eight calls per investigation nor numeric 95% issuer identification can be justified across incidents whose upstream command source was never recorded.

CI must pass before merging. No live Hubitat or Home Assistant changes.
