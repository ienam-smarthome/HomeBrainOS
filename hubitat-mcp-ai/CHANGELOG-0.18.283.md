# Hubitat MCP AI v0.18.283 — Stage 4C local-model semantic evaluation

**Source-only: no production prompt, publisher, model route, MCP tool or add-on deployment changed.**

- `stage4_offline_model_evaluation.py` executes an explicitly supplied local
  model adapter against at most eight offline cases: optionally asks an
  author model to write new Stage 4A typed narrative drafts, and separately
  asks two distinct reviewer models to assess cited evidence.
- `tools/stage4c_local_model_eval.py` supplies a manual, double-consent
  local Ollama client fixed to 127.0.0.1, with disabled proxies, no
  redirects, bounded input/outputs, timeouts, and only aggregate printout.
- Bundles a constructed eight-case reference corpus covering lighting,
  heating, extractor commands, collector-time reports and historical gaps.
- Independently supplied oracle labels are **never sent to models**.
  New model-authored sentences are always **unscored** until separately
  adjudicated after generation, even with unanimous reviewer agreement.
- Regression tests use mock model adapters, not genuine models. This PR
  has **not** measured real reviewer accuracy. Independent model IDs do
  not prove independence, and local Ollama routing must be confirmed by
  the operator not to use cloud models.
- Output includes false acceptance, false rejection, incomplete review
  sets and response counts, without original sentences, real device IDs,
  timestamps, credentials or model text.

`safe_to_publish=false` and `semantic_ground_truth_independently_verified=false`
are irrevocable for this source-only stage. No live Hubitat/HA changes
or tool execution; Stage 3F remains disabled by default.

See `docs/INVESTIGATION-STAGE-4C-LOCAL-MODEL-EVALUATION.md`.
Rollback by reverting this additive PR.
