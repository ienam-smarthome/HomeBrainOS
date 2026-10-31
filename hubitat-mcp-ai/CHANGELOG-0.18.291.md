# HomeBrainOS v0.18.291 — Stage 4K matched 3B-vs-7B extraction

**Offline synthetic-only, GitHub-hosted real model comparison. No production changes.**

- Adds `tools/stage4k_github_matched_models.py` and new isolated
  GitHub Actions workflow to compare actual local Qwen2.5 3B and
  Qwen2.5 7B model inference using **identical** Stage 4J system
  prompt, source packets, JSON schema, generation settings, and
  independent reference-scoring rules.
- The matched benchmark includes the 12 Stage 4J constructed
  sentences plus a separately labelled eight-sentence held-out set
  across lighting, heating, ventilation and contact history.
  **40 actual local model calls** are planned, bounded by workflow
  and per-request timeouts.
- Compares per-model and per-corpus missed high-risk implications,
  unwanted extra assertions, precision, recall and invalid
  responses; cannot turn model reviewer votes into source proof.
- Extends the *offline-only* Stage 4J evaluator and local transport
  to accept the exact `qwen2.5:7b` model tag, retaining
  `qwen2.5:3b` as Stage 4J's original CLI default.
- Adds regressions for prompt/schema parity, withheld reference
  labels, tampered cases, invalid inference and aggregate-only logs.
- **Host-curated constructed annotations are not externally
  authenticated human judgments**, and this stage does not score
  newly generated Stage 4G answers or prove arbitrary prose safety.
  The live publisher remains unchanged/default-off for redesigned
  model-authored output.

See `docs/INVESTIGATION-STAGE-4K-MATCHED-MODEL-COMPARISON.md`.
Rollback: revert PR or disable the standalone Stage 4K workflow.
