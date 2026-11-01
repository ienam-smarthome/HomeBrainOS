# HomeBrainOS v0.18.311 — Stage 7.8.1 optional-follow-up contract recovery

Synthetic-only Stage 6/7 pilot; no change to production publisher, model routing, Hubitat/HA devices, automations or cloud allowance.

## Live failure

A real Gemma Cloud Stage 7.8 MQTT synthetic case selected all 3 reference-relevant records in 4 provider requests, but the final answer was discarded with `next_evidence_field_invalid`. The strict v3 validator previously required `next_evidence` to be a plain 5–220-character string; a malformed/missing/oversized optional field failed the **entire** answer. The screenshot did not include the raw model JSON, so which exact invalid form was returned is not known. The optional structured `next_evidence_assessment` also previously failed the entire answer when malformed.

## Changes

- Keep **strict factual sentence** schema, source citations, atomic declarations, uncertainty checks, and 4-request budget. Unexpected top-level fields remain hard failures.
- For v3 only, invalid/missing `next_evidence` becomes a **blank, withheld suggestion** with a host-written safe diagnostic. Invalid optional `next_evidence_assessment` is discarded and explicitly flagged, not repaired or inferred. V1/v2 remain strict; valid v3 responses remain unchanged.
- Stage 7.8 review packet records a bounded follow-up field status and distinguishes valid free-text from any optional declaration. No raw invalid text/JSON is returned or used as evidence.
- The mobile UI states that the optional suggestion was unavailable and that factual sentences still require independent review, rather than labelling malformed advice as model-authored.
- Mock regressions cover object/list/null/short/oversized/missing advice, malformed assessment, valid backwards compatibility, strict citation/claim validation, no extra cloud calls, synthetic isolation and no publication approval.

## Security and causal boundaries

This does **not** guarantee factual correctness of the model-authored answer. Host matches of declared atoms are not proof of all prose semantics. Malformed citations, sentence schemas and unrecognized top-level keys still fail closed. No second-generation retry, hardcoded answer or publisher activation. Actual Ollama Cloud acceptance remains outstanding.

Rollback: revert this PR and return to v0.18.310.
