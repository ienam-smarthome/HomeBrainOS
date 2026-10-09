# HomeBrainOS v0.16.144 — Bounded secondary device identity evidence

## v0.16.143 live observations
- The scheduler report completed in 20.4 seconds, covering all 252 jobs.
- 187 scheduler-key candidate jobs were identified, but **zero authoritative owner IDs**.
- 65 jobs had no candidate, and `sendEventReminder` had 42 total queued entries.
- The returned complete `hubitat://context` response identified 51 of 94 candidate device IDs; **43 were absent from this scoped resource**, not proven deleted.
- App ID 4209 remained absent from the returned 152-app inventory; no job ownership or redundancy was proved.

## Changes
- Only when a complete `hubitat://context` result has absent scheduler-key candidate IDs, make a secondary, identity-only `hub_read_devices -> hub_list_devices` probe.
- Limit to **4 sequential pages of up to 100 identities, with a 4.5-second overall stage deadline**. No state, capability, command, configuration write or unbounded scan.
- Verify matched candidate IDs only against actual numeric IDs in the second returned source. Report source-scoped matches, unresolved candidates, pagination status, counts and elapsed time.
- Neither a completed second MCP source nor an ID match is proof of complete Hubitat-wide inventory, scheduling ownership, current execution, redundancy or CPU savings.
- Separate job handlers with **no owner candidate** into their own deterministic, ranked table to help investigate `sendEventReminder` without misattributing its source.
- Add unit and host-plan regression tests for pagination, duplicate/malformed coverage, no-candidate handling, deadline, read-only evidence, and limited activation.

## Still outstanding
- Authoritative per-job owner and code/configuration dependency verification, and actual execution/CPU impact correlation. The existing MCP job snapshot does not expose explicit owner IDs.
- Investigate unlisted app candidate 4209 and unresolved device candidates using an authoritative Hubitat source outside the accessible candidate scope, if such read-only API becomes available.

No Hubitat settings, devices, apps, rules, or schedules have been changed.
