# Hubitat MCP AI 0.10.349

## Fixed

- **Scheduled times with a period separator silently lost their minutes.**
  Live testing of 0.10.348 found "turn on livingroom light 1 every day at
  11.25" and "turn on livingroom light 1 at 11.23" both succeeded and
  created real Rule Machine rules -- but each rule's trigger read "When
  time is 11:00 AM," not 11:25 or 11:23. The requested minutes were
  dropped without any error or warning.

  Root cause: `AT_TIME`'s time-capture group
  (`\d{1,2}(?::\d{2})?...`) only recognised a colon as the separator
  between hour and minute. For "at 11.25", the regex engine matched the
  hour digits "11", then found the optional `:\d{2}` group didn't apply
  (next character is a period, not a colon), then hit a word boundary
  right before the period and stopped there -- capturing only "11" and
  silently discarding ".25". `parse_clock("11")` then correctly parsed
  that as a bare hour with an implicit `:00`, because a bare hour is a
  legitimate, intentional input elsewhere (e.g. "at 7" meaning 7:00) --
  there was nothing left in the captured string to tell it a minute had
  been typed and lost.

  Both `AT_TIME` and `parse_clock` (in `time_expressions.py`, the single
  shared module both `rule_authoring_service.py` and
  `device_control_service.py` depend on for clock parsing) now treat a
  period between an hour and a two-digit minute as an equally valid
  separator to a colon. This required care: `parse_clock` already strips
  periods elsewhere in the string to normalise "a.m."/"p.m." spellings, so
  the fix normalises a genuine `HH.MM` separator to `HH:MM` *before* that
  blanket period strip runs, rather than conflating the two. Verified this
  does not regress am/pm-with-dots parsing ("7 p.m.", "7a.m." both still
  parse correctly).

## Context

- UK-style time notation ("11.25" for 11:25) and simple typing habits
  (period instead of shift-colon) are common enough that this is a
  meaningful usability gap, not an edge case -- the two failures reported
  live were both period-separated times entered in normal conversational
  phrasing.
- Two real Rule Machine rules were created on the live hub during this
  testing round with the wrong trigger time (appId 4169 "Turn on
  Livingroom Light 1 (Daily)" at 11:00 instead of 11:25, and appId 4170
  "Turn on Livingroom Light 1 (One-time 2026-08-07)" at 11:00 instead of
  11:23). This fix does not touch already-created rules; those two are
  left for the user to review, correct the trigger time on, or delete via
  the app's own Rule Machine UI as they see fit.

## Added

- `tests/test_time_expressions.py`:
  `test_parse_clock_handles_period_separated_minutes` and
  `test_at_time_captures_period_separated_clock_expressions` -- cover the
  exact reported inputs ("11.25", "11.23"), a period-separated time with
  am/pm ("11.25pm"), and confirm the existing dotted am/pm spellings
  ("7 p.m.", "7a.m.") still parse correctly and are not misread as
  minute separators.

## Validation

- `python -m pytest -q` -- 562 passed (560 from 0.10.348 + 2 new).
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.349.
- `python scripts/analyze_imports.py` -- zero orphan modules.
