# 0.10.422

## Why this release

0.10.421's safety fix worked exactly as intended: instead of fabricating
"Enabled the app", a live retest correctly returned "did not succeed:
Invalid params: appId must be a positive integer (got: '01. Humidity
Controller')". But that surfaced that the underlying bug 0.10.420 aimed to
fix -- the model passing an app's display label instead of its numeric
`appId` -- was still happening, for the exact "disable X app" -> confirm
-> "enable it" sequence 0.10.420 was written for.

## Fixed

**The app-manifest lookback only checked one turn back, but a "confirm"
reply always sits in between.** 0.10.420 made the system prompt also check
the most recent prior user turn for app wording, so a bare pronoun
follow-up like "enable it" could still get the live app-name-to-ID
manifest. That works when the app-mentioning turn is immediately before
the follow-up -- but every sensitive app mutation (like disabling an app)
requires a "confirm" round-trip first. In the real sequence -- "disable
humidity controller app" -> assistant asks to confirm -> user replies
"confirm" -> disable succeeds -> "enable it" -- the single most recent
prior user turn is the bare word "confirm" from finishing the *previous*
action, not the "...app" wording that actually named it. The one-turn
lookback landed on "confirm", found no app wording, and omitted the
manifest exactly as before, so the model guessed the appId again.

The lookback now skips past bare confirmation replies (the same
`CONFIRM_WORDS` the confirmation store itself already recognizes -- "confirm",
"confirmed", "proceed", "yes", "yes proceed", "do it") and keeps walking
back through the turn history until it finds a user turn that isn't just a
confirmation, then checks that one for app wording.

## Validation

- `python -m pytest -q` -- 870 passed. New coverage in
  `tests/_entity_first_orchestrator_cases.py`
  (`test_pronoun_follow_up_after_a_confirm_round_trip_still_gets_the_app_manifest`)
  reproduces the exact live sequence: "disable humidity controller app" ->
  confirm prompt -> "confirm" -> disable succeeds -> "enable it" still
  receives the live app manifest with the correct numeric ID. Confirmed
  this test fails against the pre-fix single-turn lookback (reverted
  locally to verify) before restoring the fix.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.422
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
