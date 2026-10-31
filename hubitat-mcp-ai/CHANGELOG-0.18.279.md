# Hubitat MCP AI v0.18.279 — Stage 3E private offline trace reporting

**Source-only: no live update, trace recording, activation or deployment.**

- Adds `stage3_trace_privacy_report.py`: runs the Stage 3D original-model
  versus advisory-frontier comparison locally and returns strictly
  allowlisted aggregate counts and precision/recall metrics.
- Adds `tools/stage3e_local_trace_report.py`: reads an explicitly
  acknowledged, local-only, at-most-1-MiB replay file and prints aggregate
  JSON, never input JSON, credentials, device/app IDs or input paths.
- Suppresses domain-level cells with fewer than three source cases and
  rejects oversized/malformed records rather than hiding truncated trials.
- Deliberately does not authenticate self-labelled `user-labelled-redacted-trace`
  inputs or claim production improvements.
- Regression tests for six-domain replay, privacy/secret non-disclosure,
  local CLI acknowledgement, fail-closed errors and opt-in policy.

No active model planning, execution, authorization, model prompts, publisher,
Home Assistant/Hubitat configuration, device actions or data migration.
The Stage 3C observer remains OFF. Genuine trace capture and any Stage 4
publication change require separate explicit approval and verification.

See `docs/INVESTIGATION-STAGE-3E-PRIVATE-TRACE-REPORT.md`.
Rollback: revert this additive PR.
