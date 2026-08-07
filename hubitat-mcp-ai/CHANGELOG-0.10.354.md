# Hubitat MCP AI 0.10.354

## Fixed

Four scheduling-grammar gaps found during a broad offline phrasing sweep
(~45 natural phrasings run against the deterministic rule-authoring
compiler with no live model or hub round-trip). None of these produced
wrong rules -- each one fell through to the general agent path silently,
so the user's request either got a slower, less predictable model-authored
answer or was declined outright.

- **Window-style control phrasing with no "at" clause was rejected before
  it ever reached the window grammar.** `"block internet for tab-s9-fe
  from 10pm to 6am every day"` returned NOT HANDLED even though it has an
  explicit window clause and daily marker. Root cause: the plain-control
  entry gate (`_intent()` in `rule_authoring_service.py`) required an
  `_AT_TIME` match for *any* unauthored phrasing, but window phrasing has
  no "at" clause at all -- only "from X to Y". Fixed by accepting either
  an `_AT_TIME` match or a `_WINDOW` match for plain-control phrasing.
  This is distinct from the already-fixed 0.10.351/0.10.352-era
  "order independent daily marker" case, which only covered phrasing that
  already said the word "rule".
- **A leading "please" broke device-name resolution.** `"please turn on
  livingroom light 1 at 7:05am"` failed to resolve the device name because
  the courtesy prefix was left in the goal slice and broke the verb-pattern
  fullmatch used to extract the device name. Fixed by stripping a leading
  `please` in `_clean_goal()`, in addition to the plain-control entry gate
  already allowing it.
- **"every single day" was not recognised as a daily marker**, so
  `"turn on livingroom light 1 every single day at 7am"` created a
  one-time rule instead of a recurring daily one. Fixed by extending the
  `_DAILY` regex.
- **"noon" and "midnight" were not recognised as clock times at all.**
  `"turn on livingroom light 1 at noon"` and `"...at midnight"` fell
  through entirely. Fixed by extending `AT_TIME` in `time_expressions.py`
  to accept these words and resolving them via a small fixed-word lookup
  in `parse_clock()`, checked before the existing numeric-parsing path.

## Context

All four gaps were found the same way: loading the production
`rule_authoring_service.py` and `time_expressions.py` modules directly
(via `importlib`) against a fixed device inventory and a fixed clock, and
running a broad matrix of natural phrasings through `_intent()` /
`propose()` with no live model or hub call. This lets grammar coverage be
checked quickly and deterministically, independent of any live hub or
model availability, and is a repeatable way to catch gaps like these
before a user hits them live.

## Validation

- `python -m pytest -q` -- 570 passed, including 6 new regression tests
  covering all four fixes above (`test_plain_window_control_phrasing_works_without_the_word_rule`,
  `test_plain_window_control_without_daily_marker_is_not_handled`,
  `test_leading_please_does_not_block_device_name_resolution`,
  `test_every_single_day_is_recognised_as_a_daily_marker`, and a
  parametrized `test_noon_and_midnight_are_recognised_clock_words`).
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.354.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Manual offline sweep of ~45 phrasings re-run after each fix to confirm
  no regressions against every previously-fixed case (0.10.349 period
  times, 0.10.350 auto-pause, 0.10.351 redundant trailing state word,
  0.10.352-era order-independent daily marker with the word "rule").
