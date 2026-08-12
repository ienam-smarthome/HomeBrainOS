# 0.10.418

## Why this release

Live testing immediately after 0.10.417 confirmed "disable humidity
controller app" now works end-to-end (confirmation prompt, then "The
Humidity Controller app has been disabled."). The very next request in
that same session, "enable it" -- clearly meaning "re-enable the app I
just disabled" -- failed with "I could not find a device that supports
allowing internet access matching \"it\"".

## Fixed

**A bare pronoun target ("it", "that", "this device", ...) is no longer
treated as a literal device name for block/allow-internet requests.**
`parse_immediate_internet_access_intent`'s target-extraction had no
pronoun exclusion at all -- unlike device-control follow-ups elsewhere in
this codebase, which already substitute the session's last selected
device for a pronoun via `is_pronoun_reference()`. "enable it" fullmatched
the allow-internet pattern with `target="it"` and dispatched a doomed
device-inventory search for a device literally named "it", guaranteeing
the confusing failure above. This deterministic path now excludes bare
pronoun targets the same way it already excludes "app"/"apps" wording
(0.10.417), letting the request fall through to the model's own
tool-calling loop instead.

Note this is a partial fix, not a full "it" resolution: there is no
session tracking of "the last app acted on" anywhere in this codebase
(only device selections are tracked), so "enable it" now gets a real
chance via the model loop rather than a guaranteed nonsense error, but
is not guaranteed to resolve correctly end-to-end without conversation
context. Tracking the last app name is a larger, separate change and is
noted as a possible future improvement rather than folded into this fix.

## Validation

- `python -m pytest -q` -- 865 passed. New coverage in
  `test_internet_access_hardening.py`: "enable it" / "block that" /
  "allow this device" all fall through to `None` instead of being parsed
  as a literal device-name target.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.418
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
