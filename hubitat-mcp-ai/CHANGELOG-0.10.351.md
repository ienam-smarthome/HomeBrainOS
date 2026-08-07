# Hubitat MCP AI 0.10.351

## Fixed

- **A redundant trailing "on"/"off" got folded into the device name.** Live
  testing found "turn on livingroom light 1 on at 12.05" declined as
  ambiguous, offering "Livingroom Light 1", "Livingroom TRV", and
  "Livingroom Soft Sensor" as choices, instead of resolving cleanly.

  Root cause: `RuleAuthoringService._single_intent()`'s first (greedy)
  pattern for "turn on" phrasing -- `^turn\s+on\s+(?P<target>.+)$` --
  matches before any of the more specific alternatives get a chance, and
  its `.+` target group swallows everything after "turn on ", including an
  accidental repeated "on" right before the time clause. The extracted
  target became the literal string "livingroom light 1 on", which matched
  no real device, so device resolution fell back to weak fuzzy alternatives
  across every device with "Livingroom" in its name.

  This is a natural typo, not malformed input -- "turn on X" phrasing
  combined with the habit of saying "X on at TIME" produces "turn on X on
  at TIME" without the speaker noticing the duplication. Added a
  normalisation step that collapses a trailing state word into nothing
  when it exactly duplicates the leading verb's state ("turn on X on" ->
  "turn on X", "turn off X off" -> "turn off X", "switch on X on" ->
  "switch on X"), before the existing pattern list runs unchanged.

  Deliberately narrow: only collapses when the trailing word is an *exact*
  duplicate of the leading state ("on"...on" or "off"...off"). A device
  that happens to end in "switch" or "off" (e.g. "porch light on switch")
  is untouched, and self-contradictory phrasing ("turn on X off") is left
  alone rather than guessed at -- it still fails device resolution
  honestly instead of being silently reinterpreted as either state.

## Added

- `tests/test_rule_authoring_service.py`:
  `test_redundant_trailing_state_word_is_not_folded_into_device_name`
  (covers the exact reported "on"/"off" duplicate cases for both turn and
  switch phrasing) and
  `test_mismatched_trailing_state_word_is_left_untouched` (proves
  self-contradictory "turn on X off" phrasing is not silently
  reinterpreted as either state).

## Validation

- `python -m pytest -q` -- 569 passed (567 from 0.10.350 + 2 new).
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.351.
- `python scripts/analyze_imports.py` -- zero orphan modules.
