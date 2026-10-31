# HomeBrainOS v0.18.302 — Stage 7 independent manual prose review pilot

**Additive synthetic-only feature. No change to production publisher or live Hubitat/Home Assistant.**

## Why

The user's real Stage 6 tests have progressed from simple 4/4 claim-classification to 3/3 relevant source discovery and 14/14 exact model-declared source-value atoms on a difficult, delayed OFF report. But neither an accurate source selection nor a matching atom proves that the entire model-authored sentence is true. For example, a sentence claiming that a light **physically turned on because of motion** could carry a perfectly valid `state_report` citation and a correct `state=on` atom; the causal and physical claims remain unsupported.

Testing more similar prompts will not resolve this underlying distinction. A genuine independent evaluation must inspect every sentence, with access to full source records, including evidence the model skipped, and separately assess omissions and causal confidence.

## Stage 7 workflow

For **successful** fictional Stage 6 investigations, without any additional cloud calls:

1. The host freezes a source-complete, **synthetic-only** review packet *after* the model has finished its source-selection decisions and answer. It contains the initial observation, all five fictional source records (including unselected distractors), the question, the model-authored sentences and explicitly declared types/atoms.
2. Hidden benchmark `gold_sources`, expected finding types and reference labels are **excluded from this reviewer packet** so the external/human reviewer can work independently. The host retains separate hidden scoring as before.
3. The dashboard provides **Stage 7 · Independently review every sentence** in a collapsed section. The reviewer can inspect read/unread source records and rate every actual natural-language sentence as supported / partially supported / unsupported / uncertain.
4. The reviewer separately assesses overall **important omissions** and **causal caution**. The "not reviewed" state is the default; scores are never filled automatically from the author's claimed citation labels.
5. **Copy independent review packet** explicitly exports only this fictional packet plus any optional local manual ratings as formatted JSON. Nothing is automatically sent to a second model, an external service or a database; no extra Ollama Cloud inference is performed. If the user chooses to compare with another model, the copied evidence can be given to an independent reviewer, but that is a separate deliberate action.

The review packet has a stable short content digest for reproducibility (not a signature or authentication). Its source fields are allowlisted; arbitrary token/password properties are not serialized. The packet is a supplementary field of the existing successful Stage 6 response. A malformed final answer continues to fail closed as in v0.18.301, without generating or publishing a review packet.

## Explicit limitations

- This is **a human-review workflow**, not a fully automated external fact-checker. It does not establish semantic accuracy by itself, and does not repair, accept or republish any model answer.
- Merely choosing a reviewer verdict does not establish a verified ground-truth result. The judgment should be based on the complete synthetic source corpus.
- Full source records are shown only after an investigation completes, preserving blinded model source selection. A repeated run on the same fictional case may be less useful if the human has seen its source corpus.
- v0.18.302 contains **no live-history collection, no shadow production replay, no source-vs-live Hubitat comparisons, no automatic retries, and no changed model/router/publisher**.
- The optional Stage 6 inference remains consent-gated, using the user's existing Ollama Cloud account, up to four requests. Stage 7 itself makes **zero additional model requests**.
- GitHub CI uses mock cloud clients and built-in fictional test fixtures, including an adversarial example where valid atoms coexist with false narrative implications. No household or secrets are sent.

## Suggested next phone test

Upgrade the add-on to v0.18.302 and run the **Two apps issue competing commands** Stage 6 fictional scenario once, with consent (up to four cloud requests). Open the new Stage 7 review section, inspect the two different issuers and the OFF state report, and judge whether the prose incorrectly attributes the OFF state to one app without direct command-to-device proof. If helpful, use **Copy independent review packet** and share it for a separate, blinded factual analysis.

Production publisher stays unchanged. No live devices are touched. Do not treat an unreviewed or high-rated answer as production-ready.

Rollback: revert the PR and return to v0.18.301.
