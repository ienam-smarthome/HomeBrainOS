# Hubitat MCP AI v0.18.222 — Independent fact and explanation verification

## Why

Native READ V2 explicitly invites the model to return both a strict `claims`
array and optional `findings` narrative in the same reply. The fact validator
previously required the **entire** JSON object to contain only `claims`.
A correct combined reply could therefore be discarded, with all otherwise
verified facts replaced by a fallback. The narrative checker also rejected
all findings if any one segment had an unverifiable source or wording.

Both faults are cross-domain orchestration/validation defects, not reasons to
add device-name or question-word exceptions.

## Changes

- The typed fact validator now independently evaluates `claims` from a
  response containing optional `findings`. Neither the prose, its claimed
  confidence nor its schema can grant publication of an unverified fact.
  Unexpected authority fields remain rejected.
- Each independently source-ID-matched narrative finding is now checked on
  its own. If another finding is invalid, it is withheld without erasing
  accepted text. The user sees a count of withheld findings, not their
  speculative content. If no finding passes, existing source-bound fallback
  remains in force.
- Both paths keep their separate publication boundaries. This does **not**
  attempt unrestricted natural-language entailment or prove any physical
  cause from correlation.
- Read-only V2 alone is affected. The existing main Ask engine, Hubitat
  writes, confirmations and backup/readback protection remain unchanged.

## Regression tests

`pytest -q tests/test_investigation_v2_segmented_reasoning_0_18_222.py`

The suite checks optional findings, unknown fields, malformed narratives,
valid/invalid segment mixing, forged subjects, absent source receipts,
oversized findings and an integrated fake MCP two-read investigation that
accepts verified claims and narrative while withholding an invented cause.
Tests never connect to Hubitat or make physical writes.

## Operator live QA — read-only

Use the existing `/v2-test` page with V2 test access enabled. Compare
concise answers against the Investigation details and Read receipts.

1. **Room state**: "Which Bathroom lights are off, and which additional
   lights are actually assigned to the Bathroom room? Read only."
2. **Device health**: "Why is Bedroom 3 Mesh reporting offline? Distinguish
   actual plug communication from the driver's MQTT and watchdog status.
   Change nothing."
3. **Historical cause**: "Investigate why Livingroom Light 1 remained on
   overnight on 24–25 October. Separate issued commands, recorded state,
   sensor evidence and missing history. Do not change devices."
4. **Automation**: "Why did the heating protection timer stop or restart?
   Compare scheduler logs, thermostat demands and source time coverage.
   Read only."
5. **Broad health**: "Check recent Hubitat warnings, identify independently
   verified affected devices and explain which observations are inconclusive.
   Do not change anything."

For each test, retain the question, answer, evidence trace, failed reads,
actual time and latency; compare against V1 or Claude only on evidence that
was truly available to each. Never infer a full 24-hour history from a
requested lookback or a capped sample.

## Release limits

This is a **first safety-preserving reasoning-quality refactor**, not a full
rebuild or a demonstrated Claude-equivalent investigator. Model initiative,
hypothesis discrimination, source history coverage and overall answer
naturalness still require live paired tests. Do not promote V2 to production
from offline CI alone.
