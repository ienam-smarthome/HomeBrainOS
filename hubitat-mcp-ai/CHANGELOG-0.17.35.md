# HomeBrain 0.17.35 — Reusable investigation intelligence

## Purpose

Following live tests on the same Hubitat hub in three independent domains,
HomeBrain could retrieve evidence but sometimes stopped at a successful
configuration/health lookup instead of proving the requested historical
question. Further source retrieval also risked unrelated broad log scans and
unverified scheduler ID probing. This release introduces a shared approach
rather than adding phrases or automation-specific exceptions.

## Architecture

**Goal → evidence requirements → bounded collection → sufficiency assessment
→ final answer** is now a reusable contract in
`investigation_intelligence.py`.

- An investigation plan distinguishes required and optional evidence, proper
  source type, the stopping condition when coverage is incomplete, and
  conclusions that cannot be made from partial data.
- The existing unified MCP agent sees the contract before deciding tool
  calls. It prioritizes relevant target evidence and can stop with an
  explicit unresolved conclusion instead of gathering arbitrary hub-wide
  snapshots.
- The final evidence-scoped synthesis independently evaluates current-turn
  tool receipts, distinguishing **observed historical evidence**,
  **checked-but-unverified**, and **not checked**. An MCP success is not
  evidence that a timer ran, a device accepted a command, or a job has an owner.
- Lockout evidence must include a historical OFF, a controller event within
  five seconds, motion after the OFF within three minutes, and a same-window
  app decision log. Unrelated earlier/later events cannot silently satisfy
  the contract. These are evidence gates, **not fabricated execution claims**.
- Device health separates reported state, telemetry freshness, targeted
  watchdog logs and command reachability. Stale data and a connected MQTT
  flag cannot by themselves establish whether commands are received.
- Scheduler investigation distinguishes structured jobs, explicit owner IDs
  and measured executions. A matching scheduler-key prefix is never proof
  of owner identity.

## Efficient evidence acquisition

For **scheduler-specific** investigations, the existing host collector now
starts with structured jobs and bounded performance statistics only.
It skips broad 30-minute logs and adaptive busy-entity log reads that do
not establish scheduler ownership. Where no explicit owner IDs appear on
job rows, it also skips whole-hub identity cross-checking and failed
candidate-ID probes that cannot verify ownership. Full whole-hub performance
requests retain their existing broader evidence plan.

## Regression coverage

New tests cover actual live shortcomings for:
- Livingroom Light 1 / app 4019: current lockout status and sensor health
  cannot establish a previous manual-OFF lockout; time-mismatched history
  is rejected.
- Bedroom 3 Mesh / device 7103: almost twenty hours of telemetry silence,
  MQTT connected indicator and watchdog retries establish stale reporting,
  but not command delivery failure.
- Scheduled jobs: 257 rows may show scheduler-key candidates but without
  source owner fields, ownership remains unverified and expected CPU savings
  must not be invented.
- Normal device control and status queries bypass investigation contracts.

## Scope and limitations

Read-only. No new periodic polling, device/rule changes, history retention
changes, or upgrades to MCP Rule Server. The contracts measure evidence
sufficiency for supported investigation domains; they do not turn missing
upstream scheduler ownership metadata into authoritative data. The live
behaviour still needs validation before this framework is considered
generalised to other unseen domains.

## Live validation

After updating, repeat the three cross-domain read-only tests. For app 4019,
HomeBrain must identify a real manual OFF and corresponding lockout decision
or report missing historical evidence, not merely the configuration. For
Bedroom 3 Mesh, classify telemetry silence without claiming command failure
or unsupported MQTT LWT diagnosis. For scheduled jobs, avoid owner guesses
and unnecessary probes and report actionable bounded diagnostics.
