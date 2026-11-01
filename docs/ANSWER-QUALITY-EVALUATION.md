# Answer Quality v1 — running a fair evaluation

Read [the permanent charter](ANSWER-QUALITY-CHARTER.md) and [live status](ANSWER-QUALITY-STATUS.md) first. This guide is for humans and future ChatGPT sessions.

## What currently exists

- The prior `tests/fixtures/homebrain_golden_tasks_v1.json` has 13 target tasks, some still requiring live evidence capture.
- New `tests/fixtures/answer_quality_cases_v1.json` has **18 synthetic/anonymised source packets**, each with a question, facts available to the model and private grading obligations.
- **31 defined cases is not 31 model runs, 31 source-verified answers, a 31-case replay system or a Claude score.**
- `scripts/answer_quality_scorecard.py` measures **human-reviewed** answers only, never predicts performance or calls Ollama. Initially it reports `measurement_status=not_measured`.

## Q1: fixed offline packet replay, without a model call

The 18 curated synthetic/anonymised source packets can now be exported as **hash-pinned, model-facing inputs**. This is a reproducible offline comparison *input*, not a record of 18 model runs, a production benchmark or a source-truth certification.

```bash
# Exports all 18 packets as JSONL, with stable SHA-256 fingerprints.
python scripts/answer_quality_fixed_packets.py export --output /private/fixed-q1.jsonl

# Or export one fixed case for a controlled model evaluation.
python scripts/answer_quality_fixed_packets.py export \
  --case-id aq_network_broker_vs_device_health \
  --output /private/network-q1.jsonl
```

Each JSONL row contains the **unchanged case question and evidence**, a `no-tools` offline policy, its case ID and an input fingerprint. It **does not** expose `required_findings`, `forbidden_claims` or earlier review grades to the model. Keep model prompt delivery, provider/model/version/settings, token budget and review rubric identical for a before/after pair. Never substitute a newer live history for a frozen packet.

Once **actual** model runs exist, create **private metadata-only** JSON for each side with `schema=homebrain-answer-quality-offline-run.v1`, and a `runs` array. Each run must contain exactly `case_id`, `packet_sha256`, `answer_sha256`, `model`, `provider`, `build_sha` (full 40-character Git SHA), `attempt_index=1` and observed `elapsed_ms`. The answer, tool traces and any sensitive source data stay separately in the private review. The supplied commit SHA must be **independently authenticated** to the deployed code; a syntactically valid SHA alone does not prove this.

```bash
python scripts/answer_quality_fixed_packets.py compare \
  --baseline /private/baseline-run-metadata.json \
  --candidate /private/candidate-run-metadata.json \
  --output /private/q1-pair-preflight.json
```

The comparison preflight verifies matching frozen packet hashes and first-attempt metadata, and reports matched/unmatched cases. It does **not** call Ollama, grade responses, certify real model-input delivery, confirm deployed hashes, or produce a success percentage. A valid metadata pair only becomes eligible for the **separate human/source-reviewed scorecard** after the identical question/evidence contract, first-attempt status and provenance are independently confirmed. Without run records, the result is `not_measured`. The 13 legacy live/control cases are **not** silently reclassified as offline evidence packets.

## Safe operator workflow (user should only need to provide HomeBrain Q&A)

1. Pick the next `capture_required` legacy case or a curated question; give the user **one copyable read-only test prompt** with the necessary device IDs/time window and ask for HomeBrain's natural-language answer **and its complete technical evidence JSON**.
2. Review the specific trace against its source receipts and expected evidence. Separately grade grounding, causal calibration, useful first response, clarity and safety as `pass`, `partial` or `fail`. Judge *factual conclusions*, not simply the presence of keywords. Record any unsupported definitive causal claims.
3. Save a **redacted** reference to the evidence/answer in the review; never put private raw source logs, credentials, local-network URLs or sensitive household data into a public GitHub fixture.
4. Run the unchanged question and source packet on `main` and candidate build. Keep model/provider, prompt, scope, permitted tool surface and evaluation criteria fixed. Reviewers should be blind to the model where practical.
5. Run the scorecard. Compare measured sample size, grounded claims, first-attempt usefulness, overclaims, safety and latency. Reject improvements that merely make an answer sound more confident or add redundant tool calls.
6. Once a meaningful before/after effect is demonstrated, update the [status](ANSWER-QUALITY-STATUS.md), CI/PR and next action. This becomes the next chat's starting point.

## Q1: privacy-minimal HomeBrain live capture

The HomeBrain technical JSON includes actual device labels, IP addresses, command arguments, event payloads and potentially private logs. **Do not commit unredacted output to public GitHub**.

After a user supplies the complete HomeBrain JSON in a private conversation, the assistant can review the source evidence in that conversation. For local reproducibility, the `scripts/answer_quality_capture.py` extractor records hashes, timing, receipt counts and a **strictly allowlisted** summary of HomeBrain's self-reported missing-source categories. It omits unknown/private gap labels and records only their count. The extraction reads HomeBrain's production `investigation_coverage.sourceCoverage.missingSourceKinds` structure and accepts a legacy top-level field; conflicting reports fail closed. `source_gap_reporting=not_provided` is different from a reported empty list; even a reported empty list leaves `source_packet_completeness=not_independently_verified`. Other self-reported indicators (`evidenceComplete`, `sourceChecksComplete`, `sourceKindsChecked`, source-integrity warning count and synthesis-repair failure count) are retained as bounded diagnostic metadata, not proof of root-cause resolution. These metadata are **not** a source-completeness verdict, factual grade, or proof of physical action.

```bash
python scripts/answer_quality_capture.py \
  --case-id causal_light2_off \
  --input /private/homebrain-answer.json \
  --question-file /private/exact-question.txt \
  --output /private/ungraded-capture.json
```

The script **does not grade** correctness, quote private answer text, include raw tool responses, prove device safety, or claim a full-source replay. Its `prompt_match=exact` means only that the submitted question matches the registered *live* task question; synthetic curated cases are not live-replay equivalent simply because their words match. Review the technical response separately and label all conclusions supported, unsupported or unverified.

For the first current-build capture, use the registered `causal_light2_off` question **verbatim**:

> Investigate why Livingroom Light 2 turned OFF most recently. Do not change anything.

The older observed Gemma reasoning failures are documented in [Q1 retrospective](ANSWER-QUALITY-Q1-RETROSPECTIVE.md). They are not scored as a frozen before/after benchmark.

## Scorecard commands

```bash
# At kickoff: intentional honest empty scorecard
python scripts/answer_quality_scorecard.py

# After reviews exist: no Internet/Hubitat/Cloud calls
python scripts/answer_quality_scorecard.py --reviews path/to/redacted-reviews.json --output quality-scorecard.json
```

A review file must have the following structure (illustrative schema **only; not real scores**):

```json
{
  "schema": "homebrain-answer-quality-reviews.v1",
  "reviews": [
    {
      "case_id": "aq_repeated_input_delay",
      "model": "model@version",
      "build_sha": "actual-verified-git-sha",
      "reviewer": "human-reviewer",
      "evidence_reference": "anonymized-review-or-private-trace-reference",
      "review": {
        "grounding": "partial",
        "causal_calibration": "pass",
        "useful_first_attempt": "partial",
        "clarity": "pass",
        "safety": "pass",
        "factual_conclusions_evaluated": 4,
        "grounded_factual_conclusions": 3,
        "unsupported_definitive_causal_claims": 0
      },
      "metrics": {
        "latency_seconds": 43.2,
        "tool_calls": 12
      }
    }
  ]
}
```

The numeric values above are **fake examples to illustrate field types**, not the actual user's baseline or a validated HomeBrain measurement. Do not commit fake reviews as real evidence.

## How to interpret the scorecard

- `not_measured`: no human-reviewed results. Not zero defects, not failure and not success.
- `measured_review_sample`: only the submitted model/build/case observations are scored. They are not automatically source-certified by the script.
- `acceptance_status=insufficient_case_coverage`: reported rates are descriptive **sample results**, and all acceptance-target boolean fields are `null`.
- `acceptance_status=full_reviewed_case_set`: every registered case has a review for that exact model/build, so **some** full-case targets may be evaluated. The user still needs representative real-device and multiple-run testing for production claims.
- Quality rate uses the number of **reviewed factual conclusions** as denominator. First-attempt usefulness uses reviewed cases, counting only a `pass` as success. `partial` is not counted as a pass.
- The numbers do not prove Claude parity without properly paired Claude-source answers on the same evidence.
- Latency values must come from actual wall-clock/trace measurements and must not be estimated. Compare median and p95 separately for quick status/control versus complex investigations when sufficient samples exist.

## Anti-overfitting checklist

Before proposing any code change, write down:
- Which failure pattern is cross-domain? Where does it occur outside the user's latest example?
- What source fact was missing or misread? Would an evidence-format/identity/timing improvement solve a class of cases?
- Which untouched negative/alternative cases must still pass?
- Did the change improve **the same test answers**, or merely add a post-hoc sentence?
- Does it increase model rounds, Cloud cost, number of MCP reads or response time?
- If improvement is absent, can the change be removed instead of adding another rule?

## Live acceptance (after offline evaluation)

The user has authorised **development and read-only test questions**; that is not permission for autonomous device commands, thermostat changes, rule edits or live experiments affecting the home. Always request explicit approval for any such operation.

For a new session, read `AGENTS.md` and `docs/ANSWER-QUALITY-STATUS.md`, then proceed with the next milestone. Do not ask the user to repeat this strategy.
