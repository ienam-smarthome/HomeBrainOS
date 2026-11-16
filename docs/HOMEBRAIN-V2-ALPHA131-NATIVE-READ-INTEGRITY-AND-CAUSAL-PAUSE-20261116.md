# V2 alpha.131 — source-read integrity and decision to leave causal prompt churn

**Status:** development candidate; exact-head CI and merge pending. V2 Preview only.

## Installed alpha.130 evidence and decision

The uncoached read-only WHY first answer (private capture, 16 November 2026)
was a normal completion with no publication fallback but did not identify the
most recent shared-heating ON event. It read a participating Livingroom TRV
heating report at 16:25:30 rather than the unread shared controller output.
The scheduler's returned log at that moment said it was waiting for two
minutes of continuous room demand before starting the shared source. A
participant's historical `thermostatOperatingState=heating` does not prove
the central output activated. The question requires accurate *model-chosen*
focal-output identification across possible home setups. The existing
outcome-first review already told the model to discriminate roles, yet it
did not. More heating-word-specific routing or repeated prompt polishing is
not justified without general cross-domain live acceptance.

The captured request had 7 transport-successful reads, 6 model rounds,
362,254 provider-reported input tokens and 296.5s elapsed. One
`hub_list_devices` query for all detailed switches returned only an
upstream `response_too_large=true, truncated=true` diagnostic; V2 counted
that as a **successful source read**. This is a *verifiable source-accounting
defect*, unlike the unsolved model-choice problem.

## Bounded general fix

- Recognise **only** the exact top-level (or single MCP text JSON) native
  `response_too_large=true` + `truncated=true` envelope for the tool
  actually called; don't scan nested device data or equate a phrase with a
  native error.
- For READ-ONLY native calls, classify that result as a failed source:
  `success=false`, an explicit `source_limit` in PRIVATE Technical JSON,
  and a model-facing `client_source_limit` notice. Preserve the original
  native response and actual executed call. No silent automatic retry or
  device/tool routing.
- Keep command/write-path `isError` handling, UI confirmation and source
  receipts unchanged; unrelated native successful reads remain successes.
- Fictional unit and end-to-end tests cover positive/negative envelopes,
  wrong tool, source immutability, no automatic extra tool/model rounds,
  accurate current source progress and ordinary source reads.

## Boundaries and next development

**This is NOT a fix for the model picking the wrong historical controlled
output.** Do not claim a higher first-answer score, lower token costs, or
physical confirmation from CI. Avoid yet another causal-prompt-only
version. Move to other V2 scope priorities (e.g. System Health /
Troubleshooting Center, non-LLM status summaries, or user-facing
reliability) until a general, cross-domain, receipt-verified causal method
is feasible. When causal work resumes, benchmark multiple independently
scoped historical output-versus-participant cases rather than a single
heating incident. Never hardcode home device or app IDs.

V1, the heating scheduler, native device actions and write approvals
remain unchanged. No real hub/device calls occur in tests; private
household receipts are not committed.
