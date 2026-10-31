# Hubitat MCP AI v0.18.276 — Stage 3B offline planning validation

**Source-only, shadow-only; not an installed or activated release.**

- Adds `stage3_planning_evaluation.py` to evaluate Stage 3A advisory
  next-read ranking against independently authored expected-read fixtures.
- Measures top-k precision, oracle recall, initial useful rank, suppressed
  duplicates, unverified IDs, invalid scopes and unsupported leaves.
- Direct legacy comparison is reported only for genuinely comparable grouped
  witness scenarios, never invented for heating, power or missing histories.
- Adds anonymised fixture regression coverage for paired lighting, heating,
  humidity-driven ventilation, offline power device, failed historical reads
  and adversarial proposals/secret handling.
- Hardens Stage 3A against malformed dependency metadata: no crash or
  accidental app-ID admission.

No routing, MCP execution, agent prompt, publisher, Home Assistant configuration,
Hubitat device, database or production planning behaviour is changed.

See `docs/INVESTIGATION-STAGE-3B-OFFLINE-VALIDATION.md`.
Rollback: close/revert this PR; there is no runtime activation to undo.
