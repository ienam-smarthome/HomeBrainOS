# Hubitat MCP AI 0.10.357

## Fixed

- **The prompt-only fix in 0.10.356 was not enough.** Live retest of the
  exact same phrase (`"turn off toilet light and restart the hub"`) after
  deploying 0.10.356 showed the model still folded "and restart the hub"
  into `device_names` on a single `homebrain_control_devices` call, exactly
  as before. The deterministic resolver still refused to guess a device
  (fail-closed, nothing wrong executed), but the light still didn't turn
  off. This confirms steering the model's behaviour through the system
  prompt alone is not reliable enough for this local model on this
  phrasing.

  Added the deterministic backstop flagged as the likely next step in
  0.10.356's own changelog: `device_control_service.py` now recognises a
  short, closed set of clearly distinct second actions smuggled onto the
  end of a device name or room string -- restart/reboot the hub, lock/
  unlock a door, arm/disarm the alarm -- via
  `strip_trailing_unrelated_action()`, strips it before device resolution,
  and executes the routine action against the correctly-cleaned name. The
  result now carries a `note` telling the user the second action ("restart
  the hub") was not part of this device action and needs its own request.

  This follows the exact pattern already established in this file for a
  smuggled time expression (`strip_trailing_time`, added earlier this
  session): detect and cleanly separate text that doesn't belong in a
  device name, rather than letting it corrupt resolution or silently
  vanish. Unlike the time case, this one still executes the (now-correctly
  resolved) routine action, because there's no ambiguity about intent for
  that half of the request -- only the second, distinct action is withheld,
  and only because auto-executing it from a regex match rather than a
  model-selected tool call would violate this codebase's own rule that
  mutations must be gated on structured tool calls, never on raw prompt
  text.

## Context

The 0.10.356 prompt clarification is left in place -- it may still help on
other phrasings or other models -- but this project's own philosophy
("the model must not invent Hubitat's `hub_set_rule` JSON," extended here
to "the model cannot be fully trusted to correctly split a compound
sentence into separate tool calls either") means the deterministic layer
needed to carry the actual guarantee. The stripped action is intentionally
never auto-executed: this only handles the narrow, previously-reported
failure mode (a routine action silently not happening because it got
smuggled into an unrelated call's arguments), not general compound-request
handling.

## Validation

- `python -m pytest -q` -- 574 passed, including two new tests
  (`test_smuggled_second_action_is_stripped_and_the_routine_part_still_runs`,
  `test_ordinary_device_name_with_no_second_action_is_unaffected`)
  confirming the routine action executes against the cleaned device name,
  the hub is never actually restarted from the regex match, and ordinary
  device names with no second action are unaffected.
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.357.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Not yet re-verified live -- pending the user re-running the same
  originally-failing phrase after this update is deployed.
