# HomeBrainOS v0.16.139 — Bounded scheduler entity cross-check

## Changes
- For whole-hub or scheduled-job optimisation reviews, compare the complete set of key-derived app/device candidate IDs against **current Hubitat identity inventories**. The normal four performance/scheduler/log reads remain unchanged.
- Fetch at most two extra sources, concurrently and read-only: app instances via `hub_list_apps` and an identity-only, first-page device projection via `hub_list_devices` (limit 450, no attributes, commands or current states). Each is capped at six seconds; a timeout does not block the other result.
- Clearly distinguish **entity listed in inventory** from **job ownership confirmed**. The encoded `appNNN/devNNN` scheduler-key relationship remains unverified even when the entity is present. Unlisted IDs do not prove deletion or orphaned jobs.
- Preserve completeness limitations: source-listed row count versus reported total, partial or unavailable inventory, and ambiguous duplicate entity IDs.
- Correlate positively matched candidate IDs with top measured `pctTotal` device/app performance rows as inspection priorities, **not predicted CPU savings**.
- Keep raw inventories private to the host reconciliation stage; expose only small grouped counts, limited named examples and performance overlaps to the model and the final report.
- Add regression tests for complete, partial, unavailable and duplicate inventories; wrong-type and display-name false joins; compact model packet; no extra reads for non-scheduler questions; and short simulated inventory timeout.

## Safety
No Hubitat apps, rules, drivers, devices or schedules are modified. Inventory membership confirms the ID exists in a returned listing, never that it schedules or executes a job. Full action/dependency verification and before/after savings experiments remain open in Issue #733.
