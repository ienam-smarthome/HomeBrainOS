# Hubitat MCP AI 0.10.350

## Added

- **One-time scheduled rules now auto-pause themselves after their first
  fire.** Follows up on the open, unconfirmed question from the 0.10.346
  changelog: a live scheduler job inspected during development for a
  dated "Certain Time (and optional date)" trigger still carried a
  `"recurring": true` label internally, despite the trigger having a full
  calendar date -- Hubitat's own documented behaviour says a dated trigger
  fires once and does not recur, but that internal label left the question
  open without leaving a rule running unattended long enough to observe a
  possible second fire directly.

  Rather than continue waiting on that, one-time rule proposals
  (`RuleAuthoringService.propose()`, in the non-recurring branch) now queue
  a second action alongside the create: a native Hubitat `pauseRule`
  action (`capability='pauseRule', action='pause', ruleIds=[...]`) that
  pauses the rule immediately after it runs. Even if the underlying
  scheduler job did try to fire the rule again, a paused rule cannot
  execute its actions -- closing the ambiguity with a belt-and-suspenders
  fix instead of a definitive root-cause explanation for Hubitat's own
  scheduler internals.

  `pauseRule` requires an existing rule id, which doesn't exist yet at
  proposal time (the rule the action pauses hasn't been created). Both the
  edit target (`appId`) and the action's own `ruleIds` are built with a new
  placeholder (`NEW_RULE_ID_TOKEN`), which `ConfirmedActionCoordinator`
  substitutes with the real appId returned by the immediately preceding,
  verified create action before executing the follow-up. This keeps the
  confirmed action group fully pre-built and auditable at confirmation
  time (the user sees "2 sensitive Hubitat actions" and can decline), while
  still letting the second action depend on the first's real-world result.

  Daily/recurring rules are unaffected -- they still need to fire every
  day, so no pause follow-up is queued for them.

  Verified live end-to-end against the connected hub before writing any
  code: created a throwaway one-time rule, confirmed the exact
  `hub_set_rule(appId=<id>, addAction={capability: 'pauseRule', ...})`
  payload shape is accepted and reports `success: true` with a healthy
  verification envelope, then deleted the throwaway rule.

## Context

- This was a user-requested design choice with two options presented:
  auto-pause (chosen) leaves the rule visible and inspectable in Rule
  Machine in a paused state, versus auto-delete which would remove it
  entirely. Auto-pause was chosen for reversibility and auditability.
- While investigating, the two rules created live during 0.10.348 testing
  were checked: the daily rule (appId 4169) is still present and active as
  expected. The one-time rule (appId 4170) was found already gone from the
  live Rule Machine rule list (reported by the hub as a "post-delete
  RMUtils-cache ghost"). Whether that was the user deleting it manually or
  Hubitat cleaning it up automatically after its trigger time passed could
  not be determined from the evidence available, and is not claimed either
  way -- it does not change the case for this fix, since the internal
  `"recurring": true` scheduler label observed earlier is still unexplained
  either way.

## Added (tests)

- `tests/test_rule_authoring_service.py`:
  `test_one_time_proposal_queues_a_self_pause_followup_action` and
  `test_daily_proposal_does_not_queue_a_self_pause_followup_action` --
  confirm the pause action is queued only for one-time proposals, with the
  correct placeholder shape.
- `tests/test_confirmed_action_coordinator.py`:
  `test_one_time_rule_pause_followup_resolves_placeholder_to_real_appid`
  and `test_one_time_rule_pause_followup_failure_is_reported_distinctly`
  -- prove the placeholder never reaches the hub, both occurrences are
  substituted correctly, and reporting is accurate whether the follow-up
  pause succeeds or fails (a failed pause must not be reported as if the
  whole write failed -- the rule was still created).
- `tests/_entity_first_orchestrator_cases.py`:
  `test_one_time_rule_end_to_end_creates_then_self_pauses` -- full round
  trip from a plain user prompt through confirmation to execution, proving
  the feature works at the level the user actually interacts with it.

## Validation

- `python -m pytest -q` -- 567 passed (562 from 0.10.349 + 5 new).
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.350.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Live-verified the exact `pauseRule` payload shape against the connected
  hub using a throwaway test rule (created, paused, then deleted).
