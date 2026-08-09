# 0.10.388

## Why this release

Live re-test of the 0.10.387 deterministic hub health path fixed the "126
KB" mislabel and the fabricated "Cloud Backup" line, but surfaced its own,
smaller bug in the same output: `"Internal Temperature: 46.9 °C °C"` --
the unit printed twice. Reported live with the full response JSON (also
confirming `"model": null`, proving the new fast path really is running
instead of the local model).

## Fixed

**A field whose raw value already carries its unit got the tracked unit
appended a second time.** The 0.10.387 fast path formats each hub health
field by concatenating its raw value with a separately tracked unit field
(e.g. `temperature` + `temperature_unit`). That's correct when the raw
value is a bare number, but the real Hub Info driver's `temperatureC`
attribute was observed live reporting its `currentValue` as a
pre-formatted display string with the unit already included (`"46.9
°C"`), not a bare `46.9` -- concatenating the tracked unit onto that
produced the duplicate. The formatter now strips a trailing occurrence of
the unit already present in the raw value before appending it once, so it
renders correctly regardless of which form a given field/driver reports.

## Improved

While looking at the same live output, two related rough edges in the
same new fast path were tidied up:

- **CPU Load** now reads `"22.25%"` instead of a bare, unit-less `"22.25"`.
- **Zigbee**/**Z-Wave** health now read `"Healthy"`/`"Not healthy"`
  instead of the raw booleans `"true"`/`"false"`.

Neither of these were reported by name, but both were visible in the same
live response and are part of the same output this release is fixing.

## Validation

- `python -m pytest -q` -- 696 passed (2 new: a fixture reproducing the
  exact live shape -- `temperatureC.currentValue` reported as `"46.9 °C"`
  rather than a bare number -- confirms the formatted message contains
  `"46.9 °C"` exactly once and never `"°C °C"`; CPU load and the
  zigbee/zwave health flags render as a percentage and readable words
  rather than a bare number or literal booleans).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.388
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "check the hub health status" should show the
  internal temperature with its unit exactly once, CPU load as a
  percentage, and Zigbee/Z-Wave as readable health words.
