# HomeBrain 0.17.36 — Shared investigation intelligence

This release is rebased on the independently merged **0.17.35**
historical manual-OFF motion lockout acquisition improvement (PR #810).
It preserves that read-only event collector rather than duplicating or
replacing it.

## General architecture

HomeBrain now uses an explicit **goal → evidence requirements → bounded
retrieval → evidence sufficiency → final synthesis** framework across:
- Past manual-OFF/motion lockout diagnosis, requiring time-linked light OFF,
  controller, motion and app-decision evidence rather than current configuration;
- Stale MQTT/device health, separating live attributes, actual telemetry age,
  watchdog log evidence and independently unverified command reachability;
- Scheduled-job ownership, separating scheduler entry metadata from candidate
  ID prefixes and measured execution/performance information.

The contract is applied before the agent chooses read tools and re-assessed
against successful **current-turn** receipts before final synthesis. Every
necessary source is classified as observed, checked-unverified or not checked.
A successful MCP request does **not** imply that a historical event or
automation execution was proven.

The API now exposes `investigation_coverage` on applicable read-only
investigations, independently of the ordinary `success` transport flag.
Other request response shapes remain unchanged.

## Scheduler efficiency

For scheduler-specific efficiency questions, the deterministic collector
limits the initial reads to structured jobs and bounded performance data.
Unrelated generic and adaptive log collections are skipped. Candidate owner
ID probes and identity inventories are also skipped when scheduler rows
contain **zero explicit owner IDs**, because they cannot promote
scheduler-key candidates into verified owners. Whole-hub performance requests
retain their existing comprehensive path.

## Tests and safeguards

Cross-domain regression tests reproduce the three live scenarios, including
a lockout query that sees only current configuration (unverified), a
time-mismatched OFF/button/motion sequence (not causal evidence), a device
with nearly 20 hours of stale telemetry and a connected MQTT flag (command
delivery unknown), and job rows with only unverified owner-key candidates.
Normal controls do not enter this investigation path.

Read-only; no changes to devices, rules, scheduled settings, MCP Rule
Server, model provider settings or Historical Journal retention
(7 days / 200,000 rows). Historical evidence unavailable from upstream
sources remains unavailable, and this layer does not fabricate it.

## Live validation

Repeat the three independent tests against 0.17.36. Inspect the technical
`investigation_coverage` status separately from success; verify historical
lockout proof requirements, the distinction between telemetry and command
reachability, and that scheduler-only reads no longer perform unrelated
inventory probes or broad logs.
