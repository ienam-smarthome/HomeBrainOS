# Hubitat MCP AI 0.10.346

## Fixed

- Recurring-rule requests never reached `RuleAuthoringService`. In
  `homebrain_agent.py`'s deterministic dispatch chain,
  `routine_control_arguments()` matched any "turn on/off X" phrasing --
  including "turn on livingroom light 1 every day at 10:05am" -- and
  short-circuited straight to the instant control fast path before
  `base_process()` (where `RuleAuthoringService.propose()` runs) was ever
  reached. The app's own decline message advertised "I can... set up a
  recurring daily rule for that time," but that path was unreachable
  through the phrasing the message itself suggested. A prompt carrying an
  "at &lt;time&gt;" clause now skips the instant fast path and falls
  through to `base_process()` so rule authoring gets a real chance to run.
- Found while tracing the above: `mcp_agent_orchestrator.py` defined
  `_routine_control_fallback()`, a method with no call sites anywhere in
  the codebase (including tests). It read like the intended integration
  point for exactly this behaviour and was never wired in. Removed as
  dead code, along with the `_SENSITIVE_TERMS` constant that existed only
  to serve it.

## Added

- One-time scheduled actions ("turn on livingroom light 1 at 10:05am",
  no "daily"/"every day"/"rule"/"schedule" wording required) are now
  compiled into a real Hubitat Rule Machine trigger, not just declined.
  `RuleAuthoringService._intent()` no longer requires the literal word
  "rule"/"automation"/"schedule" -- a plain control verb ("turn on",
  "switch off", "lock", "block", etc.) combined with an "at &lt;time&gt;"
  clause is recognised on its own, matching how someone would actually
  phrase this rather than requiring authoring jargon. Recurring vs.
  one-time is decided solely by whether a daily marker
  ("daily"/"every day"/"everyday") is present in the request.
- The distinction is expressed in the Hubitat trigger itself, not just in
  this app's own bookkeeping: a recurring request emits `atTime` as a
  bare `'HH:MM'` (Hubitat's daily-recurring form, unchanged from before),
  while a one-time request resolves the next real occurrence of that
  clock time (today if it hasn't passed yet, otherwise tomorrow -- via
  the newly injectable `RuleAuthoringService(..., now=...)` clock) and
  emits a full `'YYYY-MM-DDTHH:MM:SS'` `atTime`, Hubitat's "Certain Time
  (and optional date)" one-time form. `tool_registry.py`'s
  `rule_machine_proposal_error` validator now accepts both `atTime`
  shapes (previously only bare `HH:mm` passed validation at all, which
  would have rejected a one-time proposal outright even after the intent
  layer learned to build one). Created rules are named distinctly --
  `"... (Daily)"` vs. `"... (One-time YYYY-MM-DD)"` -- so duplicate
  detection and Rule Machine's own listing don't conflate the two.
- `device_control_service.py`'s smuggled-time refusal message (still the
  last-resort guard for a time embedded in a tool call the model makes
  directly, now that `RuleAuthoringService` handles the common phrasing
  earlier) no longer claims one-time scheduling is unsupported, and
  suggests the exact rephrasing that will work.

## Context

- Requested directly after live-testing 0.10.345 against a real hub: "turn
  on livingroom light 1 every day at 10:05am" returned the same generic
  decline on every attempt, and checking the hub directly (`hub_list_rules`)
  confirmed no rule was ever created. Tracing the dispatch chain found the
  actual root cause described above, plus the dead-code method that looked
  like it should have been the fix.
- Also requested: closing the gap between this app's capability and what a
  general MCP-connected assistant can already do for one-off scheduled
  actions, not just recurring ones.

## Scope, stated honestly

- **Verified live, but one open question remains.** I created a real
  one-time rule on a live hub via `hub_set_rule` with a full-date `atTime`
  (`"2026-08-09T03:00:00"`) and confirmed it was accepted and scheduled
  exactly once for that timestamp (`hub_get_jobs` showed one scheduled
  entry at that exact date/time, not a spread of daily occurrences).
  However, that same job listing labelled the underlying Hubitat scheduler
  entry `"recurring": true` even though a specific calendar date was
  supplied -- Hubitat's internal `...Recur.<method>` job-naming convention
  is not, on this evidence alone, a reliable signal for whether the trigger
  will actually re-fire on a later day. I deleted the test rule immediately
  after this check (a pre-delete backup was taken automatically) rather
  than wait to observe a real second firing, so **true non-recurrence past
  the first scheduled fire is not yet empirically confirmed** -- only that
  the rule fires correctly once, at the right time, doing the right thing.
  If a one-time rule created by this feature is later seen to fire again
  the next day, that is the open question landing; please report it, and
  the safe follow-up is a `hub_manage_rule_machine(pauseRule)` action
  appended to the rule right after its first (observed) run.
- A one-time rule is not auto-deleted or auto-paused by this app after it
  fires -- Hubitat does not offer that natively through the create call
  used here, and adding it would require a second `hub_set_rule` edit call
  chained on the first call's returned `appId`, which the current
  confirmation/execution pipeline does not support (it runs a static,
  pre-planned action list, not one action whose arguments depend on a
  prior action's result). The created rule will remain listed in Rule
  Machine (harmlessly, pending the point above) until manually removed.
- The auto-revert window grammar ("...from 10pm to 6am") still requires
  the daily marker, as before -- a one-time version of that pattern (turn
  off tonight, turn back on tomorrow morning, just once) is not
  implemented.

## Validation

- Adds `tests/test_rule_authoring_service.py` coverage for: plain daily
  phrasing without the word "rule"; plain one-time phrasing producing a
  dated single-shot rule; the today-vs-tomorrow rollover via the injected
  `now` clock; and that a daily and a one-time rule for the same
  device/command get distinct names.
- Adds `tests/test_tool_effect_registry.py` coverage for the new
  ISO-datetime `atTime` form being accepted, and confirms malformed forms
  (bare date, space-separated, missing seconds, empty) are still rejected.
- Adds `tests/test_homebrain_agent.py` coverage asserting a prompt with an
  "at &lt;time&gt;" clause never reaches the instant control fast path
  (`_control_devices`) and does reach `base_process()`, and that an
  ordinary immediate command is unaffected and still uses the fast path.
- `python3 -m pytest -q` (558 passed).
- `python3 scripts/validate_addon.py` and `scripts/analyze_imports.py`
  both clean (zero orphan modules after the dead-code removal).
- Live-tested against a real Hubitat hub: created and inspected an actual
  one-time Rule Machine rule (see "Scope, stated honestly" above), then
  deleted it.
