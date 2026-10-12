# HomeBrain 0.17.37 — Cross-phase investigation evidence enforcement

## Live regression (12 October 2026)

Three live tests on 0.17.36 exposed sources of *architectural drift*:
- Livingroom manual-OFF/motion-lockout question again yielded current
  configuration and sensor/bridge health (8 calls, no model round), without a
  historical OFF, button or app-execution trail.
- Bedroom 3 Mesh device 7103 returned useful telemetry-age evidence but made a
  malformed `hub_get_device_attribute` call lacking `attribute`, while its
  nested device-scoped `hub_get_logs` request appeared to return unrelated
  whole-hub log rows.
- Scheduler-only investigation correctly limited host collection to jobs
  plus performance statistics, but the independent API finaliser appended a
  general recent-log call, increasing the final count to three.

## Architecture

**One source plan across all phases.** The scheduler-only read-plan
classifier is shared by the collector, final answer coordinator and API
performance finaliser. A scheduler-only job/owner analysis requires job rows
and bounded performance data; it never inherits whole-hub log requirements
merely because a separate performance finaliser runs afterward. Broader
whole-hub performance questions keep recent-log collection.

**Structural gateway integrity.** New `evidence_gateway_contract.py` safely
unwraps repeated read-only MCP gateway envelopes while preserving explicit
device and time filters. A declared read with missing required inputs is
rejected locally as an unsuccessful validation instead of being sent to Hubitat.
Mutating commands are never rewritten by this read normaliser.

**Goal-completion evidence.** The investigation assessor now understands the
structured `homebrain_motion_lockout_investigation` receipt, not only generic
device-event rows. It assesses actual focal OFF, nearby button evidence,
subsequent active motion and verified app decision separately, without
turning configured lockout settings into proven execution. It also refuses
to count unrelated log messages as device watchdog activity.

**Request routing.** Explicit investigative goals take precedence over the
generic automation-status shortcut. A live-read investigation that finishes
via a direct/specialised path still publishes `investigation_coverage`
instead of silently losing the completion assessment. An unverified
historical explanation can coexist with a successful MCP request.

**Scheduler API evidence.** The finaliser exposes a count-only source digest
(checked scheduler rows, verified explicit owner rows, unverified key-pattern
candidates) as investigative coverage. No inferred owners or CPU savings.

## Safety and compatibility

No device commands, rules or configuration updates. Existing history
capture and 7-day / 200,000-row retention remain unchanged. Normal controls
and broad whole-hub performance reviews keep their established routes.

## Live verification

Update to 0.17.37 and repeat the three distinct read-only tests. Confirm:
- Manual-off lockout returns a historical focal receipt or explicit
  missing-history coverage (not just current sensor health).
- Bedroom 3 Mesh has no invalid network attribute request, preserves the
  device filter for logs and does not equate host-generated age increments
  with new device telemetry.
- Scheduler-only tool list has **two planned calls and no finaliser-added
  hub_get_logs**, with 0 verified owners if MCP lacks owner fields.

Regression tests and CI validate the code paths, but real Hubitat evidence
and source availability must still be checked on the next live run.
