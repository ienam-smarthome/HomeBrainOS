# v0.18.265 — V3 D1 shadow claim pilot after Historical Journal recovery

## Live v0.18.264 diagnosis
The 30 October 2026 14:50–15:30 Bathroom Light 1/2 investigation produced 20 independently source-timed target switch reports and 20 collector-reception copies, but it still could not verify the original ON initiator.

The latest run used 14 tool calls / 5 model rounds / 35.7 s and returned 40 witnesses, zero source-timed input witnesses and zero matched target ON-command issuers. It measured `v3_claim_envelope_missing=1`, `v3_shadow_legacy_digest_replaced=1`, `v3_shadow_source_time_token_matches=10`, and still left command-history coverage unchecked.

**Architectural reason:** `unified_investigation_instruction` only included Stage D1's optional claim-attestation pilot if *both* archived target histories were source-attested at the moment the original evidence instruction was composed. In this case the model first saw empty/native newer history and the Journal source rows became available later from `_recover_journal_into_discovery`. The follow-up `cross_source_discovery_checkpoint` exposed the new journal state but **not** the optional claim contract. Missing envelope is therefore inconclusive: it cannot be treated as a model failure when it was not asked.

## Implementation
- Factor the bounded, two-target, source-witness-gated pilot into one pure `causal_claim_pilot.render_shadow_claim_pilot(facts)`.
- Both original synthesis evidence and **the later journal recovery checkpoint** now use exactly the same pilot text, witness IDs and typed claim grammar, independently of read order.
- Only a verified two-target source-time journal with missing native switch coverage qualifies; single-target or collector-only data cannot activate it.
- Construct a compact cross-target witness catalog rather than showing many examples from only one busy light.
- Increment `v3_claim_pilot_recovery_offered` only when the recovery checkpoint containing the pilot is actually added to the model messages. A missing claim envelope without an offer is **not** evidence of inability to produce typed claims.
- All claim validation and legacy publication contracts remain unchanged. This is a read-only diagnostic pilot and does not force extra tool calls, claim an upstream issuer, or grant new permissions.

## Acceptance and next phase
Tests cover initial-empty to recovered-journal handoff, parity across two prompt paths, real source-witness IDs for both verified targets, rejection of collector-only and one-target pilots, and structured-claim validity remaining separate from arbitrary model prose.

Follow the new pilot counter with `v3_claim_envelope_present/valid/rejected/missing`; the model may still omit an optional envelope, and shadow success alone must never authorize publication. The observed reduction from 27 to 14 tools also removed sensor and command evidence: faster is not automatically a better investigation.

The next separate architectural stage should address model breadth and witness-to-prose consistency before conditionally preserving native answers. No live Hubitat/HA changes. Full CI required.
