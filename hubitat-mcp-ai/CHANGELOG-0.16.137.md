# HomeBrainOS v0.16.137 — Live Hubitat scheduler-job ID parsing

## Fixes
- Parse the actual job-key forms observed in the v0.16.136 live test: `dev7086Once.heartbeat`, `dev7334Once.healthCheck`, `dev7889Recur.autoPoll`, `dev6910Recur.sessionTick`, and other strictly formatted `app/devNNNOnce/Recur.method` records.
- Preserve strict validation: full keys only, owner IDs must be nonzero positive numeric strings, and a method encoded in a job key must match a separately provided method field when one exists. Display names and embedded job-name fragments are not used as ownership evidence.
- Keep scheduler-key matches **unverified owner candidates**, distinct from confirmed appId/deviceId ownership. Report candidate counts by app versus device while retaining unknown/unauthenticated owner totals.
- When Gemma displays a sampled job-table row with an unverified key-derived owner (e.g. "Device 7086"), mark the matching cell as "Unverified candidate device 7086" if the host digest has zero explicit owners.
- Regression tests reproduce live job keys and map/list scheduler encodings, distinguish verified owner rows from candidates, cover mismatched methods/false lookalikes, and protect sample table labels.

## Scope
- All changes are read-only to Hubitat.
- Ownership remains unverified until IDs are joined against an authoritative app/device inventory. Matching next-run times do not prove simultaneous execution, CPU spikes or predicted efficiency savings; further work remains tracked under issue #733.
