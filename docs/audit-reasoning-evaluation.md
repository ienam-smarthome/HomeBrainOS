# Paired HomeBrain (Gemma) vs Claude audit reasoning evaluation

## Purpose

Assess the **quality of the reasoning**, not whether routing succeeds, a model
returns words, or the deterministic System Check is complete.

A model call with ai_analysis.status=completed only proves a non-empty advisory
was accepted by the running HomeBrain build. It does **not** establish that the
advice was accurate, sufficiently analytical, or equivalent to Claude.

This is a local/offline test fixture and read-only evaluator. It does not
connect to Hubitat, Ollama or Claude, spend API credit, or change devices.

## Fair comparison procedure

1. Use the synthetic, non-secret cases in
   tests/fixtures/audit_reasoning_benchmark.json.
2. For **both** models supply only each case's prompt and evidence fields.
   Do not supply the expected indicator checks or potential_overclaims: those
   are grading hints, not part of the evidence given to the model.
3. Ask each model to answer without tools, browsing, memory or prior chat context.
   Keep inference settings, available time and answer-length target comparable.
4. Save the exact resulting **model-authored** answer. For Gemma, if copying the
   whole HomeBrain API response, the evaluator extracts only text under
   "### Reasoned answer" and ignores the deterministic report.
5. Repeat with multiple runs if models are stochastic; compare median/manual
   performance rather than one lucky response. Preserve model name/version,
   date, decoding parameters and elapsed time alongside results.
6. Run the indicator checker. Then manually review its findings: keyword
   presence is neither evidence of factual accuracy nor reasoning quality.

Model submission file JSON example (keys must match the case IDs):

    {
      "hub_overload": {"answer": "PASTE MODEL-ONLY TEXT HERE"},
      "tv_pairing": {"answer": "PASTE MODEL-ONLY TEXT HERE"},
      "rule_lockout": {"answer": "PASTE MODEL-ONLY TEXT HERE"}
    }

A full HomeBrain API response can be used instead of an answer entry:

    {
      "tv_pairing": {
        "ai_analysis": {"status": "completed"},
        "message": "### Reasoned answer (AI interpretation; not independent evidence)\nMODEL TEXT\n\n### Coverage\nHOST REPORT TEXT"
      }
    }

A missing advisory or ai_analysis.status other than completed produces
**not-produced/disabled/timed-out** status, not a zero-quality model verdict
based on the host's text.

Run from the repository root:

    python scripts/evaluate_audit_reasoning.py \
      --benchmark tests/fixtures/audit_reasoning_benchmark.json \
      --gemma gemma-answers.json --claude claude-answers.json

Output is a set of **lexical indicators** found or missing in the independent
model text, with candidate overclaims requiring manual inspection.
Negations and quotes can trigger warning strings, so never auto-fail on a
potential-overclaim substring.

## Manual rubric (0-3 points per dimension, per case)

- **Direct answer:** 0 = no answer; 1 = generic checklist; 2 = relevant but
  incomplete; 3 = directly resolves the user's question within evidence bounds.
- **Evidence selection and prioritisation:** 0 = invented or irrelevant;
  1 = raw data dump; 2 = grounded but weak ranking; 3 = strongest observed
  evidence selected and competing signals weighted fairly.
- **Causal/temporal reasoning:** 0 = invented cause or chronology;
  1 = pure coincidence asserted; 2 = cautiously distinguishes correlation;
  3 = evaluates competing hypotheses and discriminating observations.
- **Uncertainty calibration:** 0 = unsupported certainty; 1 = generic
  disclaimer; 2 = facts versus hypotheses separated; 3 = precise source
  limits, observed-versus-inferred status, and justified confidence.
- **Useful safe next check:** 0 = unsupported mutation or hazardous change;
  1 = broad "check everything"; 2 = relevant read-only check;
  3 = one targeted, falsifiable, read-only discriminator.

Keep side-by-side notes for **which concrete inference was better and why**;
do not describe a model as "Claude-equivalent" from indicator coverage or
three synthetic cases alone. Failures of factual correctness or safety must
be discussed independently of points.

## Suggested follow-up with real HomeBrainOS v0.18.80

Install v0.18.80 and explicitly verify the saved
comprehensive_audit_ai_analysis_enabled setting is true. Submit the established
read-only comprehensive audit query. Check route, ai_analysis.status and
optional_ai_advisory receipt; collect the model-only advisory and independently
record the full host evidence. Compare the same *redacted, time-bounded*
evidence with Claude. Do not paste API keys, private endpoint URLs, or raw
personal location/household information into public issues or fixtures.

Current benchmark fixture is synthetic and does not prove live Hubitat or
model results. No paid model is enabled by this procedure.
