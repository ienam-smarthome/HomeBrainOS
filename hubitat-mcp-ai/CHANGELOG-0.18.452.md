# HomeBrainOS v0.18.452 — Claim-validated factual floor on failed causal synthesis repair

## Live evidence and why the previous answer failed

The user's installed v0.18.451 first presented a seemingly careful unknown-cause
answer for a reported 00:30 GMT OFF event on 7 November 2026. The full Technical
JSON showed two ungrounded subordinate statements: FP400 motion=inactive was
known only from a **collector-received Historical Journal** observation;
both native absolute-window sensor queries returned zero source history
rows. The model nonetheless called this a source sensor observation 19s
before OFF. Additionally the returned app logs were queried around an earlier
15:13 event, not the requested 00:30 OFF; the device log sample was at 20:58
ON. Despite nine model rounds and 19 MCP calls, repair failed once. These
failures cannot be addressed reliably by repeatedly adding device-specific
word patterns.

## General change

- Introduce `causal_verified_fallback.py` as a small, generic source-typed
  answer constructor. It is called from the existing final API boundary
  only when a **read-only causal_provenance latest-OFF** investigation has
  `synthesis_repair_failed>0`, `rootCauseVerified=false`, one
  authoritative requested focal OFF boundary, and a matching verified
  source-reported OFF state history.
- Construct host-owned `observed_value` and (when available) ON→OFF
  `observed_interval` claims, and validate through
  `claim_evidence_contract.validate_claims`. Durations are computed in
  code. Model sentences and model-proposed claims are not trusted in the
  fallback answer.
- Distinguish a state-reporting bridge from the initiating controller.
  Preserve a matching positive Hubitat command issuer if independently
  returned; otherwise describe returned bounded command-off records and
  avoid global absence claims. A missing matching command cannot identify
  an external origin.
- Admit source-timed motion/presence only when a verified absolute native
  window contains the actual event and correctly matched source clock.
  A Historical Journal collector-received observation can only support
  existence of a partial archive row, never sensor event timing or a
  sensor-to-OFF lag. Empty verified windows are not proof of inactivity.
- Compare **requested** past-log `since` and `until` timestamps against
  the actual focal OFF timestamp before describing source coverage. Queries
  for other intervals cannot be described as focal app-log evidence.
- Return a clear uncertainty verdict. Keep `evidence_validation.claim_validated_factual_floor`
  when the deterministic floor is published, without treating it as a
  verified root cause or adding more model/tool rounds.

## Safety and compatibility

This is not broad general claim-first publication. The new claim-v2 schema
remains shadow-only except for the tightly gated host-created OFF factual
floor. If focal source identity or scope is unverified, keep the existing
guarded answer; never replace write/confirmation/noncausal responses. No
change to Hubitat, Home Assistant, provider billing, operational limits or
sensitive write authorization.

## Verification

Synthetic, device-neutral regression tests cover failed-repair fallback,
unverified archived clocks, incorrect log windows, validated durations,
positive/negative bounded command evidence, native source-timed sensor
history, missing focal source, successful repair and write/confirmation
exemptions. CI on the final PR head is required before merge; CI success
is not a source-real quality measurement. Install v0.18.452 and rerun
the same read-only question with complete Technical JSON to verify the
fallback flag and factual content before widening claims publication.
