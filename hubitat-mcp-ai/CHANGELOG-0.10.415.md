# 0.10.415

## Why this release

Live re-testing right after 0.10.414 merged showed "What's my current
power usage?" now "succeeding" -- but with the wrong number. The hub has
both 15 discrete metered smart plugs (each reporting a literal `power`
attribute) and a separate whole-house meter device ("Octopus Meter
Current Power", which only reports via `valueStr`/`value`). The answer
came back "No whole-house meter was found. Summing the 15 monitored
smart plugs, your current power usage is 81 W" -- ignoring the real
4.70 kW whole-house reading entirely. 0.10.414's `hint` field only fires
when a `power`-attribute scan finds zero rows; here it found 15 rows (the
plugs), so the hint never ran, and the model had no way to learn that a
separate, more authoritative whole-house meter device also existed.

## Fixed

**`homebrain_query_devices` now surfaces a `whole_house_meter_candidate`
whenever a `power` query is made, independent of whether the discrete
scan also found rows.** A narrow, label-based match (a device labelled
with a "meter"/"energy monitor"/"power monitor" word, explicitly
excluding anything labelled as a plug/socket/outlet/switch) identifies a
dedicated whole-house meter and reports its `valueStr`/`value` reading
alongside a `whole_house_meter_hint` explaining that this single meter's
reading should be preferred over summing discrete devices. The tool
description was updated to tell the model to check these fields first for
any "current power usage" style question.

## Validation

- `python -m pytest -q` -- 859 passed. New coverage in
  `test_device_query_service.py`: a whole-house meter is surfaced
  alongside 15 metered-plug rows; a device merely labelled with "meter"
  as part of a plug's own name is correctly excluded; the candidate is
  never surfaced for non-power attributes.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.415
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
