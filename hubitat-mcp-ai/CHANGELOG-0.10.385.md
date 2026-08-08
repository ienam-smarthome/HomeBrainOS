# 0.10.385

## Why this release

Live-tested right after 0.10.384: "turn on livingroom light" (ambiguous
between two real lights) came back `"Command sent but state verification
failed: Livingroom TRV."` -- the assistant had turned on a thermostat
radiator valve, not either of the two real Livingroom lights. Reported
live with a screenshot and "it worked - but review the attached" about
the exclusion feature test, surfacing this as a separate, more serious
bug found in passing.

## Fixed

**Root cause 1 -- `device_kind="auto"` silently excluded every light from
the live-lookup fallback paths.** Every plain "turn on/off `<name>`"
request carries `device_kind="auto"` (see `routine_control_arguments()`),
meaning "match either a switch or a light." The fast, identity-cache-based
resolution path (`identity_candidates`) has always applied that
three-way rule correctly (light-only / switch-only / either), but three
separate live-lookup fallback sites in `device_control_service.py` --
used whenever resolution has to fall back to a live `hub_read_devices`
call instead of the cache -- carried an older two-way copy of the same
rule that only recognised `"light"` vs. "switch and not light," silently
treating `"auto"` the same as `"switch"` and dropping every light-capable
device from the candidate pool. `"turn on livingroom light"` needed
exactly that fallback (an ambiguous match against the cache), and once
the real lights were filtered out, the only device left with a
plausible fuzzy-name match was **Livingroom TRV** -- a thermostat
radiator valve that happens to also advertise `Switch` and share
"Livingroom" in its label.

The fix replaces all four ad hoc copies of this rule -- one already
correct, three buggy -- with a single new `DeviceControlService._matches_kind()`
method, the one and only place this three-way rule is expressed now.

**Root cause 2 -- a legitimate ambiguous result got silently overridden by
a noisier, broader retry.** Once real lights were excluded (root cause 1),
resolving `"livingroom light"` against the narrow, labelFilter-scoped
candidate set correctly came back *ambiguous* (Livingroom Light 1 vs.
Livingroom Light 2 -- a real, useful judgement call). But the per-name
fallback loop retried unconditionally against the *entire* house
inventory whenever the narrow attempt didn't return a single confident
target, regardless of whether that narrow attempt was "ambiguous between
good candidates" or "found nothing at all" -- discarding a legitimate,
worth-surfacing ambiguous result in favour of a blind fuzzy match against
every device in the house, which is exactly how the TRV won. The retry
now only fires when the narrow candidate set was genuinely empty
(the labelFilter lookup found nothing to judge at all) -- a real
ambiguous-or-too-fuzzy verdict from a precise, relevant candidate set is
now trusted and surfaced as a disambiguation question instead of being
silently re-gambled against a much larger, noisier pool.

Both root causes compounded to produce the live failure; either one
alone would likely have surfaced as an honest "ambiguous, please pick
one" instead of a wrong device receiving a live command.

## Validation

- `python -m pytest -q` -- 690 passed (2 new: a single unambiguous light
  target still resolves correctly through the live-lookup fallback path
  with `device_kind="auto"`, not just via the identity cache; the exact
  live scenario -- two real lights, a same-room TRV, and 30 unrelated
  distractor devices -- comes back ambiguous with both real lights
  offered as choices, and dispatches nothing to any device, confirming
  the TRV is never touched).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.385
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "turn on livingroom light" should now come back
  as an ambiguous disambiguation prompt ("Livingroom Light 1" or
  "Livingroom Light 2"), never a command sent to Livingroom TRV.
