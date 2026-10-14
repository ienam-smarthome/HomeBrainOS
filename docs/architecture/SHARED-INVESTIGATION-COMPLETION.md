# Shared evidence completion (v0.17.55)

## Problem
Source-based completion in v0.17.54 ran inside one native model tool loop,
so deterministic early exits were able to return `success` with no
`investigation_coverage`. The observed outcome adapter also dropped
previously assessed coverage.

## Architecture
`app._answer_result` awaits the request coordinator and runs the single,
read-only `apply_shared_investigation_completion(outcome, prompt)` API
checkpoint before either /api/ask or /api/chat consumes the outcome.
The adapter preserves original specialist response fields.

For recognised historical/causal and existing typed domain investigations,
the checkpoint:
1. Reuses earlier structured investigation assessments where supplied.
2. Compares scope-relevant successful read receipts against source classes.
3. Separately records source integrity and truncation warnings.
4. Keeps `evidenceComplete` false or unknown when no independent proof exists.
5. Preserves all previous findings and reports the missing classes.
6. Marks an otherwise successful partial investigation as `unresolved`.

A `command-history` lookup must target a command event attribute rather
than count a switch-state event as a command. A reported `producedBy`
bridge is the transport/source of a Hubitat event; it is not automatically
the upstream actuator or the initiating automation.

## Deliberate scope
This gate does not issue another MCP call at the API boundary. Fresh data
fetches remain the responsibility of authorised, budgeted read executors
and the v0.17.54 semantic missing-source retry. Causal proof and telemetry
freshness require source-specific reconciliation. The generic gate never
upgrades a checked source to a verified historical cause.
