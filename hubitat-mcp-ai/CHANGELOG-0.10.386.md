# 0.10.386

## Why this release

Live re-test of 0.10.385: "turn on livingroom light" no longer commanded the
wrong device (Livingroom TRV) -- the dangerous part was fixed -- but the
disambiguation prompt still listed "Livingroom TRV" as a third choice
alongside the two real lights, and the live evidence showed the full
45-device fallback manifest retry still ran even though the narrow
labelFilter-scoped lookup found "2 target candidates" first. Reported live
via a fresh screenshot and JSON showing `"version": "0.10.385"`, with no
further text -- the gap was clear from the evidence itself.

## Fixed

**Root cause -- the narrow, labelFilter-scoped `hub_list_devices` lookup
never asked for capability data, so a real Hubitat gateway response came
back without it.** `_matches_kind()` (added in 0.10.385) and the
capability checks it wraps (`_is_switch_device()` / `is_light_device()`)
both key entirely off a device's `"capabilities"` field. The short-lived
device cache used elsewhere in this add-on
(`HubitatMCPClient.get_cached_devices()`) has always explicitly requested
a `fields` list including `"capabilities"` on every `hub_list_devices`
call -- but the room-wide and labelFilter-scoped lookups inside
`device_control_service.py`'s live fallback path never did, they called
with only `{"labelFilter": "<name>"}` or `{}`. A mock test double that
always echoes every field regardless of what's asked for masked this
completely; a real Hubitat gateway response without an explicit `fields`
request came back missing `"capabilities"` for these two Livingroom
lights. With no capability data to check, `_matches_kind("auto", device)`
evaluated `False` for both real lights, emptying `eligible` for the
narrow lookup despite it genuinely having found the right two devices --
which meant the 0.10.385 guard (`if resolution.target is None and not
eligible:`) still saw an empty `eligible` and still fired the broad,
noisy full-manifest retry, letting Livingroom TRV back in as a
disambiguation choice.

The fix adds the same explicit `fields` list
(`id, name, label, room, capabilities, attributes, commands`) already
used by `get_cached_devices()` to both live-lookup call sites in
`device_control_service.py`'s fallback path (room/all-lights-wide, and
per-name labelFilter-scoped), so capability data is reliably present
regardless of what a given Hubitat gateway defaults to when `fields` is
omitted.

## Validation

- `python -m pytest -q` -- 691 passed (1 new: a mock that reproduces the
  real-gateway behaviour of dropping `"capabilities"` from any
  `hub_list_devices` response that doesn't explicitly request it via
  `fields`, confirming "turn on livingroom light" still comes back as a
  clean two-way disambiguation between the real lights -- never widening
  to the full manifest, never listing or dispatching to the TRV -- even
  under that stricter mock).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.386
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "turn on livingroom light" should come back as an
  ambiguous disambiguation prompt offering only "Livingroom Light 1" and
  "Livingroom Light 2", with no further full-manifest fallback evidence
  entry and no "Livingroom TRV" choice.
