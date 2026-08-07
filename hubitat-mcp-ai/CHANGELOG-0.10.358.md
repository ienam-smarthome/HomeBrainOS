# Hubitat MCP AI 0.10.358

## Fixed

Two real bugs found during the same live retest session that verified
0.10.357, both root-caused properly rather than patched around.

- **A one-time rule at a different time on the same day was wrongly
  treated as a duplicate of an earlier one and silently skipped.** Live
  test: "turn on toilet light at noon" was confirmed and created; a later
  "please turn on toilet light at 7am" replied "No duplicate rule was
  queued because this Rule Machine rule already exists" and did nothing.
  Root cause: the one-time rule name only encoded the calendar date
  (`"... (One-time 2026-08-08)"`), never the time, so any two distinct
  one-time requests for the same device and command on the same day
  produced an identical name and collided in the duplicate-name check.
  Fixed by including the time in the rule name suffix
  (`"... (One-time 2026-08-08 07:00)"`) in `rule_authoring_service.py`.

- **A device name typed without a hyphen the device's own label uses
  ("tab s9fe" for "Block Tab-S9-FE") was declined as ambiguous alongside
  two completely unrelated devices.** Root cause, in
  `device_target_resolver.py`: the label normalises "Tab-S9-FE" into
  separate tokens "tab", "s9", "fe", but a person naturally types the same
  code as one token ("s9fe") without reproducing the internal hyphen.
  Neither "s9" nor "fe" alone was similar enough to "s9fe" for the
  existing per-token typo tolerance, which capped the match's score into
  ambiguous territory even though nothing else was a remotely plausible
  match (the two other candidates scored barely half as high). Fixed with
  two changes: `_specific_tokens_compatible` now also accepts a wanted
  token that appears as a contiguous run inside the candidate's
  concatenated specific tokens (handling exactly this hyphen-splitting
  shape, not general fuzzy substring matching), and
  `resolve_device_candidate` gained a second, stricter acceptance tier --
  a moderate absolute score can still resolve automatically if it beats
  the runner-up by a much wider margin (0.25 instead of the normal 0.12),
  since a low score caused only by tokenization shouldn't be penalised the
  same as genuine ambiguity between two real candidates.

## Context

Both bugs were found via direct live retesting after 0.10.357's fix was
confirmed working, not through the offline grammar sweep -- they're a
different class of problem (rule-name collision, fuzzy-match scoring) from
the natural-language grammar gaps fixed earlier in this session. Both were
root-caused to the actual mechanism before any fix was written, per the
project's own standard, rather than patched around symptomatically.

## Validation

- `python -m pytest -q` -- 577 passed, including a new duplicate-name
  regression test
  (`test_two_one_time_requests_for_different_times_the_same_day_are_not_duplicates`)
  and two new resolver tests
  (`test_hyphenated_device_code_typed_without_hyphens_still_resolves`,
  `test_dominant_margin_does_not_paper_over_genuine_ambiguity` -- the
  latter confirms the new acceptance tier does not swallow real ambiguity
  between two similarly-named candidates).
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.358.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Not yet re-verified live -- pending the user re-running both originally
  failing phrases after this update is deployed.
