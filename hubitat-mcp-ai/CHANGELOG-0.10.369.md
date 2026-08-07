# 0.10.369

## Fixed

Live testing of `DeviceQueryService.resolve_device` (the generic
device-name-to-ID lookup used for reads, history, and attribute queries)
against a real 91-device Hubitat inventory surfaced two related,
reproducible bugs. Unlike `DeviceControlService`, which already pre-filters
its candidate list to switch/light-capable devices before calling
`resolve_device_candidate`, `resolve_device` was passing the **complete,
unfiltered inventory** into the resolver, which has no concept of device
capability and scores purely on text similarity.

1. **Wrong-kind devices polluting disambiguation.** "hallway light"
   returned *Hallway Light 1*, *Hallway Light 2*, and **Hallway TRV** (a
   thermostat valve, not a light) as equally-weighted clarification
   options, because the TRV shares the room name and scores similarly by
   string similarity. The same pattern reproduced for "living room light"
   (pulled in a TRV) and "bathroom light" (pulled in a temperature/humidity
   meter).
2. **Silent wrong-answer risk on bare attribute words.** A bare
   "temperature" query resolved to a single specific sensor at 0.90
   confidence with no clarification offered, despite several other devices
   in the same house independently reporting a temperature reading with a
   materially different live value at the same moment (6.2°C at a fridge
   meter vs. 27.8°C in the living room, in the observed test). This is a
   confident-wrong-answer risk, not a missing-device risk — the previous
   behavior never surfaced it as ambiguous.

## Fix approach (deterministic, not prompt-only)

`resolve_device` now infers a device-kind hint (light / switch / socket /
motion) from simple keyword matching against the requested name — the same
approach `DeviceControlService` already uses for on/off commands — and
narrows the candidate pool to devices matching that kind via
`_matches_device_kind` (extended with a `motion` branch keyed off the
`MotionSensor` capability) before calling `resolve_device_candidate`.
Filtering is only applied when it leaves at least one candidate, so an
unrecognized or unconventional label can never be filtered out entirely.

Separately, when a bare attribute word (`temperature`, `humidity`,
`battery`, `power`) resolves via the resolver's ranked-similarity path
(reason `"high-confidence ranked candidate"`, not an exact-name match) and
more than one candidate in the (possibly kind-scoped) pool independently
reports that same attribute, the result is now downgraded to an explicit
disambiguation listing up to three reporting devices, instead of silently
returning one. A device whose actual label is literally the attribute word
(e.g. a driver labelled "Temperature") is unaffected — the guard only
applies to non-exact, ranked matches.

**Known residual limitation:** this does not fully solve every
label-versus-capability mismatch. A motion sensor labelled by its physical
location and driver rather than by the word "motion" (e.g. "Kitchen
Linptech") is now correctly *included* in the candidate pool for a "kitchen
motion" query once its `MotionSensor` capability is known, but may still
fall below the ranked-match confidence floor on text similarity alone if
its label doesn't share enough characters with the query. Closing that gap
fully would need a synonym/alias layer on top of capability filtering,
which is out of scope for this fix.

## Validation

- `python -m pytest -q` — 623 passed (3 new: two regression tests
  reproducing the wrong-kind-candidate and silent-attribute-pick bugs
  against synthetic device fixtures shaped like the live-observed cases,
  plus one guarding that an exact label match still bypasses the new
  bare-attribute check).
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py`
- `python scripts/analyze_imports.py` — `orphan_modules: []`
- Manual live-data check: ran `DeviceQueryService.resolve_device` directly
  against a real 91-device inventory snapshot (fetched live via the
  Hubitat MCP connector) for the exact queries above; confirmed "Hallway
  TRV" / "Bathroom meter" no longer appear in light disambiguation lists,
  and "temperature" now returns an explicit multi-device disambiguation
  instead of a silent pick.
