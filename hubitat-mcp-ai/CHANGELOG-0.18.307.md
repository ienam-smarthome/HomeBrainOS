# HomeBrainOS v0.18.307 — Stage 7.5 evidence structure versus answer quality

**Experimental synthetic benchmark and mobile review only.** No production publisher, model/provider route, MCP tool, device, or automation changes. No Ollama Cloud inference in CI, no additional calls on a user run.

## Why

The 1 November 2026 Gemma Cloud Stage 7.4 competing-command run correctly described the Inactivity App's OFF, the Button App's later setLevel(40), the final OFF report, and the unproven unique cause. All nine claimed source-value atoms matched. Yet its model-declared type coverage was 2/3 because the final answer did not use the optional `competing_commands` sentence label, despite describing both distinct commands. A type-label score is not the same as the source evidence available or the natural-language answer's quality.

## Changes

- A new isolated `stage75_evidence_answer_review.py` evaluates **host-observable source structure**, independently from the authored sentence labels. It uses the existing trusted fixture source-kind checker and only the records Gemma actually selected. For competing commands, the host sees the distinct app/command pair regardless of whether the model supplied a separate relationship label. These are **evidence structure** scores, not a certified causal finding or a verified free-prose answer.
- Postrun answer-obligation worklist separates reference evidence not inspected, inspected but not cited, partially cited, or entirely cited. These statuses never rate answer completeness: every actual language/omission review defaults to **not reviewed**. Previous Stage 7.2 human controls remain the authority for reviewer findings.
- A typed evidence ladder distinguishes **issued command**, **reported state**, **independent telemetry packet**, **physical acknowledgement** and **command-to-outcome correlation**. Telemetry by itself never establishes which app initiated it. No synthetic fixture authenticates an executed command to a unique physical outcome. The model's next-evidence suggestion is displayed as **not independently validated**, with guidance to seek command-correlated execution receipts or comparable causal evidence.
- Mobile diagnostics rename the legacy finding-type coverage display to **model-declared finding-label coverage (not answer quality)**, and add a collapsible **Stage 7.5 · Source structure vs answer quality** panel. It does not rewrite Gemma's explanation.
- Backward-compatible `homebrain-stage7-review.v1` packet now includes `stage75_evidence_answer_review` alongside previous scope, answer and per-sentence review sections.

## Regressions

Synthetic tests cover the real Stage 7.4 2/3 label versus 3/3 host source scenario, explicit relationship labels, missing acknowledgements, independent telemetry with no established initiator, all three historical benchmark cases, skipped relevant source, fabricated/duplicate selections, contradictory prose, mobile review, four-call mock budget and isolation from production modules.

**Limitations:** Source-type structure is weaker than physical causation, and matched citations/metadata cannot certify natural-language wording. A human must review uncertainty scope, causal claims and omitted question parts. No automatic publication approval.

On-phone follow-up: install **v0.18.307** and run the consented Stage 6 **Two apps issue competing commands** synthetic test once (up to four existing Ollama Cloud calls). Under Stage 7 review, compare host-observable source types with model-declared labels, and judge answer obligations and sentences independently.

Rollback: revert the Stage 7.5 PR and restore v0.18.306.
