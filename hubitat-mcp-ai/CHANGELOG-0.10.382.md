# 0.10.382

## Why this release

Live-tested immediately after 0.10.381: "turn off the lights" (no room, no
device name -- an unqualified whole-house request) came back "Unresolved"
with an unrelated disambiguation offer (Livingroom TRV / Block Tab-S9-FE /
Fridge), reported live with the explicit expectation that this should have
simply turned off every light that was on.

## Fixed

**A bare, room-less "turn off/on the lights" had no deterministic
house-wide interpretation.** `DeviceControlService` already has a
deterministic room-wide path (0.10.x: "turn off Bedroom 1" acts on every
device in that room) and an ordinary per-name fuzzy-match path ("turn off
Kitchen Light"), but nothing in between for "every light in the house,
unqualified." `routine_control_arguments()` parses "the lights" as a
literal `device_names` entry, and `resolve_device_candidate`'s fuzzy
matching has nothing named "the lights" to match against -- so it fell
through to the same "Unresolved" / nearest-fuzzy-match disambiguation
prompt a genuinely unknown device name produces, offering completely
unrelated devices (a TRV, an internet-block plug, a fridge) instead of
doing the obviously intended thing.

`device_control_service.py` now recognises a closed set of unqualified
aggregate phrasings -- "the lights", "the light", "all lights", "all the
lights", "all of the lights", "every light", "all my lights" -- via a new
`is_all_lights_target()` helper, deliberately narrow so a *named* or
*room-qualified* request ("turn off Kitchen Light", "turn off the office
lights") keeps going through its existing, unaffected resolution path.
When matched, resolution targets every device in the house whose
capabilities mark it a light (the same `is_light_device` check
`homebrain_active_lights` already uses for reads), mirroring the existing
room-wide code path: a fast identity-cache pass first, falling back to a
live `hub_list_devices` read only if the cache has nothing, and reporting
a clear "No lights were found in this house" error rather than a
misleading empty "success" if the house genuinely has none. A non-light
switch or plug (e.g. a TV smart plug) is never touched by this, even
though it shares the same generic switch capability every light also
carries.

The command itself (on/off) is applied to every matched light regardless
of its current state -- turning off an already-off light, or on an
already-on light, is a harmless no-op, so this doesn't need to first read
each light's current state to decide whether to touch it.

## Validation

- `python -m pytest -q` -- 679 passed (4 new: a bare "the lights"/"all
  lights"/etc. request acts on every real light device house-wide and
  skips a non-light switch that shares the same capability; every
  recognised phrasing variant resolves the same way; a house with no
  light devices at all reports a clear error without dispatching any
  command; a specifically named light is unaffected and still goes
  through ordinary per-name resolution).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.382
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "turn off the lights" should now turn off every
  real light in the house instead of returning "Unresolved".
