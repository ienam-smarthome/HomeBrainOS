# Hubitat MCP AI v0.18.285 — Stage 4E actual GitHub-hosted local model evaluation

**Source-only: NO production model, publisher, MCP or Hubitat/HA changes.**

- Adds `.github/workflows/stage4e-actual-model-evaluation.yml` to
  provision an isolated Ubuntu GitHub-hosted CPU runner with locally
  downloaded Qwen2.5 0.5B and Llama 3.2 1B Ollama models.
- Invokes actual model semantic reviews of **eight constructed source
  scenarios** (16 calls), using Stage 4C's loopback-only adapter.
  Ollama cloud inference is explicitly disabled; the Stage 4E-only
  reviewer uses JSON-schema constrained output (no fabricated verdicts),
  with repository contents READ permission and no secrets.
- Adds `tools/stage4e_github_actual_models.py` to enforce explicit
  synthetic-only acknowledgement, GitHub-only environment, output
  bounds and aggregate GitHub Actions summary.
- Adds tests for fake-transport baseline, reviewer false acceptance,
  no reference-label leakage, zero valid review INCONCLUSIVE status,
  shell workflow security checks and no active publisher imports.
- No live model quality or human/Claude-level reasoning is asserted:
  actual execution and valid outputs must be confirmed from the
  dedicated GitHub Actions run. The tiny models and synthetic cases
  are only an initial diagnostic.
- A workflow that has no complete paired review returns non-success
  instead of inventing a zero error rate.

See `docs/INVESTIGATION-STAGE-4E-GITHUB-MODEL-EVALUATION.md`.
Existing model/tool choices and V3 publisher remain unchanged.
Rollback: revert the additive PR or disable the workflow.
