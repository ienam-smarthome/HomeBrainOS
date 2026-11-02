# Q2 — paired, answer-bound, source-reviewed model comparison

**Status:** offline measurement tool; no claim of real model accuracy until privately retained first-attempt answers are source-reviewed. **Runtime add-on version remains 0.18.371.** No Hubitat/HA, Internet, cloud billing, private-model endpoint or provider secrets are needed to run this comparison script.

## Why an additional gate is necessary

The existing Q1 `answer_quality_fixed_packets.py compare` validates two submitted metadata manifests against the exact frozen *input* packet SHA-256 for the first attempt. The permanent `answer_quality_scorecard.py` grades submitted human reviews, but its review entries are not themselves bound to a specific model answer digest. A reviewer could accidentally score the wrong answer, or a later re-run, without the existing scorecard noticing.

`scripts/answer_quality_paired_reviews.py` adds an **exact answer-SHA join** between both submitted run manifests and the human pair review. It reuses the existing five-dimensional review rubric and scorecard rather than adding a lexical proxy for truth. Reports are only aggregates; no raw answer, token, private event, reviewer name or source log goes into the output.

## Private, offline workflow

1. Choose the **same** frozen packet from `python scripts/answer_quality_comparison_prompt.py --case-id aq_network_broker_vs_device_health`. Record its SHA and send the identical prompt to two actual models on their explicitly configured provider transports. Keep identical tool policy, generation budget and settings, and disclose provider/model/build, wall time and cost privately. Do not quietly retry failures and call the retry the first attempt. No cloud API is called by these scripts.
2. Retain the model's exact first answer privately. Compute `sha256(UTF-8 raw response text)` and place only the digest, exact packet SHA, model, provider, build SHA, first-attempt index (1) and recorded wall latency in two **private** `homebrain-answer-quality-offline-run.v1` metadata files. The current metadata schema does **not** attest generation temperature, seed, runtime provider bills, transport trace or actual prompt delivery; record those outside the public manifest.
3. Privately source-review both exact answers against the full frozen available-evidence packet, using `required_findings` and `forbidden_claims` as reviewer obligations only (never show these to the models). Complete `grounding`, `causal_calibration`, `useful_first_attempt`, `clarity`, `safety`, grounded/evaluated factual conclusion counts, and unsupported definitive causal claim count. Do not grade fictional evidence as live home observations.
4. Bind each review to its **exact answer digest** and a SHA-256 of the supporting private evidence packet/review trace. Use a short pseudonym (not a real person's name) as reviewer. If blinded grading was actually performed, keep its separate private mapping; this script **does not claim or independently verify blinding**. The reviewer manifest must contain **only** metadata and rubric fields.
5. Run `python scripts/answer_quality_paired_reviews.py --baseline /private/base.json --candidate /private/alt.json --reviews /private/reviews.json --output /private/report.json`. This rejects unpaired, changed source packets, late retries, answer-hash mismatches, mixed undisclosed arm identities, malformed rubric rows and attempts to embed private prose. Only successfully matched, personally reviewed pairs enter the displayed percentages.

## Example review input shape — fictitious hashes only

```json
{
  "schema": "homebrain-answer-quality-paired-reviews.v1",
  "pairs": [
    {
      "case_id": "aq_network_broker_vs_device_health",
      "baseline_answer_sha256": "<64-lowercase-hex-of-exact-first-answer>",
      "candidate_answer_sha256": "<64-lowercase-hex-of-exact-first-answer>",
      "reviewer": "reviewer-pseudonym",
      "evidence_reference_sha256": "<64-lowercase-hex-of-private-source-review>",
      "baseline_review": {
        "grounding": "pass",
        "causal_calibration": "pass",
        "useful_first_attempt": "pass",
        "clarity": "pass",
        "safety": "pass",
        "grounded_factual_conclusions": 3,
        "factual_conclusions_evaluated": 3,
        "unsupported_definitive_causal_claims": 0
      },
      "candidate_review": {
        "grounding": "partial",
        "causal_calibration": "fail",
        "useful_first_attempt": "fail",
        "clarity": "pass",
        "safety": "pass",
        "grounded_factual_conclusions": 2,
        "factual_conclusions_evaluated": 3,
        "unsupported_definitive_causal_claims": 1
      }
    }
  ]
}
```

Angle-bracket placeholders above are **not valid input**; enter actual SHA-256 digests, not private text or guessed hashes. This example is instructional, not a real scored result.

## Honest measurement contract

- With **no reviewed pairs**, `measurement_status=not_measured` and both scorecard result objects are `null`.
- With submitted human reviewed pairs, `human_review_sample_reported` shows explicitly which cases and denominators were reviewed, first-useful wins/losses/ties, source-grounded percentages and unsupported causal counts. **Submitted grades are not independently authenticated by the tool.**
- Every model/provider/build must be stable within one arm; the two arms must differ. Both model answers must identify the same original source packet and first attempt, not merely the same question theme.
- Even a full 40-case curated review is **not** the complete Q4 gate: 13 legacy live tasks remain, production HomeBrain publisher/runtime is not invoked by this offline tool, and real transport delivery, bills and blinded reviewer independence are unverified.
- CI uses synthetic fixtures only to test validation, never invents a real reviewer or awards benchmark accuracy. `acceptance_gate_passed=false` is intentional.
- Cost and provider settings remain a **separate disclosed requirement**, not guessed from model tag or network status. Do not invoke Gemma/Ollama Cloud automatically: any nonzero spend must be explicitly authorised.

## Next practical comparison

Use an initial small, balanced sample across light-command provenance, heating, MQTT broker/endpoint freshness and Rule Machine missing native identity. Freeze the same model-visible source packet for both and preserve the first response in private storage. When consented actual model runs and human-source reviews exist, use this tool to calculate a defensible paired comparison; do not claim it is available merely because the CLI and CI pass. Continue Q3 only after assessing actual qualitative results and latency.
