# Hubitat MCP AI 0.10.360

## Added

- **"Recommend useful automations for my home" now gets a genuine model-
  synthesized answer, not just a deterministic capability-gap checklist.**
  0.10.359 widened the gap analysis to more device kinds, but live
  retesting on a heavily-automated real hub (179 existing apps/rules)
  showed it still couldn't produce anything for a home where nearly every
  motion sensor, lock, and contact sensor already has *some* automation
  referencing it by name -- there was no capability-list gap left to find,
  even though a human (or a general-purpose assistant) can obviously still
  suggest themed ideas like "away/security mode" or "consolidate the
  homework routine" by reasoning across the whole device inventory. That
  synthesis is fundamentally not reducible to a checklist, no matter how
  many capabilities the checklist covers.

  Added a new, narrowly-scoped module, `automation_ideas_service.py`,
  that asks the configured model directly -- in one plain, non-tool-
  calling round -- for creative suggestions grounded only in the real,
  already-fetched device manifest and existing automation names. It
  explicitly instructs the model never to claim anything about current
  device state as fact, only to propose ideas. Because it never makes a
  factual claim, it deliberately does not go through
  `UnifiedMCPAgent`'s tool-calling loop or its strict evidence-required
  grounding policy (`grounding_policy.py`) -- that policy exists to stop
  unverified factual claims, not clearly-labelled suggestions.
  `AutomationStatusService` itself is untouched and remains fully
  deterministic, exactly as its own docstring requires ("without relying
  on LLM formatting"); the new capability lives entirely in the new
  module and is only invoked for a request classified as wanting new
  ideas specifically (`AutomationStatusService.wants_new_automation_ideas`),
  never for a request to review or audit existing automations.

  If the model call fails for any reason (missing API key, timeout,
  malformed response, no devices to ground it in), the deterministic
  gap-analysis message from 0.10.359 is returned completely unchanged --
  this can only ever add to the response, never break it.

## Context

This closes a three-round investigation: 0.10.359 widened the
capability-gap checklist (a legitimate but bounded improvement), and this
release adds the piece that checklist-widening could never provide --
actual reasoning across the full device inventory. The routing decision
that sends "recommend automations" phrasing to `AutomationStatusService`
at all was a deliberate earlier fix (see that service's own test
comments) and was left untouched; only the content behind the specific
"wants new ideas" sub-case changed.

## Validation

- `python -m pytest -q` -- 588 passed, including:
  - 4 new tests in `test_automation_ideas_service.py` covering a grounded
    success case (asserting the model call is non-tool-calling, includes
    the real device manifest and existing automation names, and instructs
    against factual claims), a chat-failure fail-closed case, a
    no-devices-to-ground-it case, and a blank-response case.
  - 2 new integration tests in `test_app_endpoints.py`: one confirming
    "recommend useful automations for my home" routes to the new
    creative-suggestion path and gracefully falls back to the
    deterministic message when the model call fails; one confirming a
    request to review *existing* automations still uses the plain
    deterministic snapshot and never calls the model.
  - `AutomationStatusService.wants_new_automation_ideas()` classifier
    tested directly against both new-idea and existing-review phrasings.
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.360.
- `python scripts/analyze_imports.py` -- zero orphan modules (new module
  registered in `docs/RUNTIME-MODULE-MAP.md`).
- Not yet re-verified live -- pending the user re-running "recommend
  useful automations for my home" after this update is deployed.
