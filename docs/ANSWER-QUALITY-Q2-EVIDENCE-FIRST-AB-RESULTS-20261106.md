# Q2 evidence-first prompt A/B — actual isolated local trial (6 November 2026)

**State:** Experiment code green-merged in [PR #1467](https://github.com/ienam-smarthome/HomeBrainOS/pull/1467), merge commit `a6c87abdfefedc6e357a77d5bbbb96186c85ca16`.
**Exact tested PR head:** `d7334993d5cbbde5538ffe7fc7020f724504360d`.
**Actual trial:** [GitHub Actions run 42234238612](https://github.com/ienam-smarthome/HomeBrainOS/actions/runs/42234238612).
**CI:** 8/8 successful exact-head checks, including full Python, offline scorecard, repository metadata, two validation jobs, general tests, add-on smoke and isolated model A/B.

## Pre-registered comparison

The baseline was the existing unchanged `render_comparison_prompt`; the candidate was the single model-neutral `render_evidence_first_prompt`. All 40 frozen case source/question bodies matched byte-for-byte between the two prompt renderings in tests. The actual run covered the same **four** selected synthetic/anonymised cases with **two tiny local calibration models** (`qwen2.5:0.5b`, `llama3.2:1b`).

Within each model/source case, both prompt arms used the same requested `temperature=0`, `seed=7`, `num_ctx=4096` and `num_predict=320`. The trial alternated order between model and case, sent each arm **once with no automatic retry**, and used a no-cloud loopback Ollama server isolated from Hubitat, Home Assistant and user records.

## Actual observed model-request wall times

| Frozen source | Qwen baseline | Qwen candidate | Llama baseline | Llama candidate |
| --- | ---: | ---: | ---: | ---: |
| OFF issuer vs reporter | 2,265 ms | 1,609 ms | 3,183 ms | 6,576 ms |
| Early heating OFF | 1,372 ms | 1,292 ms | 2,562 ms | 3,718 ms |
| MQTT endpoint freshness | 973 ms | 931 ms | 2,919 ms | 3,588 ms |
| Native Rule Machine identity | 740 ms | 763 ms | 2,684 ms | 5,460 ms |

- **16/16 requests returned nonempty model text** under the runner's bounded response check. The output did not independently attest Ollama's final stop reason, so do not claim verified full-length semantic completeness.
- Candidate was faster for **Qwen 3/4** source cases (median paired candidate minus baseline **−61 ms**) and for **Llama 0/4** (median paired difference **+1,966 ms**).
- The combined **eight** matched model/source differences had candidate faster in **3/8**, median **+346 ms**. This pooled time is descriptive only; model-specific results are more interpretable.
- On **two Qwen cases (MQTT and native parent)** candidate and baseline answer SHA-256 values were identical despite distinct instruction prompt hashes. The other six pairs had differing output digests. An output hash difference or length difference is **not a factual correctness grade**.

No response prose was printed, saved to artifacts or available to a reviewer. GitHub runner time and model warm-start effects were not independently measured beyond each single request. One trial on tiny local models is not production HomeBrain latency, a reproducible p95, or an assessment of `gemma4:31b`.

## Decision and evidence boundary

**Keep the candidate offline and unpromoted.** It has not demonstrated semantic noninferiority or improvement, and its extra instructions incurred an observed latency penalty for all four Llama samples. There is no reason to edit the production model prompt or add more incident-specific publication handling based on these observations.

**Semantic grounding, first-answer usefulness, causal correctness, natural clarity, safety of generated prose and Claude comparison: NOT MEASURED.** The original historical Qwen 3.5 4B vs Llama 3.2 3B capture study is separate; do not pool those different model sizes, dates, checkout SHAs and prompt contracts with this trial. Formal Q4 scorecard remains without independently authenticated source-reviewed grades.

The project should next obtain privately retained, answer-SHA-bound, source-reviewed *same-model and same-source* prompt outputs when possible, rather than repeating opaque first-answer trials or treating faster generation as better reasoning. If original answer texts cannot be reviewed within the allowed privacy boundary, explicitly keep Q2 accuracy unmeasured and do not promote the candidate.

No production code, installed add-on, device, rule, router or Home Assistant state was modified by this benchmark. No paid Cloud inference was requested; GitHub runner infrastructure minutes are unmeasured. Roll back the optional prompt/runner independently if maintenance cost is not justified by a later real quality gain.
