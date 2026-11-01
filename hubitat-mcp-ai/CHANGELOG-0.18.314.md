# HomeBrainOS v0.18.314 — Stage 6.11 citation-shape prompt hardening

**Synthetic-only Stage 6/7 experiment; the production publisher, Hubitat/HA device access and normal model routing remain unchanged.**

## Real-model observation

The user's v0.18.313 Ollama Cloud mesh-plug test retrieved all 3 reference-relevant fictional sources (S2, S3, S1) in 4 requests, with no planning inconsistencies. The final explanation was correctly rejected with `malformed_evidence_citation_ids`. This safe category means at least one sentence's `evidence_ids` was not a 1–3-item list of nonempty string leaf IDs, but the exact malformed shape cannot be recovered from the supplied screenshot. This was an answer contract failure, not evidence of missing source selection.

## Changes

- Explicit Stage 6 synthetic final-answer contract: `evidence_ids` must be a JSON array of **1–3 distinct nonempty strings** that appear in the already supplied `allowed_evidence_record_ids`; never a scalar, object, null, empty array, mixed type, CSV string, duplicate or array with more than 3 members. **Prefer a single ID** for a simple sentence; 2–3 only when the sentence relates multiple source records.
- One exact, non-causal, illustrative JSON sentence-object example (with `evidence_ids:["I1"]`) demonstrates the expected v3 array, empty `atoms` and epistemic fields. It is identified as a shape-only example not to copy into the authored explanation.
- No citation coercion or repair. Existing Stage 6.10 strict validation, source-container/leaf boundary, fail-closed rejection and static-safe diagnostics remain intact. Unverified natural-language semantics are never auto-certified.
- Regression tests cover scalar string, CSV, object, null, numbers, empty/oversized/heterogeneous arrays, repeated or blank IDs, source-container misuse, valid leaf IDs, all 3 fictional benchmark scenarios with 4 mocked Cloud calls, and rejected response preserving completed evidence selection.

## Acceptance

Update to **v0.18.314** from the phone and run **Stage 6 → Mesh plug: connected broker, offline device** with explicit consent (up to 4 existing Ollama Cloud requests). Inspect the model-authored explanation and Stage 7.9 independent reviewer. If the model still emits a malformed citation, the run must fail closed and disclose only the safe category, with no retry, claim publication or device change.

**Limitation:** Prompt guidance improves expected compliance but cannot guarantee the Cloud model will obey it. Tests establish local contract behavior, not real-model acceptance.
