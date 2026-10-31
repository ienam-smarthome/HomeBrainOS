# Stage 4F — Bigger local-model reasoning benchmark on GitHub

**Repository version:** v0.18.286, based on merged v0.18.285.

## Why Stage 4F

Stage 4E successfully executed two real Ollama reviewer models on an isolated
GitHub-hosted CPU runner. Its final run (Actions #8) invoked all 16 model
calls and obtained eight complete, source-cited reviewer pairs, but both
tiny models rejected every statement — including all four source-supported
sentences. **Consensus false rejection was 4/4 (100%)**, despite zero
false acceptances on the four unsupported sentences.

This is a *usable protocol, unusable judgement threshold* on the small model
pair, not evidence that source facts should be weakened.

## This experiment

A separate `.github/workflows/stage4f-stronger-model-evaluation.yml`
runs **Qwen2.5 3B** and **Llama 3.2 3B** as locally pulled Ollama models.
No dependency on the user's Windows PC. Both are evaluated on the **same**
eight Stage 4C constructed reference cases, preserving the Stage 4E
reference-label split (four supported, four unsupported).

The Stage 4F runner sends the Stage 4B reviewer exactly one sentence and its
cited host facts and *never* the reference label, source case ID or the
other reviewer's answer. It still validates the exact Stage 4B typed
response schema and cited fact IDs.

A potentially misleading example in the earlier Stage 4C
transport had illustrated only an `insufficient` verdict. The Stage 4F
transport uses no sample verdict, adds domain-general balanced instructions
and uses the same JSON-schema-constrained output introduced in Stage 4E.
It explicitly asks the model to accept straightforward facts directly
supported by the source, while refusing causal or physical conclusions
that are not proven. **The prompt does not contain specific benchmark
answers or room-by-room keywords**, and validation is unchanged.

Stage 4F measures:
- per-model structurally valid and invalid responses;
- per-model false acceptance and false rejection against the source reference;
- pair-level unanimous entailment, disagreement and false accept/reject rates;
- requests, model invocation errors, and missing/incomplete reviews.

**A partial review is never counted as correct**; if no complete model
pair is available, the GitHub job exits INCONCLUSIVE, not 0%-errors.

## Explicit limits

- Both model weights are publicly available Ollama 3B variants downloaded
  to an ephemeral GitHub Actions runner. No user credentials or device data
  are used. Ollama cloud inference is disabled, bound to loopback, and no
  publisher/tool/agent code imports this evaluator.
- Eight pre-labelled synthetic statements are *not genuine home incidents*.
  They do not test a model's ability to investigate, select tools, recover
  source event history or author natural-language answers.
- The individual source reference labels are independently written for
  synthetic examples, but are not externally authenticated field truth.
  Two different model tags do not establish independent judgement.
- Stage 4F changes the reviewer models **and** prompt presentation from
  Stage 4E. If quality improves, this experiment alone cannot attribute
  the improvement uniquely to model size or wording. A follow-up
  matched-condition experiment is required for causal attribution.
- The CPU-only model runs can be slow. The job uses a fixed invocation
  budget, explicit timeouts and bounded local output.
- The GitHub job summary and console print **only aggregate counts,
  rates and approved model tags**. No raw user records, model answers,
  prompts, event timestamps, case IDs or exact device identifiers.
- The PR adds a separately scoped workflow. Stage 4E's existing workflow
  and results are retained unchanged for comparison.
- No consent or live installation is needed for these synthetic tests.
  The HA add-on can stay on its installed version; no Hubitat or
  Home Assistant changes are made.

## Rollout and acceptance gate

1. Run the new real-model workflow and all three standard CI workflows
   at the exact PR head. Do not merge on an incomplete or failing run.
2. Review actual model per-sentence aggregate accuracy and full error
   counts; do not hide high false acceptance to improve true acceptance.
3. If acceptable, design separately adjudicated model-authored answers
   and a matched prompt/model ablation. Do not enable the redesigned
   planner or publisher from benchmark scores alone.
4. Explicit owner approval is required for any future live read-only
   collection or published natural-language answer switch.

**Rollback:** revert this additive source PR, or disable only the Stage 4F
workflow. Existing Stage 4E/4D and production code remain untouched.
