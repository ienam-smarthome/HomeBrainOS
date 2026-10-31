# Hubitat MCP AI v0.18.278 — Stage 3D controlled offline replay

**Source-only milestone, not a live installation or activation.**

- Adds `stage3_controlled_replay.py` to compare the original model's
  supplied MCP read-call sequence with the existing Stage 3A advisory
  evidence frontier on precisely the same pre-round retained receipts and
  positively declared gateway operation enums.
- Independently authored expected reads are used only after both sequences
  are computed; absent or unverifiable references do not inflate results.
- Six-domain, constructed model-call fixture coverage: paired lighting
  historical reconstruction, thermostat issuer, humidity fan, offline
  power history, failed history and adversarial unsupported/secret calls.
- Reports top-k utility, exact duplicate prior attempts, ungrounded IDs,
  malformed scopes and unsupported suboperation counts, with no source
  identifiers or arguments emitted.
- Explicitly distinguishes constructed regression data from authentic
  production model call traces. **No end-to-end latency or live reasoning
  improvement is claimed.**

No production orchestration, planner activation, tool execution, final
publisher, UI feature flag, Hubitat or Home Assistant device change, migration
or deployment occurs.

See `docs/INVESTIGATION-STAGE-3D-CONTROLLED-REPLAY.md` for bounded
inputs, privacy, limitations, acceptance gates and next steps.
Rollback: revert the PR; no active runtime change to undo.
