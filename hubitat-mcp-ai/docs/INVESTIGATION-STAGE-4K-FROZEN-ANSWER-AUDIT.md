# Stage 4K — frozen-answer, source-bound post-generation adjudication

Source version **v0.18.291**, following Stage 4J on main v0.18.290.
**Source-only/offline; not deployed, not a publisher or live observer.**

## The missing validity check

The Stage 4A typed claims can match host facts while the prose adds unsupported
causation or a physical outcome. Stage 4I can independently reject such
individual propositions, and Stage 4J can measure whether an extractor captured
these assertions, but Stage 4J's original twelve sentences are pre-authored
synthetic examples.

Stage 4K makes a reproducible *answer-level* audit possible. The caller freezes
a complete Stage 4A model draft **before** attaching a separate per-sentence
reference annotation. The full draft and a freshly regenerated Stage 4A
source packet are bound via SHA-256 digests. This prevents an evaluator from
silently changing sentence text, order, citations, source facts or packet scope
between freezing and evaluation. The host rebuilds the packet **from the
supplied scoped receipts**; it never trusts a packet furnished by a model.

The returned freeze manifest contains digests and sentence count, never prose.
The caller must keep the draft, receipts, private adjudication labels and
manifest in a local secure context. Never upload household logs or identifiers
to a public pull request, CI artifact, or model outside the owner's consent.

## Offline contract

1. Call `freeze_stage4k_answer(receipts, draft)` with a complete candidate
   Stage 4A draft, at most 16 sentences of up to 500 characters each, and
   scoped read receipts. Retain the frozen manifest alongside the answer.
2. Have a **separate post-generation reviewer** label every whole sentence's
   positive and implied atomic assertions using Stage 4J atom types. At most
   five reference atoms per sentence. Use this exact annotation envelope:
   `{schema:"homebrain-stage4k-adjudication.v1", draft_sha256,
   packet_sha256, sentences:[{sentence_sha256, reference_atoms},...]}`.
   This is a protocol requirement, **not** automatic proof of independence.
3. Call `audit_stage4k_frozen_answer(receipts, draft, manifest, adjudication,
   model="qwen2.5:3b", invoke=explicit_local_adapter)`. The adapter sees
   only the sentence and host packet; the withheld reference atoms never enter
   its request.
4. The Stage 4J evaluator checks extraction recall/precision and missed
   high-risk assertions; Stage 4I checks each extracted atom against exact
   source witnesses. A count-weighted report covers **all** 16 sentences
   across bounded Stage 4J batches. Failed model calls count as missed
   assertions, never an innocent or passing result.
5. Treat all output as diagnostic. The report includes no sentence text,
   device identifiers, source values or raw model outputs.

The unit suite uses synthetic fixtures and stubs only. No new workflow
calls a model, and no external fixture collection is enabled.

## Remaining proof gaps — explicitly not claimed

- A self-supplied read receipt is **not authenticated live source provenance**.
  Regenerating the packet proves equality relative to that input only.
- The digest binds text and sources but cannot prove the reviewer received
  the answer later, or independently labelled every implied proposition.
  A missing annotation is not automatically detectable without outside
  human review.
- The model-generated origin of a draft is not verified by a digest.
  Current regressions use constructed drafts, not newly captured authentic
  model-produced, owner-consented household answers.
- SHA-256 is not a signing protocol or permissions mechanism. Treat private
  digest manifests as potentially guessable for simple text.
- Even a 100% labelled-corpus extraction score and all proven source atoms
  do not establish semantic safety for previously unseen prose.

Every report has `publisher_approval=false`,
`reference_labels_post_generation_independence_authenticated=false`,
`supplied_receipts_external_provenance_authenticated=false`, and
`unseen_prose_semantics_certified=false`.

**No imports into active agent, tool, publisher, HA, Hubitat or model routing.**
No device control, live captures, provider credentials, or publication changes.

## Next acceptance

Obtain explicit owner consent for redacted **real model-produced answers** and
their genuine source receipts. Freeze the answers *before* external/manual
adjudication, verify provenance, audit multi-sentence implied risks, and report
high-risk omission/error rates. Review independent source authentication and
permission boundaries before even a reversible read-only rollout. Until then
the current V3 publisher remains authoritative.

Rollback: revert Stage 4K's additive source, tests, and documentation.
