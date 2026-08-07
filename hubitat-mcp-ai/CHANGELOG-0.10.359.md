# Hubitat MCP AI 0.10.359

## Fixed

- **"Recommend useful automations for my home" gave the wrong kind of
  answer.** Live test on the real hub (91 devices, 179 existing apps/
  rules) routed correctly to `AutomationStatusService` (this routing was
  a deliberate earlier fix, kept as-is -- see that service's own test
  comments) but produced only a plain broken/disabled status dump plus an
  honest "I don't yet have a way to suggest brand-new automation ideas"
  caveat, because the gap analysis behind any real suggestion was scoped
  to three safety capabilities only (`WaterSensor`, `SmokeDetector`,
  `CarbonMonoxideDetector`), and none happened to be uncovered on this
  hub. The user's complaint, confirmed via a clarifying question, was
  "wrong kind of answer": they wanted genuine new-automation ideas, not an
  audit of existing ones.

  Fixed by broadening the same grounded, name-match gap analysis (never
  invents a device or automation -- only cross-references real retrieved
  data) to four more common device kinds where a specific automation is
  well understood: `MotionSensor` (motion-activated light), `ContactSensor`
  (door/window-left-open alert), `Lock` (auto-lock after being left
  unlocked), and `PresenceSensor` (arrival/departure automation). The
  "Real gap" suggestion section also now leads the response, ahead of the
  broken/disabled diagnostic dump, since it's the direct answer to what was
  actually asked. The old "safety-only" analysis is preserved unchanged
  under its original name and tests for callers that still want just that.

## Context

This was not blindly re-patched: the routing itself (recommend + automation
words -> `AutomationStatusService`) was deliberately added in an earlier
fix specifically to avoid a worse outcome (falling through to the general
model loop, which previously took 11.8s and then refused outright). That
fix and its regression test were left untouched. Only the *content* of the
advisory response was widened, since the actual problem was the narrow
capability list, not the routing decision.

## Validation

- `python -m pytest -q` -- 582 passed, including 5 new tests in
  `test_automation_status_advisory.py` covering the broadened capability
  set, exclusion of already-named devices, the exact live-failure scenario
  (motion sensor + lock with no safety-capability device present),
  suggestion ordering ahead of the broken list, and confirming the "can't
  invent new ideas" caveat still appears when genuinely nothing is found.
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.359.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Not yet re-verified live -- pending the user re-running "recommend
  useful automations for my home" after this update is deployed.
