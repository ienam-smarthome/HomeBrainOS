# Stage 4J — Prose-to-atomic claim completeness evaluation

**Source-only milestone v0.18.290**, following merged v0.18.289.

## What this stage tests

Stage 4I proved that a source command is NOT proof of a physical
outcome, upstream cause, or events absent from incomplete history.
But a model-written sentence might say BOTH "the command was issued"
and "the boiler fired" while reporting only the first, verifiable atom.
A source validator that checks only the model's self-declared
claims could wrongly appear to approve that prose.

Stage 4J introduces a **separate claim-extraction completeness
benchmark**. Qwen2.5 3B reads the complete sentence and a bounded
Stage 4A source packet, and proposes all atomic propositions that
the sentence makes—including unsupported causal or physical claims.
The host independently measures proposed atoms against a
**separately held, pre-annotated synthetic reference** and checks
each extracted atom via Stage 4I source-proof obligations.

The model receives the sentence and source facts, but NEVER the
reference annotations or expected claim counts. The structured
output schema constrains atomic *types and source IDs*, not which
claims should be detected.

## Twelve adversarial constructed sentences

Across lighting, heating, ventilation and source history, the corpus
contains affirmative event and issuer descriptions, collector-clock
statements, known archive gaps, unverified physical effects,
claimed comprehensive records and a claimed causal link between
two source facts. Crucially, some sentences combine **a true
source event and an unsupported physical or negative assertion**.

The aggregate report measures:

- valid/invalid model extraction responses and inference errors;
- correctly identified, missed and extra propositions against
  the separately curated reference;
- **missed high-risk implications**, especially upstream causation,
  physical outcomes, event absence and historical completeness;
- claim-extraction precision/recall and fully matched sentences;
- host-proven and unproven extracted atoms using Stage 4I.

Source proof is NOT delegated to the LLM. The host projects exact
witness fields from verified packet IDs and disallows invented
source acknowledgements. The model selects *what a sentence says*;
the host determines *what the supplied evidence establishes*.

## Actual model execution without a PC

The new GitHub Actions workflow
`.github/workflows/stage4j-prose-atom-coverage.yml` uses a temporary
CPU-only machine with locally downloaded `qwen2.5:3b` weights.
It runs at the Stage 4J PR head and can also be manually dispatched.
`OLLAMA_NO_CLOUD=1`, `OLLAMA_HOST=127.0.0.1:11434`, no secrets,
read-only checkout, no user files, no external model inference.
All outputs are bounded allowlisted aggregate counts; no sentence
text, source values, event IDs, device names or model replies are
printed. Malformed/failed inference never receives a fabricated
good score. The job exits INCONCLUSIVE if no valid results exist.

## Limits and non-negotiable publication boundary

This is a **diagnostic extraction benchmark**, not a certified
semantic parser. Even if Qwen recognises every atom in twelve
examples, it may miss an implied claim in an unseen, complex or
ambiguous answer. Reference annotations are **host-curated
synthetic labels**, not independently authenticated real-world
events or independent human adjudication of Stage 4G's
actual newly generated prose.

A missing high-risk atom means the proof checker has never seen
that dangerous assertion. An exact extraction match **on this
corpus** is not evidence that all claims in arbitrary natural
language have been found. There is no blanket keyword-based
causation detector and no domain-specific phrase publication rule.

Every result declares:
- `extraction_completeness_on_unseen_prose_proven=false`;
- `reference_annotations_externally_authenticated=false`;
- `source_proof_does_not_attest_free_text=true`;
- `production_publisher_approval=false`.

**Neither a high extraction score nor host-proven atomic claims
allow production publication.** The V3 publisher, tool control
surface, LLM routing, Stage 3F capture and installed HA add-on
remain unchanged. No Hubitat or Home Assistant changes.

Next acceptance: extend coverage to real, owner-consented
redacted model-authored answers with independently labelled
*post-generation* semantics, measure omissions and unsafe
combinations on a larger corpus, and independently audit
transport/source provenance before proposing a reversible
read-only production shadow.

Rollback: revert this additive PR or disable only this workflow.
