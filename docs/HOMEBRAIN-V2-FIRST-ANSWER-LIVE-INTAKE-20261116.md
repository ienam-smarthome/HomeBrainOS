# HomeBrainOS V2 — benchmark-first live capture intake

**Status:** development candidate (CI pending). This is an offline benchmark
utility only. No V2 app version bump, model prompt, causal publication gate,
native tool, scheduled task, live Hubitat action or provider change.

## Why

The fixed **53-case** answer-quality inventory already exists: 13 legacy
golden tasks and 40 synthetic/anonymized curated source-packet tasks.
The scorer (`scripts/answer_quality_scorecard.py`) already requires
independent human grading before assigning any quality value. The V2 first-
answer auditor (`hubitat-mcp-ai-v2/tools/first_answer_audit.py`) already
describes native receipts without reproducing private device/source content.

The missing operational bridge is from a user's **original PRIVATE V2
Technical JSON first answer** to a **specific, uncoached, frozen LIVE
question** and an ungraded review template. We must not treat
identically-worded synthetic prompts as matching the *same* live evidence,
score by model lexical matching, reuse prior conversation receipts, or
cherry-pick the second attempt when the first failed.

## Offline intake workflow

1. Pick one of the 13 legacy live task prompts verbatim from
   `tests/fixtures/homebrain_golden_tasks_v1.json`. For example the
   **read-only** `causal_light2_off` task:
   `Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.`
2. In installed V2 Preview start a NEW conversation, ask the exact prompt
   with no coaching and save the **first** response via **Copy for review
   Technical JSON**. Save the original unmodified JSON in a private folder.
   Preserve failures and incomplete answers too. Do not publish that file
   or put it in GitHub, CI, or public storage.
3. On a trusted machine with the repository, run:

   ```bash
   python scripts/first_answer_live_intake.py /private/original-answer.json \
     --build-sha ACTUAL_40_CHAR_GIT_COMMIT \
     --output /private/human-review-draft.json
   ```

   `--build-sha` is optional, but if omitted a human must fill it before
   scoring. Never infer the build commit from the UI's alpha version string.
   Multiple original exports can be supplied; duplicate case/model/build
   pairs are rejected instead of selecting the favourable answer.
4. The new file is created with owner-only permissions on POSIX, fails
   rather than overwriting an existing review, and includes only an exact
   case ID, model/build for private local use, SHA-256 references to the
   original file and question, bounded source-attempt counts, model rounds,
   elapsed time and **null human-review fields**. No question, answer,
   private event row, tool argument, device ID or log message is copied.
   This remains private because the model name and capture hashes may be
   sensitive in context.
5. Read the ORIGINAL answer and exact original successful receipts. The
   reviewer must determine output identity, observation vs command,
   app decision, time-window coverage, unsupported definitive causes,
   useful answer and safety. Fill the output's `reviewer`, actual
   `build_sha` (if missing), five
   `pass/partial/fail` review fields, and three nonnegative factual/causal
   claim counters. Do not fill automatically from receipts or model prose.
6. Only AFTER review, run:

   ```bash
   python scripts/answer_quality_scorecard.py \
     --reviews /private/human-review-draft.json \
     --output /private/scorecard.json
   ```

   The scorer **rejects the draft until graded**; its model/build subset
   is labelled `insufficient_case_coverage` until the frozen evaluation
   set is actually reviewed. Green CI and one good answer are not an
   accuracy score or production acceptance.

## Important constraints

- This LIVE intake deliberately rejects the 40 curated offline packet
  prompts. Evaluate them separately on their fixed source packets using
  existing frozen-source evaluation and review tooling. A live question
  with the same text does not prove that the returned evidence is the
  curated packet.
- Any legacy case with `read_only=false` is excluded from live intake;
  write tasks require isolated mocked execution and explicit safety
  review. Native write/unknown tool attempts in a capture also fail closed.
- A capture with nonzero prior receipts or prior sources is excluded.
  Reported zero prior evidence does not independently prove that the
  browser session was new; the reviewer must confirm this.
- A positive tool result is NOT proof of a full historical window, correct
  causal interpretation or a physically executed command. The tool
  records source categories and counts, not factual grading.
- The tool has no network, MCP client, database, cloud model, scheduler
  or automatic rating. The 53-case fixture files and V2 runtime remain
  unchanged. Synthetic unit tests alone cannot establish real first-answer
  accuracy, model parity, privacy of a public file upload, or a device
  permission guarantee.

## Next measurement

Run multiple genuinely independent, uncoached first attempts across
lighting, heating, status/health and offline-device domains, with matched
source scopes and the actual installed SHA/model noted. Record *all*
attempts including failures; manually review and compare models only on
matched tasks. Only resume structured-claim/prose-gate or controller
role-graph changes after their baseline and before/after quality effect
can be measured across independent source-real cases.
