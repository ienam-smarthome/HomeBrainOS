# HomeBrainOS v0.16.146 — Scheduler probe provenance isolation

## Live v0.16.145 finding
The targeted scheduler identity probe achieved its performance goal: six candidate IDs were checked in 168 ms rather than spending the previous 4.5-second budget on a bulk device-list page. All six reads were unresolved.

The same run exposed an evidence-provenance bug. Failed `hub_get_device` probes emitted MCP Rule Server `Device not found` log entries. Because adaptive app-log collection ran after those probes, HomeBrain read its own newly generated diagnostic rows and described them as an existing MCP Rule Server error loop. The recommendation to remove configuration references was therefore unsupported.

## Fix
- Adaptive device/app diagnostic log reads now complete **before** targeted scheduler identity probes run.
- The targeted probe remains read-only with the v0.16.145 limits: max 6 IDs, max 2 concurrent reads, 4.5-second total deadline.
- Secondary-source metadata records that the probe ran after diagnostic log acquisition and that failed lookups may create expected Rule Server not-found log rows.
- The rendered scheduler cross-check explicitly warns that such probe-generated rows must not be diagnosed as a pre-existing Rule Server error loop.
- Added regression coverage asserting adaptive app-log evidence is acquired before `hub_get_device` probes.

## Interpretation
The v0.16.145 failures for 2065, 6910, 6911, 6913, 6918 and 6921 show only that those targeted reads did not resolve through `hub_get_device`. They do not establish deletion, stale schedules, scheduler ownership, redundancy or safe removal.

## Safety
No Hubitat devices, apps, rules, schedules or settings are changed. Diagnostic reads can cause the MCP Rule Server to write its own error log for a failed lookup; v0.16.146 isolates that diagnostic side effect from the evidence used to assess pre-existing logs.
