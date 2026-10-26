# HomeBrainOS v0.18.150 — Preserve verified snapshots and recover empty switch history

The v0.18.149 live Investigation V2 test correctly identified Bedroom 3 Mesh
(device #7103), performed four successful MCP reads and retained a current
device snapshot: `healthStatus=offline`, `deviceHealth=unknown`,
`mqttStatus=connected`, `switch=off` and
`lastSeen=Mon Oct 12 01:30:01 BST 2026`. The final "grounded answer" then
incorrectly stated that no current observation was available. The
switch-filtered historical request (381 hours, limit 500) returned zero source
rows, followed by two irrelevant diagnostic reads. Unsupported hypotheses
were passed to atomic claim synthesis, which attempted a repair and fell back.

## Changes

- **Current snapshot survives synthesis.** The host now includes the same
  source-projected, allowlisted status fields in both the technical report and
  canonical grounded answer, with explicit read-time provenance.
  `lastSeen` is a reported historical value, not independent evidence of a
  physical event at that time; `mqttStatus=connected` may describe the
  broker client, not device reachability. Stored wattage may be stale.
- **Recover from empty switch history.** When a positively successful
  switch-filtered read returns *zero actual source rows*, the host can attempt
  one unfiltered historical read for the same independently verified device.
  That extra read must pass the live tool schema, permissions and read-only
  validator, and is bounded to 50 rows. It does not establish source
  completeness and never permits an arbitrary device/command.
- **Bound history page sizes.** Device-context history requests now cap at
  50 rows, consistent with the MCP skill's recommended pagination approach.
  The valid last-contact timestamp still selects a bounded time range, but
  neither the time span nor response success proves chronological coverage.
- **Don't pay to invent evidence.** If authenticated read-time device status
  exists but no time-stamped case observations were retained, V2 uses the
  deterministic host-grounded output rather than asking the model to invent
  atomic source record IDs and spending another correction round. The answer
  remains explicitly incomplete and does not claim a root cause.
- **Regressions.** Synthetic tests cover returned status, retained credentials
  redaction, empty switch history with a recovered unfiltered state, both
  histories empty, no extra model atomic/repair calls, and unchanged write
  boundaries.

## Outstanding

The semantic objective planner, full-inventory retrieval, and deeper
app-log/driver causal reasoning still need performance and quality work.
Source retention or unexposed historic data may prevent recovering the
12 October outage. No unverified physical-cause conclusion is permitted.

All changes are opt-in Investigation V2 only; production V1 and Hubitat
devices, apps, automations and permissions remain unchanged.
