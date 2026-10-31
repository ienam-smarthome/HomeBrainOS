# HomeBrainOS v0.18.300 — Stage 6.5: question-linked evidence value

**Shadow-only, opt-in, synthetic-only. Production publisher remains unchanged.**

## Why this change

The real v0.18.299 Stage 6 clock-conflict investigation completed (4 cloud calls, 6.4 s), accurately described source-time versus receipt-time, and matched eleven declared source-field values. But Gemma read `S2` and `S3` and spent its last read on unrelated timezone configuration `S5` rather than `S1` (the issuing app's command). It discovered 2/3 reference-relevant sources and left `command_record` uncovered. The v2 source-appraisal envelope was also incomplete. Improving JSON compliance alone does not solve *why* the model judged sources useful.

## Stage 6.5 approach

1. In every synthetic planning round, ask Gemma to preserve the **original investigation question** and identify up to four bounded question IDs `Q1`–`Q4`, including whether each is unresolved, addressed or presently unverifiable.
2. For **every unread source title**, evaluate which question IDs it could inform and its **expected incremental information gain**: `none`, `context`, or `material`. Material evidence is that which could change a conclusion or settle/qualify an unresolved question.
3. Ask Gemma to select a **highest-information-gain** unread source, rather than one that merely confirms the latest event timeline. The host independently checks whether that choice is consistent with the model's **own** rankings. On a self-inconsistent lower-ranked choice, flag `selected_source_below_model_rank`; do not silently replace the source.
4. STOP while a source is explicitly self-rated `material` is rejected—even if other appraisal fields are incomplete. Missing or malformed optional question appraisals remain conspicuously **unaudited**, consistent with Stage 6.4 safe-control separation.
5. Retain the **hidden host source-relevance oracle** for independent *outcome* scoring, separate from the model-supplied source utility. Question statuses and gain rankings are **not** verified facts.

This is a generic information-gain protocol. Neither implementation nor host gate automatically selects lighting logs, S1, room names, app categories or device types, and it does **not** use user-prompt keyword routing.

## New evaluation

Mock regressions reproduce the reported S5-versus-S1 failure:
- Selecting S1 as `material` is self-consistent; choosing S5 as `context` while S1 is `material` is reported as a model-ranking inconsistency and still scores 2/3 reference source recall.
- Incomplete or malformed appraisals cannot become `planning_contract_complete` and do not fabricate a score.
- STOP with a self-identified material source is rejected; unknown sources/actions and unexpected keys still fail closed.
- A 4-call synthetic sequence with S2, S3 and S1 reaches 3/3 reference source discovery and expected finding-type coverage **in the mock**, not as a claim that real Gemma will repeat this result.
- No source-relevance oracle leaks into any model-facing payload.

## Using it

After updating to **v0.18.300**, run **Stage 6 → Delayed OFF report versus device time** once. The existing explicit checkbox authorises up to **four Ollama Cloud requests** from the configured primary account. Review **Question/value audit**, the question-linked ranked sources, model consistency, selected IDs, host reference recall and whether command history was actually examined.

These scores do **not** establish full natural-language factual support or Claude-equivalent reasoning. The host still verifies only declared type/atom citations; implicit narrative claims require human independent review. No live Hubitat or Home Assistant data/commands, synthetic cloud calls in CI, automatic retries, model-routing changes or redesigned publisher activation.

Rollback: revert the Stage 6.5 PR and reinstall v0.18.299 if needed.
