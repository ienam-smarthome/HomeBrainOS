# 0.10.404

## Why this release

Live-testing follow-up. The user asked for "front door last opened" and got
a correct 9-event history, but the general device-history answer rendered
raw Hubitat ISO timestamps verbatim ("2026-08-10T15:04:12.318+0100") instead
of a readable local time -- every other history-style presenter in this
codebase (`contact_history_queries.py`, `location_event_queries.py`) already
renders through `natural_datetime.format_natural_datetime`; this was the one
remaining raw-ISO leak.

The user also reported an apparent contradiction: a bare "Front Door" query
answered "No contact events were reported... in the last 24 hours," while
"front door last opened" (asked shortly after) found 9 events in that same
window. Investigated directly against the live hub and the current code:
the underlying event-history API, device resolution, and presenter logic
all check out correctly for this device (`hub_list_device_events` with
`attribute="contact"` and without both return the same event set). The most
likely explanation is timing, not a bug: the two questions were evidently
asked far enough apart that door activity happened in between, so "no
events in the trailing 24 hours" was genuinely correct at the moment of the
first question. No code change was made for this one, since it could not be
reproduced as an actual defect in the current code path.

## Fixed

**Device-history events rendered raw ISO timestamps instead of readable
local time.** `deterministic_tool_presenter.py`'s `_present_device_history`
(used both for the general `homebrain_device_history` answer and any "last
X" query the model reaches through the standard tool-calling path) built
its timestamp with a bare `str(event.get("date"))`, unlike
`contact_history_queries.py` and `location_event_queries.py`, which already
route through `format_natural_datetime()`. Now uses the same helper, so
`"2026-08-10T15:04:12.318+0100 -- **contact: closed**"` renders as
`"3:04 pm on Monday 10 August 2026 -- **contact: closed**"`.

## Validation

- `python -m pytest -q` -- 775 passed (1 new:
  `test_history_presenter_renders_natural_local_time_not_raw_iso`).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.404
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
