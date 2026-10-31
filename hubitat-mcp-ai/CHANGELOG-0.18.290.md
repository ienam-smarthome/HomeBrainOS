# HomeBrainOS v0.18.290 — Stage 4J prose-to-atom completeness evaluation

**Source-only and offline. No live HomeBrain, Hubitat or Home Assistant changes.**

- Adds `stage4_prose_atom_coverage.py`: independent comparison
  between model-proposed factual implications of a whole sentence
  and withheld, separately curated atomic reference labels.
  Tracks omissions of unsupported physical, causal, event-absence
  and completeness claims, not just correctly cited source facts.
- Each extracted atomic assertion is checked by the **Stage 4I
  host-owned proof validator**, not accepted because the model
  (or two reviewers) says it is true. Model-extracted atomic
  propositions do not supply their own trusted witness values.
- Adds actual Qwen2.5 3B local Ollama evaluation over twelve
  constructed, pre-annotated sentences on read-only, no-secret,
  no-cloud GitHub Actions CPU compute; expected annotations
  remain unavailable to the extractor.
- Tests include combined true-command plus invented-physical
  effect, missing implied risk, false exhaustive history,
  source clock, gaps, duplicated IDs, invalid outputs and
  private-data/log isolation.
- Even perfect extraction of these constructed sentences
  **does not certify exhaustive semantics on arbitrary newly
  authored prose**. No production publication approval, model
  routing or active workflow code is changed.

See `docs/INVESTIGATION-STAGE-4J-PROSE-ATOM-COVERAGE.md`.
Rollback: revert this additive PR or disable the Stage 4J GitHub workflow.
