# 0.10.401

## Why this release

Live-testing follow-up: the hub's native Logs page separates "Location
events" (mode changes, sunrise/sunset) from "Hub events" (systemStart,
update, cloudBackup). The user asked whether either could be surfaced
by the app. Investigated live against the actual hub via the session's
MCP tools: location events are reachable today through the existing
`hub_list_device_events` tool contract when both `deviceId` and `appId`
are omitted (confirmed against the user's own screenshot data -- mode
names, order, and timestamps matched exactly). Hub events are not
reachable through any tool available in this MCP server -- an
exhaustive pattern search across the full system log (17,695 parsed
entries) for `systemStart`, `cloudBackup`, `System startup`, and
`Updated with build` returned zero matches. Hub events are therefore
out of scope for this release; they would require a different upstream
tool this server does not currently expose.

The user chose the fuller of two proposed scopes for location events: a
direct query surface, plus enrichment of the existing "why did X
happen" contact-event answers with the hub mode that was active at the
time.

## Added

**Direct location-event queries.** New pure-logic module
`location_event_queries.py` recognises two new deterministic request
shapes and a new `DeviceHistoryService.location_events()` method reads
them via the confirmed-live upstream contract (`hub_list_device_events`
with `deviceId`/`appId` both omitted, bounded to 168 hours back / 50
events, same limits as device history):

- "show recent mode changes" / "location events" / "what mode changes
  happened today" -- lists recent mode-change events, newest first,
  filtering out non-mode location rows (e.g. `sunriseSunsetUpdated`) so
  the answer stays focused on what the user actually asked about.
- "when did we last enter Night mode" / "when was School Run mode last
  active" -- reports the timestamp of the most recent matching mode
  change, or states explicitly that no such change was reported in the
  window (never fabricates a match).

**Mode context on "why" answers.** The existing "why did the front door
open" style answers (`_contact_event_outcome`'s `explain_cause` branch)
now append a short clause naming the hub mode that was active at the
event's timestamp, when that data is available -- e.g. "The hub was in
Night mode at the time." This is best-effort: if the location-event
read fails or no mode change precedes the reference timestamp, the
clause is silently omitted rather than guessed. The answer's existing
disclaimer that device history alone does not identify a cause or actor
is unchanged. Plain "when did X last open" questions (no "why") are
unaffected and do not trigger the extra read.

## Not included

**Hub events (systemStart, update, cloudBackup).** Confirmed
unreachable via any tool this MCP server currently exposes. Revisiting
this would require either a new upstream tool or an extension to an
existing one; out of scope here.

## Validation

- `python -m pytest -q` -- 754 passed (23 new: 15 in new
  `tests/test_location_event_queries.py` covering every pure function
  in the new module; 3 in `tests/test_device_history_service.py`
  covering `location_events()`'s omitted-target contract and bounds;
  6 in `tests/test_homebrain_agent.py` covering the two new direct
  queries, the why-answer mode enrichment happy path and its silent
  omission when mode data is unavailable, and confirming the plain
  "last contact" path does not trigger the extra read).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.401
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- `docs/RUNTIME-MODULE-MAP.md` updated with the new
  `location_event_queries.py` row (required for
  `test_runtime_modules_match_canonical_module_map` to pass).
