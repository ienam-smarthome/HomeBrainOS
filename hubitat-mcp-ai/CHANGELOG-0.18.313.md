# HomeBrainOS v0.18.313 — Stage 6.10: Strict evidence citation clarity

## Real Ollama Cloud finding

The 1 November 2026 v0.18.312 synthetic mesh plug run selected all three relevant S2, S3 and S1 source groups in four Ollama Cloud requests, but Stage 6 rejected the final explanation with `unknown_or_malformed_evidence_citation`. The screenshot does not expose the rejected JSON or exact ID, so the failure might be a source-container ID (S2), an unknown record ID, a malformed list, a duplicate or an unsupported kind. We do not assert which one occurred.

## Change

- The final explanation prompt explicitly supplies `allowed_evidence_record_ids`, built from the initial focal record and **only** the sources actually selected by the model. It clarifies that S1/S2/S3 are group identifiers and that sentence citations and atomic assertion `record_id` must use exact inspected leaf record IDs such as I1/E2. No unread or host-gold references enter the prompt.
- The new `stage610_citation_contract.py` strictly validates citation kind, list cardinality, duplicates, ID type, selected source-container misuse and unknown/unexamined records. It NEVER guesses an S*→E* mapping, rewrites unsupported statements or weakens the strict factual citation gate.
- Safe, constant error categories distinguish `source_container_instead_of_record_id`, `unknown_record_id_in_citation`, `malformed_evidence_citation_ids`, `duplicate_evidence_citation` and `invalid_claim_type`. No raw failed model text, secrets or specific unknown IDs are returned.
- The final prompt's top-level JSON instruction now agrees with optional next-evidence assessment fields introduced in Stage 7.8/7.9.

## CI

Mocked regression tests cover valid leaf record IDs, S* container misuse, unknown or unseen IDs, malformed or duplicated lists, unsupported claim kinds, correct prompt whitelist, no reference-oracle leak, four-cloud-request cap and strict fail-closed rejection preserving postrun source selection. Existing suites remain active.

**Safety:** Synthetic Stage 6/7 only, no added AI call or recovery retry, no Hubitat/HA live device operation, no production publisher change. Citation validation does not independently verify natural-language meaning.

## Acceptance

On phone, update to v0.18.313 and repeat Stage 6 → Mesh plug: connected broker, offline device. Expected: a properly sourced model-authored explanation and Stage 7.9 review. If Gemma still produces an invalid citation, the answer remains rejected but the more specific safe category can identify whether it used a source-container ID, unknown record, duplicate or malformed list. Never automatically promote an uncited sentence.
