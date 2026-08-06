# Hubitat MCP AI 0.10.343

## Fixed

- "Recommend useful automations for my home" (and similar advisory
  phrasing -- "suggest improvements", "review my automations", "clean up
  my automations") fell through the deterministic `automation-status`
  gate entirely, because `matches_request()` only recognised literal
  status-listing words ("list", "show", "which", "status", "active",
  "disabled", "paused", "broken"). The request landed in the generic
  model loop instead, which took 11.8s and then refused outright --
  the only tool evidence it produced (an app-manifest priming call) is
  deliberately marked as not supporting a live claim, so grounding
  correctly saw zero usable evidence even though real, current data
  (172 automation items) genuinely had been fetched moments earlier.
- `matches_request()` now also recognises advisory-intent words
  ("recommend", "suggest", "advice", "improve", "review", "clean up",
  "audit") alongside the subject check, routing these requests through
  the same reliable, grounded `snapshot()` fetch that "list automations"
  already used successfully.
- Advisory-phrased requests get a new, more useful response instead of
  the raw item-by-item listing: broken automations first ("worth fixing
  first"), disabled ones next ("worth a look if any are still
  relevant"), and an honest note that this reflects what's already
  configured rather than inventing brand-new automation ideas from the
  device inventory (a capability this doesn't have yet).

## Found via

- Live testing: the reported prompt was exactly "Recommend useful
  automations for my home", which returned `Refused` after 11.8s with
  "I could not retrieve verified live Hubitat evidence, so I will not
  provide an inferred answer" -- despite `hub_list_apps` having
  genuinely succeeded and returned all 172 real automation items in the
  same request.
- Also checked and ruled out as a false lead: "0 motion sensors active"
  alongside "4 active rooms" looked like a possible inconsistency, but
  `active_room_summary()` defines a room as active when it has a light
  on *or* active motion -- the 4 active rooms in that test session
  exactly matched the 4 rooms with lights on, confirming this is
  correct, self-consistent behavior, not a bug.

## Validation

- Adds `tests/test_automation_status_advisory.py`: gate-matching for
  advisory phrasing, the exclusion guard still applying, and the new
  advisory message builder (broken/disabled highlighting, truncation of
  long disabled lists, the honest new-ideas caveat, empty-inventory
  handling).
- `python3 -m pytest -q` (539 passed).
- `python3 scripts/validate_addon.py` and `analyze_imports.py` both clean.

## Not fixed here (scoped out, flagged for later)

- This does not add the ability to suggest genuinely *new* automations
  by cross-referencing the device inventory against existing automation
  coverage (e.g. "you have a front door sensor but no automation reacting
  to it at night"). That's a real, larger feature -- correlating devices
  with automation gaps -- not a bounded fix, and the advisory message
  says so explicitly rather than overclaim.
