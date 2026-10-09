# HomeBrainOS v0.16.145 — Targeted scheduler candidate identity probe

## v0.16.144 live result
- 250/250 structured scheduled-job rows were analysed.
- 187 scheduler-key candidates remained unverified; 63 rows had no owner candidate.
- 41 of the 42 total `sendEventReminder` entries had no owner candidate.
- Primary context listed 51 of 94 candidate device IDs; 43 were absent from that scoped source.
- The new secondary `hub_list_devices` request hit its entire 4.5-second deadline before returning page 1: 0 rows, 0 matches, all 43 still unresolved.
- App candidate 4209 remained absent from the returned 152-app inventory.

## Changes
- Replace the slow secondary bulk inventory scan with targeted `hub_get_device` reads.
- Sample at most **6** context-absent candidate IDs, at most **2 concurrent reads**, within one **4.5-second overall deadline**.
- Count presence only when a successful response contains the exact requested numeric device ID.
- Treat rejected, not-found, malformed and timed-out reads as **unresolved**, never deleted/orphaned.
- Report attempted, matched, unresolved and unattempted counts so a bounded sample cannot be mistaken for an exhaustive inventory.
- Preserve the existing no-owner-candidate handler table and all ownership/causality disclaimers.

## Safety
Read-only. No device commands, state changes, app edits, rules, schedules or Hubitat settings are changed. A targeted identity match proves only that the device exists in that MCP source; it does not prove the device owns, created or executed the scheduled job.

## Next live verification
Rerun the exact scheduled-job analysis. The second-source section should now report targeted ID reads rather than a bulk page. If one or more candidates (for example 2065/6910/6911/6913/6918) return exact identities, that proves the context resource is a scoped subset for those IDs. It still does not establish scheduler ownership.
