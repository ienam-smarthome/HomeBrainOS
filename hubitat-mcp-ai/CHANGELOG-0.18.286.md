# HomeBrainOS v0.18.286 — Stage 4F stronger local model evaluation

**Source-only offline GitHub Actions benchmark. No live activation.**

- Adds a new CPU-only, no-cloud, loopback-only GitHub Actions job that
  downloads local Qwen2.5 3B and Llama 3.2 3B model weights, invokes
  two real reviewers over the same eight source-labelled synthetic
  examples used in Stage 4E, and publishes aggregate counts only.
- Removes the previous single `insufficient` schema illustration from
  Stage 4F prompts while retaining the strict Stage 4B cited-source
  validator and model-selected entailment/contradiction/insufficiency.
- Measures **each reviewer's** false acceptance and false rejection
  separately, plus dual-reviewer consensus and disagreement, missing
  responses and schema invalidity; cannot mask one overcautious model
  behind a paired verdict.
- Stage 4E baseline: 16/16 real model calls, eight complete reviewer
  pairs, **0/4 false accepts, 4/4 false rejections** (both tiny models
  rejected every sentence). This remains a fixed historical observation.
- Distinct 3B models and balanced instructions are co-varied; any
  improved result must NOT be solely attributed to model capacity.
- All test data are constructed, no live logs, MCP tools, private
  device IDs, Hubitat/HA credentials, app settings or source timestamps.
- No changes to active investigation planner, original model path,
  publisher, device control or live Home Assistant installation.

See `docs/INVESTIGATION-STAGE-4F-STRONGER-MODEL-EVALUATION.md`.
Rollback: revert this additive PR or disable the Stage 4F workflow.
