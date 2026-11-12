# HomeBrainOS V2 alpha.61 — Manual claim-delta assessment on mobile

**Date:** 12 November 2026 | **Scope:** Opt-in V2 AI Evaluation only

## Motivation

The original V1-versus-V2 tests measure complete-agent first-answer competence.
The frozen-receipt V2-only test (alpha.59/60) measures whether revision of the
*same original draft from the same evidence* adds value. The new test is not a
substitute for end-to-end tool choice, missing-source discovery or safe actions.

Cross-domain human reviews of five separate cases (causal lighting, heating
history, freezer power, hub reboots and native rules) revealed mixed results:
reviews sometimes corrected overly broad negative claims, but sometimes
introduced them, lost critical source-scope qualifiers or failed to correct
unsupported causal inferences. These five selected cases are illustrative, not
a representative statistical comparison.

The meaningful experimental measure is now **human-verified claim changes**
alongside human score changes and extra time, not merely different wording.

## New optional phone worksheet

On the existing **AI Evaluation** tab, first run an explicitly consented
frozen-receipt replay. This returns three completed stages from a shared first
draft, with no MCP calls. Under the answers:

- Expand **Original MCP receipts · private source evidence** to check the exact
  successful reads, errors, filters, time bounds, reported issuers and rows.
  It renders the original JSON as text, never HTML. It makes no new read.
- Classify the case as a fresh independent question, prior regression control,
  or unclassified. This is **self-reported**, not a provable randomization label.
- Enter four human 0/1/2 grades for each of the three answer stages:
  factual grounding, source completeness, causal calibration and usefulness.
  Causal N/A is permitted only when consistently inapplicable to all stages.
- Optionally document each **specific claim transition** from initial answer
  to source review or source review to final audit, with a human-selected
  category and a reference into the original receipt evidence. The categories
  include introduced/corrected unsupported assertions, supported facts
  lost/recovered, scope changes and wording-only edits.
- View initial/review/final total scores and final-minus-initial score delta
  alongside additional model time. The UI labels the scores as manual and
  never calls them independently verified.
- Download **PRIVATE-homebrain-v2-reviewed.json**, containing the original
  evaluation response plus the optional manual grades, evidence SHA and notes.
  This file is private and **must not** be committed to GitHub.

The original unscored export remains available. A blank claim-delta list
means **not assessed**, not "zero regressions observed". A partially completed
form disables the scored export. Ratings and notes exist in the current browser
tab only; no server database, cloud scoring endpoint or persistence is added.

## Offline validation and aggregation

The pure Python file
\`hubitat-mcp-ai-v2/evaluation/claim_delta_review.py\` validates reviewed
exports without calling models, devices, cloud services or MCP. It rejects
misaligned evidence fingerprints, missing grades, inconsistent causal N/A,
non-monotonic cumulative times, unanchored claim annotations, non-tool-free
replays and duplicate evidence hashes counted as independent cases.
Its console output contains only hashes, score totals, human-labelled claim
change counts, review overhead and case roles—not source/claim prose.

Example (OPTIONAL, no PC needed to use mobile review):
\`\`\`
python hubitat-mcp-ai-v2/evaluation/claim_delta_review.py PRIVATE-case1-reviewed.json PRIVATE-case2-reviewed.json
\`\`\`

## Interpretation

This worksheet is **not blinded**: reviewers see which answer is initial and
which is revised. It is a practical in-browser audit, not proof that a change
improves correctness. For an unbiased architecture choice, continue using the
existing private blinded A/B ledger \`evaluation/review_pass_pairs.py\`,
matched evidence, fresh independent questions, representative domain coverage
and repeat models/runs. Raw scores can be compared, but human labels must be
verified against the original receipts before conclusions are claimed.

Specifically, if source selection is wrong in the live investigation, frozen
review cannot repair it by querying an omitted source. Evaluate retrieval and
text revision separately. No incident-specific patches, automatic correctness
scores or deterministic causal rules are introduced.

## Safety, impact and acceptance

- V2 normal Ask/Chat, existing prompts and review stages are unchanged.
- V1 and independent Hub & Device Monitor recording are unchanged.
- No new route, write action, storage, model invocation or network call.
- UI remains optional; only the already existing replay requires explicit
  per-run provider transmission consent.
- The rubric is for **human judgement**, not an autonomous LLM grader.

Merge only after repository validation, V2 pilot tests, full Python test suite
and addon container smoke test are green. A green CI proves packaging and
synthetic contracts, not accuracy against the user's live private system.
