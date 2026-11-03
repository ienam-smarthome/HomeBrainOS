# v0.18.382 — Q1 first-question input fingerprint

## User-directed scope

Internet-blocker research is **paused at user request**. This release resumes the permanent Answer Quality Q1/Q2 programme and makes no native Rule Machine authoring or Internet blocking changes. The delayed writer stays disabled.

## Evidence gap and general hypothesis

The frozen Q1 inventory already contains **40 curated synthetic/anonymised packets and 13 legacy tasks**. Numerous real, privately reviewed HomeBrain answers had a version label and useful source receipts, but the technical response could not show which **literal user question** reached the `/api/ask` server. Consequently a reviewer could not securely compare that run with the registered first-attempt question, even if a user supplied an apparently matching prompt afterwards. Neither the running Git SHA, actual model input, actual first attempt, nor complete external source evidence was authenticated. Official first-attempt useful and grounding rates remain **NOT MEASURED**.

## Production change

The API response builder now adds an optional `request_provenance` object **only when the validated HTTP request's question is supplied by the /api/ask route**:

- `source="api_ask_request"`;
- `normalization="collapse-whitespace-v1"`;
- `normalized_prompt_sha256`: SHA-256 of the actual validated submitted prompt after trimming/collapsing whitespace;
- `model_delivery_verified=false`, `first_attempt_verified=false`, `deployed_build_sha_verified=false`.

This does **not** include the raw question, conversation history, prompt snippets, device names, IP addresses or source payloads. The hash is an API-reported fingerprint, **not a signed trusted execution attestation** and not proof that the model saw unchanged text. It can be re-evaluated against the **same registered question** by the offline metadata-only Q1 capture CLI. Existing client responses are unchanged except this additive diagnostic.

The capture tool rejects invalid digest shapes and unrecognised provenance sources/normalisations; it marks contradictions when a separately supplied question differs from the API-reported digest, rather than granting an exact match. It may now establish **registered question match at the API boundary** without requiring a separate question paste. Curated *offline* packets never become *live* first-attempt cases simply because their hash matches. No human truth grade, source completeness, deployed commit authentication or first-attempt judgement is synthesised.

## Tests and measurement

Offline regression coverage: exact API-question normalization across whitespace; stable digest independent of response text; no raw prompt disclosure; failed/missing/forged hash; user-supplied question conflict; curated versus live case boundary; no implied model-delivery/build/first-attempt proof. Existing frozen case definitions and rubric unchanged. Run all CI at the exact PR head; merge only when green.

**Before:** Q1 real diagnostic runs on older builds cannot verify exact submitted prompt via technical JSON; number of independently certified live first attempts in the published Q1 baseline is **0**. **After:** source changes and synthetic tests on this PR, but installed prompt-hash acceptance and the official baseline remain **NOT MEASURED**. This is an evaluability improvement, not an accuracy, naturalness, speed or Claude-parity result.

## Rollback and next step

Revert the `/api/ask` additive provenance, capture validation and tests if privacy or compatibility regressions appear. The next development task is a **single read-only Q1 registered prompt** on installed v0.18.382 with complete answer and Technical JSON; use the new hash for question matching, retain original private answer and independently assess source coverage/claims. Exact deployed Git build provenance and real first-attempt status must still be verified separately. A Q2 model A/B requires consented model use on the *same frozen packet* and real independent review. No Hubitat/HA writes and no paid model upgrades were performed in this development.
