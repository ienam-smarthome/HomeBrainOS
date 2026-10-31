# Hubitat MCP AI v0.18.277 — Stage 3C passive observation (default OFF)

**Source only; not a live deployment or activation.**

- Adds an explicitly opt-in `stage3_shadow_mode="observe"` argument to
  the original model orchestrator. Default remains `off`; the installed
  add-on exposes no setting to activate the observer.
- Adds `stage3_loop_shadow.py`, a metrics-only observer over the model's
  proposed calls, original already-retained READ receipts and the exact
  same round's advertised MCP read gateway operation enums.
- Reports aggregate bounded candidate counts, duplicate attempts, unsafe
  scope suppressions and unmatched schema proposals without copying
  credentials or modifying model messages or tool calls.
- Tests preserve off-by-default, causal uncertainty, exact catalog
  capability and no-write/no-answer-change boundaries.

No extra model rounds, tool executions, routing changes, final publisher
changes, Hubitat/HA device modifications, permissions or migrations.
The Stage 3A frontier remains advisory; nothing uses its candidates to
replace the original model's choices.

See `docs/INVESTIGATION-STAGE-3C-PASSIVE-OBSERVER.md`. A separately
reviewed rollout is required before any installed add-on enables observation.
Rollback: revert this additive PR; no live state change exists.
