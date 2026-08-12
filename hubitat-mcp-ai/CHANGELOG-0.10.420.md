# 0.10.420

## Why this release

Live testing right after 0.10.419's crash fix confirmed "enable it" no
longer returns a 500 -- but it still didn't work correctly. Instead, the
confirmed action failed: `hub_manage_native_rules_and_apps did not
succeed: Invalid params: appId must be a positive integer (got: '01.
Humidity Controller')`. The model had passed the app's numbered display
label as the literal `appId` argument instead of its real numeric ID.

## Fixed

**A pronoun follow-up to an app request no longer omits the app
manifest.** The system prompt only includes the live app-name-to-ID
manifest (the thing that tells the model "Humidity Controller" maps to
numeric `appId: 3995`) when the *current* prompt contains app-related
wording ("app", "pause", "resume", "rule", ...). "enable it" has none of
that wording on its own, so the manifest was omitted entirely, and the
model -- with no correct ID to reference -- guessed using the numbered
label text it had seen earlier in the conversation, which the gateway
correctly rejected. The system prompt builder now also checks the most
recent prior user turn for app wording, the same way device pronoun
follow-ups elsewhere in this codebase already resolve against session
context, so a follow-up like "enable it" right after an app-related
request still gets the manifest it needs to reference the correct ID.

## Validation

- `python -m pytest -q` -- 868 passed. New coverage in
  `tests/_entity_first_orchestrator_cases.py`: a pronoun follow-up right
  after an app-related prior turn still receives the app manifest with
  the correct numeric ID; an unrelated pronoun follow-up (e.g. after a
  device question) does not needlessly pull in the app manifest.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.420
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
