# HomeBrainOS v0.18.453 — Trusted response evidence adapter and claim-v2 shadow diagnostics

## Why

Claude supplied v2.1 `claims_v2.py` and `evidence_adapter.py` with 21 isolated
tests passing on a condensed Light 2 fixture. Against the full 7 November
Technical JSON, the four past-log requests all targeted earlier times;
two independently verified bounded sensor windows returned zero rows;
the FP400 motion=inactive journal observation was **collector-received**;
the candidate-sensor disposition said 4 of 10 *probed*, but only 2 native
absolute history windows were source-verified. Six reported OFF boundaries
overlapped the returned command history, with two command-off receipts
within a 2-second **matching convention**, not proof of exhaustive causal
coverage. Claude's unmodified validator accepted invalid clocks, invented
zero-result coverage, cherry-picked/duplicated transitions and failed reads.
Do not replace the canonical HomeBrain validator with this draft.

## Implementation

- Extend canonical `claim_evidence_contract.py` with
  `journal_observation` (explicit collector-reception role, never
  source-event timing) and `transition_pairing` (all eligible transitions
  chosen by trusted host packet, model may not supply witness/transition
  lists). The latter computes a one-to-one matching sample using source
  clocks and recorded Hubitat command issuers, **always scoped to returned
  records with incomplete retention**. It never proves an external cause.
- An `absent_in_scope` claim tied to a trusted focal instant now also
  requires its verified search window to contain that instant; 0-page,
  failed and non-zero-result reads remain rejected. Existing nonfocal v2
  contract fixtures keep their fail-closed coverage requirements.
- New source-neutral `claim_evidence_adapter.py` builds event witnesses
  from successful, read-only, current-turn receipts with one host-selected
  focal OFF boundary, a matching targeted device ID, and source-reported
  Hubitat switch boundary history. Duplicate history projections are
  deduplicated. Commands come from a validated, explicitly returned native
  command-off page; no model text/retention assumptions.
- The adapter quarantines Historical Journal observations as
  `journal-reception`, `collector-received`. They cannot back
  `observed_value`, source-clock `correlation` or a causal sensor lag.
  Two actual successful native absolute history windows remain distinct
  from four sensor-selection `probed` dispositions. `hub_list_rules`
  tool-menu replies do not attest installed rule/app inspection.
- Past app-log **requests** are counted only when source-verified request
  windows contain the focal time; a 0-page past-log query is not turned
  into an absence claim.
- The existing `api_response_builder.py` now attaches a non-publishing
  `evidence_validation.claim_evidence_shadow` metadata object for a
  successfully attested **read-only causal-provenance** answer. This
  counts host-validated claims, command pairing, journal receptions,
  independently returned sensor windows, candidate disposition and
  focal log request coverage. It explicitly says
  `model_claims_assessed=false` and `shadow_only=true`.
  There is **no new model call, MCP read, prompt injection path, device
  modification or replacement of successful model prose**.
- Keep the v0.18.452 deterministic factual floor on failed repairs and all
  existing write, confirmation and provider safety gates unchanged.

## Testing and acceptance

Regression fixtures cover whole-sample 6/2/4 command matching,
nonmatching log queries, source versus collector clock, verified native
sensor windows, model-selected subset attack, duplicate transition attack,
failed receipts, ambiguous focal selection, request-class isolation and
host-calculated numeric deltas for humidity, heating and power, plus
non-causal hub-health limitations. The synthetic tests are not live answer
quality measurements.

Merged [PR #1511](https://github.com/ienam-smarthome/HomeBrainOS/pull/1511) after all four required GitHub checks passed at exact head `1600af59001959d37e3e86b79aa7db4931b32efd`, including **6,738 passing Python tests**, packed add-on smoke and metadata. Squash main commit `755635e8fb08d8f976504a3f55ef145d21a30c6c`. Only after installation of
v0.18.453 can source-real read-only acceptance be performed: ask the same
most-recent OFF question and inspect both answer and
`evidence_validation.claim_evidence_shadow`. The expected **historical**
7 November packet has 6 returned OFFs, 2 matched command-offs, 4 without a
returned match, 4/10 selection-stage probed sensors, 2 native sensor
windows and 0/4 log requests containing the focal OFF. A fresh historical
response may legitimately differ as underlying event retention evolves.

The next milestone is to pass vetted model-proposed claim envelopes alongside
this shadow packet, freeze held-out multi-domain comparisons and promote
general claim-first publication only after first-answer usefulness and
unsupported-causality measurements improve. Do not retire overlapping guards
based on synthetic green tests alone.
