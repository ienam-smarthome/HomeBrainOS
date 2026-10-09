# HomeBrainOS v0.16.141 — Fast, coverage-safe scheduler device identity cross-check

## Changes
- Prefer the MCP client's `hubitat://context` bulk resource for scheduled-job device identity verification, retaining **only device IDs/names**, not live state; accept completeness only when the resource's structural coverage checks pass.
- Retain the six-second **total** device inventory stage deadline, including any fallback. If compact context is unavailable or incomplete, attempt a first-page, identity-only `hub_list_devices` read (limit 125, rather than 450) within remaining time.
- If a source is incomplete, report only what was verified; do not treat unlisted candidates as deleted or orphaned jobs.
- When the device inventory is **unavailable**, show all 94 (or actual) candidates as **not checked**, not falsely as 94 unlisted identities.
- Surface exact app candidate IDs unlisted from a reported complete app inventory (for example app 4209) as **investigation-only** leads, without assuming an obsolete scheduler entry.
- Add regression tests for fast complete-resource reads, incomplete context with bounded fallback, unavailable context fallback, and unavailable inventory counts.

## Safety
- No Hubitat state writes or changes to scheduled jobs, apps, devices, or drivers.
- Matching entity IDs still does **not** establish job ownership or execution frequency; actual performance impact and safe scheduling changes require separate evidence.
- The new resource path and timing still require live Hubitat verification after Home Assistant add-on update.
