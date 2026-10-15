# HomeBrain v0.17.77 — Native event-retention contract, earlier focal reads, and current source coverage

## What the live v0.17.76 trace actually proves

On 15 October, HomeBrain v0.17.76 queried Livingroom Light 1 (device 7805) for an exact 14 October window (18:54:36.691Z–18:56:00Z). The query succeeded but returned **zero switch-state events**. HomeBrain separately queried app 4129, SenseCap D1 Settings, via `hub_get_logs` and got **zero logs**. Its earlier `command-on` history did return SenseCap's on() command at 19:54:46.691 BST. The answer was safe about causation but took eight model rounds/33.4 seconds and incorrectly appended “app_logs not verified as checked” after the successfully scoped app-log read.

Upstream `kingpanther13/Hubitat-local-MCP-server`, `libraries/mcp-devices-lib.groovy`, implements `_deviceHistoryBypass` by calling `_fetchBypassDeviceEvents(deviceId)` once and filtering that **current native /device/eventsJson store** by `since`/`until`. These are **filters on retained rows**, not archived timestamp-indexed reads or pagination into expired historical events. A prior session retrieved the physical ON and OFF, but later latest-N switch pages show the oldest returned switch at 22:45:47 on 14 October, beyond the requested 19:55. Current exact-window zero therefore cannot disprove the earlier observed event. No change to HomeBrain can manufacture a device event no longer returned by upstream data.

## Code corrections

- After the already-existing host causal subject prefetch and verified command-source receipts, run the missing-focal window query immediately, before repeated model exploration. A failed or empty query now yields the same calibrated fail-closed conclusion without several unnecessary model rounds. Successful recovery continues normal graph-based investigation.
- Extract a reusable `_execute_focal_plan` host method so both early completion and normal finalization use the same read-only execution path.
- After late host source reads, **recalculate** required source-class coverage. Do not append a pre-read “app_logs unchecked” warning after a successful app-ID-scoped log query; an empty log result means “checked, zero returned”, not “never executed”.
- Preserve `upstreamReturnedCount`, upstream window mode, and explicit inability to certify native store completeness in projected evidence.
- Explain that the oldest switch entry in the current recent page is newer than the user's requested incident, without asserting the hub's retention configuration, or that the incident never occurred.
- An empty app-specific history must not be conflated with a failed app-log read or proof the app did not execute.
- Regression tests replay the empty requested window plus an independently checked empty producer log.

## Safety and future prevention

Read-only diagnostics. No devices, rules, scheduled Internet blocks or Hubitat settings are modified. For *future* historical investigations, a continuously captured external event journal can preserve events before the native event store rotates; this release does **not** enable or change journal collection. To determine the exact current retention setting, examine the device’s `maxEvents`/Events preferences and compare with its oldest exposed events. If upstream native event history no longer includes a past event, HomeBrain must explicitly report that limitation rather than claim a cause.

## Live acceptance

After installation, repeat the prior light question once. Expect a bounded device-state read for device 7805, a scoped app-log read for app 4129, no incorrect `app_logs unchecked` wording, and substantially fewer AI rounds when the event remains unavailable. The answer may still be “Historical ON not independently verified,” because upstream now returns zero rows. Check metric `skills_early_focal_stop` when early stop is taken.
