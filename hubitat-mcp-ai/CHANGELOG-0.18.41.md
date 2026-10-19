# v0.18.41 — Prioritised whole-hub evidence and scheduled-job coverage

## Live v0.18.40 findings
The read-only comprehensive audit now reliably completes (~32.3 s, no model round) and checks a 205-device inventory, 152 normalised automation instances, capped 200 log rows, 20 each app/device performance leaders, and three scoped diagnostic sources. It finds four explicitly offline devices, Bedroom 3 Mesh watchdog warnings and OpenWeatherMap error log rows, while correctly honoring the user's intentionally unpowered SenseCap D1 setting.

However the requested scheduled-job source was **not read** by the comprehensive route and the 11K-character report front-loaded inventories ahead of ranked, actionable observations. An old heartbeat timestamp is not proof that failover stopped; an enabled or disabled automation record does not by itself prove schedule execution or ownership.

## Changes
- Add a single bounded (4-second cap), **read-only** `hub_get_jobs` call using the existing registered log/diagnostic gateway. Analyse only the structured returned jobs via the existing `summarize_job_workload`. Include a precise typed evidence receipt for success/failure; no schedule edits or guessed device/app IDs.
- Show reported and examined job counts, explicitly verified owner-field count, busiest returned method counts and shared next-run timestamps. A queue item is not executed work, shared timing does not prove CPU contention, and scheduler-key guesses are not authoritative owner IDs. If the gateway fails, label job coverage as **not independently examined**, never as zero jobs.
- At the very top of comprehensive reports, show up to five **prioritised evidence-backed checks**. Correlate an exact offline device ID with its actual scoped watchdog warning, name remaining explicitly offline IDs separately, identify sampled ERROR log sources by exact ID, and conditionally surface quiet devices actually named *heartbeat* as candidates for schedule verification rather than verified failover failures.
- Respect user-marked intentionally unpowered SenseCap D1: leave it out of unexplained-error recommendations. No source-grounding shortcuts that classify all quiet devices as faulty.
- Keep the original detailed audit report below the priorities and scheduled-job digest. All source limitations and read-only confirmation protections remain.
- No new MCP tool privileges, no Hubitat mutations or paid routing changes. Free Gemma remains default.

## Tests and limitations
Tests reconstruct the v0.18.40 offline, watchdog, weather-driver and quiet heartbeat examples; validate 273 queued jobs with 52 reminder entries and 35 same-time entries; prevent false owner/CPU/failover diagnoses; check missing/malformed scheduler reads; preserve detailed audit coverage and safe rendering; update the existing integration fake to expect one more read. Full CI is required before merging.

Still not verified in this release: which specific Rule Machine rules overlap Light Mode Controller, whether disabled apps retain valid jobs, which heartbeats should run, or the cause of physical device communication failure. Those require explicit cross-source rule/app configuration and execution evidence.
