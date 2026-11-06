# Q2 — historical first-answer provenance audit (6 November 2026)

## Why this milestone follows the permanent charter

Four actual local first-answer pairs were previously captured privately on
4 November 2026 against four **unchanged synthetic/anonymised offline packets**.
They already have substantive *qualitative* source reviews (MQTT freshness,
OFF-command attribution, heating restoration and Rule Machine parent identity).
We must not request them again or rewrite the source packet to favour a model.

The original model responses and private first-answer folders are **not stored**
in this public repository. The prior conversation and domain reviews establish
recorded answer hashes and case-specific findings, not a newly authenticated
independent blinded reviewer. The four Q2 runs used **four different checkout
build SHAs**, even though each individual pair used the same checkout. The
existing `answer_quality_paired_reviews.py` properly refuses to present
different builds as a single matched-build scorecard. Do not weaken that gate.

## What was implemented

- `tests/fixtures/answer_quality_q2_recorded_pairs_v1.json` stores only
  metadata already documented in previous source reviews: four frozen case
  identifiers, packet fingerprints, original answer SHA-256 digests, local
  model/provider, user-reported checkout SHA, recorded first-attempt index
  and model-request timings. **No private answer text, household logs or
  personally identifying information is included.**
- `scripts/answer_quality_q2_recorded_pairs.py` validates every pair with
  the unchanged `build_fixed_packets`, `pair_metadata` and
  `validate_run_manifest` checks. It rejects private-text fields,
  mismatched packet hashes, mixed checkout SHAs *within* a pair,
  duplicated case IDs, bad first-attempt metadata or identical model arms.
- The audit produces descriptive timing deltas and a per-case record
  without the original answer digests. It reports **zero formal human
  reviews and no factual correctness percentage**.
- Tests verify both the four recorded observations and malicious/
  inconsistent edits fail closed.

Run the offline audit with no cloud, Ollama, Hubitat or HA access:

```bash
python scripts/answer_quality_q2_recorded_pairs.py
python -m pytest tests/test_answer_quality_q2_recorded_pairs.py -q
```

## Original observations (not a production or quality benchmark)

| Source-only case | Qwen3.5 4B request | Llama3.2 3B request | Qualitative source gap |
| --- | ---: | ---: | --- |
| MQTT session vs endpoint | 20.344s | 8.531s | Llama omits watchdog discriminator |
| Command issuer vs state reporter | 26.344s | 10.594s | Both invent delivery/causality; original Qwen answer visibly incomplete |
| Early OFF heating setpoint | 22.672s | 6.406s | Qwen invents mechanisms; Llama omits restoration and demand |
| Native Rule Machine parent identity | 19.657s | 8.297s | Neither establishes direct source-typed class binding |

See [four-domain qualitative assessment](ANSWER-QUALITY-Q2-FOUR-DOMAIN-LOCAL-REVIEW-20261104.md)
and linked original reviews for the exact evidence limitations.

These four observed pairs put the candidate Llama faster in 4/4 *recorded
model-only requests*. The audit computes median request times, not production
user-visible service latencies, cross-build causal speed effects, factual
grounding or p95 population claims. No randomised paired multi-run study
is represented. Reconstructed metadata is still user-reported; hashing it
does not prove provider delivery or model identity.

## What the new audit cannot conclude

**Quality is NOT MEASURED in the official scorecard.** Historical source-review
notes and original digest checks do not substitute for retained original
private answer files plus individually completed, answer-bound human review
rubrics. The new script does not reopen the original answer files, independently
rehash the provider response, assign grades, infer Claude parity, merge different
checkout builds or certify a model winner. Do not convert source-review
synopses into numeric claim denominators or fictitious reviewer identity.

A formal Q2 measurement would require independently inspecting the **existing**
private answer files, SHA-binding each arm's full original first-answer text,
finishing the five source-review dimensions and reporting separately by
session/build; no new model trial is needed to establish that ledger.
If the private originals are not accessible to the reviewer, retain the
currently correct `not_measured` status. Further development should address
the documented cross-domain evidence-use failures using comparable source
packets and negative controls, not added room-specific response templates.

## Safety, tests and rollback

This change is a standalone offline evaluation aid, **no add-on version bump**,
no production model/publisher modifications, no additional MCP rounds,
no cloud charge, and no Hubitat/HA/router/repository automation mutation.
The only repository changes are this script, public metadata, regression tests
and roadmap handoff. Roll back by reverting these standalone files if the
historical data cannot be reconciled against the immutable source manifest,
or if the audit ever falsely certifies answer quality. CI should prove only
reproducibility of the metadata checks, never semantic model correctness.
