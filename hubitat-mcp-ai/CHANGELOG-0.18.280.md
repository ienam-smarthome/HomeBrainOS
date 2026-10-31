# Hubitat MCP AI v0.18.280 — Stage 3F local opt-in trace capture

**Source-only, not a live capture deployment.**

- Introduces `stage3_local_capture.py`, a per-request, explicit-consent,
  at-most-15-minute in-memory observer for model-chosen READ calls.
  Native private identifiers are session-HMAC pseudonymised and real
  times are replaced with synthetic equality-preserving windows.
- Records only bounded, positively declared READ schemas, scope shapes,
  previous read attempts and canonical verified identity/issuer leads.
  No source names, raw tool output, messages, credentials, household
  device IDs, raw state values or original timestamps are retained in
  collector records or shared reports.
- A live `UnifiedMCPAgent` only attaches capture when explicitly passed
  `stage3_shadow_mode="observe"` AND a separately consented
  `stage3_capture_session`. The add-on factory passes neither; default
  remains OFF. No UI/API/env settings enable it.
- Supports immediate `disable()`, automatic expiry <=900 seconds,
  strict single-request isolation, capped sample sizes and in-memory
  only aggregate reporting via Stage 3E.
- Adds privacy, expiry, scope/credential rejection, non-mutation and
  metrics registry regression tests.

**Limits:** A manually consented in-process trace does not by itself
independently authenticate provenance or prove model answer quality.
Real timestamps/source chronology are deliberately destroyed; no
historical causal-reconstruction claims can be made from the capture.

No Hubitat/HA writes, additional model rounds, new tool rights, actual
model-choice changes, publisher changes or installed add-on upgrade.
Details: `docs/INVESTIGATION-STAGE-3F-LOCAL-CAPTURE.md`.
Rollback: disable the local capture object or revert the PR.
