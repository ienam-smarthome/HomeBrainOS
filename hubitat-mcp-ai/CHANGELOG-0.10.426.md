# 0.10.426

## Why this release

Direct follow-up to the live stress-test run against 0.10.425: after applying
that release, the user ran the full reasoning-mode test list and reported
every category correct except one pair -- "When did the front door last
open?" and its "and when did it close before that?" follow-up both answered
"No contact events were reported for Front Door in the last 24 hours," which
contradicted the very same test session's own "How many times did the front
door open yesterday?" answer, which had just shown real Front Door contact
events within the last 48 hours.

## Fixed

**A "last X" point question was silently bounded to a 24-hour window it was
never meant to have.** `homebrain_device_history`'s tool description already
told the model to scope a "when was X last opened/closed/on/off" question to
a specific `attribute` with a small `limit` so the answer is the event
itself, not an unfiltered dump -- and the model did exactly that. But nothing
told it to also widen `hours_back`, so it silently inherited the tool's
generic 24-hour default, meant for open-ended "what happened" reviews, not
for a "most recent occurrence, whenever it was" question. When the real last
matching event happened to be more than a day old, the read came back empty
and the model correctly, but wrongly, reported "no events" -- a plausible
answer that was actually a false negative.

`DeviceHistoryService.history()` now widens its own default: when the caller
sets `attribute` but leaves `hours_back` unset, the effective window becomes
the full seven-day bound instead of one day. An explicit `hours_back` still
always wins. This costs nothing in the common case -- the result stays
capped by `limit` (small, per the tool's own guidance for point questions),
so a genuinely recent event is reported exactly as before. Only the false
"no events" negative for an older-than-a-day last occurrence goes away.

Unscoped queries (no `attribute` -- a broad "what happened" review, not a
point question) are unaffected and keep the original 24-hour default.

## Validation

- `python -m pytest -q` -- 878 passed. New coverage in
  `tests/test_device_history_service.py`:
  `test_attribute_scoped_query_widens_default_window_to_seven_days`
  reproduces the exact live-reported bug shape (attribute set, `hours_back`
  left unset); `test_unscoped_query_keeps_the_original_twenty_four_hour_default`
  and `test_explicit_hours_back_still_overrides_attribute_default` pin the
  two cases that must stay unchanged. Confirmed the new widening test fails
  against the pre-fix code (`hoursBack` came back `24` instead of `168`)
  before restoring the fix.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.426
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
