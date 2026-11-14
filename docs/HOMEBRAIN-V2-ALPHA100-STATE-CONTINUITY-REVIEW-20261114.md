# HomeBrainOS V2 alpha.100 — historical continuity review eligibility

**Date:** 14 November 2026. **Scope:** V2 Preview only. No private household MCP receipts, device-specific names, or live hub calls committed.

## Source-real evidence and failure boundary

An owner-provided installed alpha.99 first answer asked whether a read-only target had remained in the same reported switch state during the previous four hours. The model queried current inventory and a native `switch`-attribute-filtered four-hour event history. That source returned **zero matching rows** and explicitly warned against inferring uninterrupted state, full requested-window coverage or absence of unseen commands. The model correctly concluded that uninterrupted state was not established, but it made overbroad statements such as no switch commands/events were *recorded* when only a filtered query had returned zero rows. The response finished in three model rounds, ~9.6 seconds, with two successful native reads, zero recorded writes, and **both** `source_review_invoked=false` and `final_claim_audit_invoked=false`.

Alpha.99 had fixed an omission of the source's explicit negative coverage flags in the existing **final audit**. The final audit was not reached in this question, so that code change could not be evaluated by this real result.

## Root cause in V2 review eligibility

The historical-measurement classifier understood explicit historical *reporting* requests, not time-bounded *continuity* questions written as “Did/Was/Has … remain/stay … throughout/continuously”. It also accepted digits in a past/last duration more reliably than ordinary number words. The question did not meet the causal-intent trigger. Consequently the existing optional historical source-review and final-audit stages were never eligible.

## Bounded general improvement

- Add a narrow **read-only historical-state continuity intent** recogniser: question-style read starts, state/connection/operation terminology, persistence/whole-interval framing, and a concrete historic window must **all** be present. Extend historic duration parsing to common word numbers, `since HH:MM`, and whole-night/day idioms. Exclude imperative writes, current-state snapshots, unrelated small talk and untimed questions.
- Route this recognised question family to the **existing** `historical_measurement` model-led source-sufficiency review. Do not introduce a separate persistence model, new special-case answer wording, proof inference, source list, deterministic device plan, mandatory monitoring read or unconditional polling.
- An eligible question can now invoke the **existing optional source review and then existing tool-free final audit**, if the request has sufficient remaining time, suitable read-only tools are available and review has not already run. This can **increase model rounds, token use and latency for those eligible questions**. No extra model stage is created, and other tasks' review policy is unchanged. No additional native history call is automatically executed; the model may independently choose a proportionate read-only tool.
- Native MCP schemas/permissions, user approval safeguards, cloud consent and provider selection, original receipts, error labels, V1 and hub configuration remain unchanged.

## Fictional regression tests

Tests cover diverse thermal, lighting, switch, connectivity and motion questions with numerals/word-number periods and since-clock windows; negative controls for imperative writes, ordinary current-state and non-home casual questions; low-time/no-read-tool/already-reviewed restrictions; and a scripted existing-agent execution with exactly two *model-selected* native reads, a model-led review, a tool-free final audit seeing the original source's negative coverage proof flags, and no extra or write tool dispatched. The scripted model's correction is a fixture, not proof of live model intelligence.

## Acceptance and honest limits

Require exact final-head V2 pilot tests, full Python suite, container/smoke, UI fixtures, metadata and repository validation, then post-merge checks. No live hub or paid model is contacted during CI.

After operator-confirmed hub stability, install Preview alpha.100 and use a **new, independent, uncoached, read-only continuity question**. Retain PRIVATE original successful MCP receipts; verify whether source review and final audit were actually invoked and whether the model correctly scopes negative event claims and distinguishes returned rows from all recorded events. Record total model rounds, tokens, elapsed time, whether the Monitor was really queried, and zero writes. Alpha.99's test remains evidence of the eligibility failure, not an independent before/after accuracy score.

If the model still overclaims despite receiving exact coverage flags in the actual final-audit round, use controlled model comparison or structured source-to-claim validation instead of adding more topic-specific prompt patches. Review whether additional tokens/latency justify the eligible review lifecycle before any broadening.
