# HomeBrainOS V2 — frozen-evidence review-pass experiment

**Date:** 12 November 2026. **Baseline:** alpha.58. **Status:** offline evaluation tooling only; no deployed inference change.

## Why

The user's private alpha.58 first-answer capture for a repeated causal question scored 2/8. Stage tracing showed an unsupported "not Hubitat" conclusion before the source review (3 successful, 1 rejected receipt); the source review obtained one additional successful receipt but retained that overclaim; the final tool-free audit weakened the language but still asserted likely external initiation. Total: 8 model rounds, approximately 18.13 seconds server time. This establishes that this one run's existing reviews did not resolve the causal defect. It does **not** demonstrate multi-pass architecture is universally worse. No private event rows, names, requests, tokens or response prose are copied here.

## Experiment to run, independently of production

1. Assemble at least 12 **new**, diverse, read-only, originally uncoached questions, with exact questions and proof requirements locked before inference. Preserve original successful tool receipts and rejected tool calls **privately**. Keep the repeatedly reviewed light incident as a regression control, not a holdout.
2. Freeze a single evidence bundle for each question, including metadata for source filters, row caps, missing sources and actual receipt errors. Both paired conditions must receive byte-identical evidence. Do not infer missing commands or negative results from unqueried sources.
3. Use the **same model/provider/version/settings** and comparable message context. Randomize/counterbalance condition order and run multiple repetitions. Compare the *single answer* condition with the existing *source review + final audit* condition. Optionally evaluate individual review stages as separate arms in a subsequent study. The evaluator **does not execute model calls** and therefore does not guarantee identical tokens, seeds or model settings.
4. Preserve each completed answer as a private file. Blind human judges to condition labels and score factual grounding, source completeness, causal calibration and usefulness (0/1/2 each; causal N/A only when truly inapplicable). Flag unsupported definite claims, missing necessary discriminating sources, chronology errors and unsupported negatives; preserve positively verified command issuers. Record model rounds, server elapsed, model configuration and read-only safety.
5. Run the **local-only** `hubitat-mcp-ai-v2/evaluation/review_pass_pairs.py` on a private JSON manifest. It validates exact evidence-file SHA-256 agreement for both arms and scores/latency, but cannot judge correctness or cause. It refuses to grade a trial with a reported unexpected write. The resulting summary has opaque case IDs, hashes, human numbers and no answer/evidence text. Keep even this summary private until reviewed for disclosure.
6. Report quality distributions, frequency of unsupported definite conclusions, failed reads and latency. Examine source acquisition *separately*: keeping receipts constant tests answer-revision behaviour, not whether a source-review pass would make better tool choices. If evidence is insufficient, both arms must remain uncertain.
7. Do not change the production agent's default review policy, V1, native MCP, home diagnostics recorder, add-on version or write permissions on the basis of one experiment. Consider stage removal only after independent cross-domain review plus V1/V2 acceptance.

## Minimal private manifest schema

The following is **fictional structure only**; use private locally stored answer/evidence filenames:

```json
{
  "schema": "homebrain-v2-review-pass-pairs.v1",
  "cases": [{
    "id": "synthetic-01",
    "read_only": true,
    "model": "model-version",
    "frozen_evidence_file": "frozen-01.json",
    "arms": [
      {"label":"A","mode":"single_answer","answer_file":"reply-a.json",
       "evidence_sha256":"<sha256 of frozen-01.json>","elapsed_ms":1000,
       "model_rounds":1,"unexpected_write":false,
       "scores":{"factual_grounding":1,"source_completeness":1,
                 "causal_calibration":0,"usefulness":1}},
      {"label":"B","mode":"source_review_and_audit","answer_file":"reply-b.json",
       "evidence_sha256":"<same sha256>","elapsed_ms":2000,
       "model_rounds":3,"unexpected_write":false,
       "scores":{"factual_grounding":2,"source_completeness":1,
                 "causal_calibration":1,"usefulness":2}}
    ]
  }]
}
```

No device writes, cloud-model experiments, private fixture submissions, or claims of improved first-answer quality were part of this PR. CI validates ledger logic only; manual blinded evaluation is still required.
