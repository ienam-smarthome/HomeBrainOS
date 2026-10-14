# Hubitat MCP AI v0.17.55 — shared completion for investigations

## What's new
- Add a common, read-only evidence-completion checkpoint after the request
  coordinator. It applies to /api/ask and /api/chat regardless of whether
  the answer used a model-led MCP loop, deterministic early exit or specialist
  investigator.
- Preserve `investigation_coverage` when turning agent results into
  metric-bearing observed outcomes (a previously overlooked copy omission).
- Track targeted command history as distinct from switch state history:
  a Hue Bridge-reported physical state event is not a proof that the hub
  logged (or did not log) a particular upstream command.
- Preserve domain-specific evidence obligations for device telemetry,
  scheduler ownership and historical motion lockout.
- Expose source classes checked/unverified and history truncation or integrity
  warnings in `investigation_coverage.sourceCoverage` and
  `sourceIntegrityWarnings`.
- A partial investigative result changes `metrics.outcome` from `success`
  to `unresolved` where applicable, and appends a concise factual
  incompleteness statement without replacing verified observations.
- Add request metric counters and regression tests for Bedroom 3 Mesh,
  Livingroom Light 1 and proposal-only requests.

## Safety and limitations
- No action or confirmation is performed by the completion checkpoint.
  Failed/cancelled/write requests and ordinary inventory lookups are unchanged.
- The initial cross-path checkpoint is **post-read**, not a new independent
  read executor. Model-led investigative requests can still perform the
  bounded missing-source retry added in v0.17.54. Specialist fast paths
  disclose missing coverage but do not automatically query new sources.
- No generic model-free verifier can prove an upstream command initiated
  a state transition merely because source classes were read. Causal
  completeness remains conservative until independent provenance proof.
- Some legacy investigative goals have no fully typed requirement contract;
  this release does not claim universal semantic classification or proof.
