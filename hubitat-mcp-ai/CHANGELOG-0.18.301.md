# HomeBrainOS v0.18.301 — Stage 6.6: preserve synthetic investigation when final model JSON fails

## Field result and evidence

After v0.18.300 (Stage 6.5 question-value source ranking), the user ran the **Delayed OFF report versus device time** benchmark and received:

> Stage 6 independent explanation failed: invalid structured model response. No retry was attempted.

This means the model reached the final-answer stage, but the strict response validator rejected the output. The exact failure subtype is **unknown**, because the old handler collapsed malformed JSON, schema mismatch, missing source citations, incorrect atomic types and other structural problems. The screenshot does not establish whether the model had chosen S1, S2, S3 or S5, nor whether its prose was factually correct.

## v0.18.301 correction: preserve independently scorable progress, not rejected prose

- After the 1–3 model-driven fictional evidence-selection rounds, Stage 6 continues to request one final explanation (still at most **four** explicit, paid Ollama Cloud requests per benchmark).
- If the final model response violates the existing strict schema/citation/value-atom contract, **reject it without publishing any of its prose or claims**. Do not automatically retry, parse prose heuristically, hallucinate citations or bypass the existing validation gate.
- Classify only known static validator outcomes: invalid JSON, malformed fence, missing/incorrect top-level fields, unexpected sentence keys/count, unknown citation IDs, invalid or duplicate source-value atoms, missing uncertainty or next-evidence fields, oversized output and malformed nested structure. All other failures use an unclassified static reason; raw model output, provider bodies and exception messages never appear in the API.
- The dedicated HTTP 502 JSON response preserves a minimal **synthetic-only planning summary** from earlier successful rounds: selected source IDs, expected source relevance (post-run only), irrelevant picks, cloud attempts, planning-contract completeness, issue codes and ranking consistency failures. Gold labels are **never fed into a subsequent model call or used to choose a source**.
- The dashboard shows the error category and this partial source-selection summary, explicitly saying *the final answer was rejected and not fact-checked*.
- Authentication, network, timeout and provider HTTP 401/403 failures retain their separate existing handling. No false reclassification as a schema failure.

## Why we are not simply relaxing the answer format

The current final-answer contract requires 1–7 model-authored sentences with typed citations and an optional v2 exact source-field/value atom envelope. A citation may be wrong; the validator must continue to reject structurally invalid evidence claims. The failed response could also be malformed JSON or a model-format mismatch, which is not yet established. Accepting free-form prose without knowing the failure would weaken the safety properties the architecture is intended to preserve.

## Phone test and boundaries

1. Update **Hubitat MCP AI** to **v0.18.301**.
2. Run **Stage 6 → Delayed OFF report versus device time** once with existing explicit consent for up to four Ollama Cloud requests.
3. If the model fails final validation, share **Validation category**, **Previously selected fictional sources** and **Planning review complete**. We can evaluate whether Stage 6.5 chose S1 without requiring another repeated test merely to see the planning stage.
4. If the result succeeds, inspect full host source scores and natural prose as before. Source-value atom matches alone still cannot certify all implicit text semantics.

**No real Hubitat/HA device read or write, publisher activation, model-routing changes, new account/key, retry or CI cloud inference.** Only static fictional data is sent to the primary model on the user's explicit click. Test CI uses mock cloud responses. Add-on installation/upgrading is controlled by the user.

Rollback: revert this PR, restore v0.18.300.
