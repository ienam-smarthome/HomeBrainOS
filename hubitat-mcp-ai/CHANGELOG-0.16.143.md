# HomeBrainOS v0.16.143 — Scheduler report evidence-first rendering

## Live v0.16.142 findings
- The scheduled-job request completed in 18.9 seconds; 252/252 jobs were reviewed.
- Compact MCP context returned 181/181 devices in 1.2 seconds, but that completeness applies only to the returned resource, not necessarily all devices on Hubitat.
- 51/94 device candidate IDs and 40/41 app candidate IDs occurred in returned snapshots; 43 device candidates and app 4209 were absent from these sources, **not proven deleted**.
- The model's first table incorrectly presented candidate method aggregates as confirmed Device/App owners, omitted the 42 `sendEventReminder` entries, and mislabeled cadence observations.

## Fixes
- Replace recognized model-generated opening `Scheduled Job Analysis` tables with the deterministic job workload summary from all returned structured rows.
- Replace recognized model-generated `Observed High-Frequency Activity` tables with source-labelled, validated log interval data. Do not transfer Halo3000x's one-minute energy cadence to an unrelated Octopus device.
- Preserve AI inspection commentary and measured-performance discussion; source-derived job and cadence tables take precedence.
- Present MCP context completeness as **resource-scoped**, not independently verified hub-wide device completeness, and identify `hub_list_apps` as the actual app inventory source.
- Regression tests cover conflicting model table counts, source-cadence identity, unchanged unrelated prose, source coverage and missing-ID safety.

## Limitations and safety
- Matching a candidate ID verifies identity presence in the returned source, **not job ownership**.
- Job entry counts and observed log intervals do not establish execution frequency, CPU contention or potential savings.
- No Hubitat devices, apps, rules or schedules were modified. Live verification pending.
