# 0.10.389

## Why this release

Live re-test of 0.10.388: the duplicate-unit bug and the missing "%" on
CPU load were both fixed, but the same output still read `"Zigbee: true"`
and `"Z-Wave: false"` -- the raw booleans, not the intended "Healthy"/"Not
healthy" wording. Reported live with the full response JSON.

## Fixed

**The boolean-to-word formatter only recognised a Python/JSON bool, but
the real Hub Info driver reports zbHealthy/zwHealthy as the literal
strings `"true"`/`"false"`.** Hubitat attribute values are almost always
transmitted as strings, the same way a switch reports `"on"`/`"off"`
rather than a JSON boolean -- `isinstance(raw, bool)` alone never matched
that, so the raw string leaked straight through into the final message.
The mock fixture this fast path shipped with (0.10.387/0.10.388) used an
actual Python `bool` for these two fields, which is why this didn't
surface until a real hub was tested. `health_word()` now also recognises
the string forms `"true"`/`"false"` (case-insensitive) alongside an actual
bool, and the test fixture's default now matches the real hub's string
shape instead of a bool, so this class of gap can't silently return.

## Validation

- `python -m pytest -q` -- 696 passed (existing hub-health tests updated
  to use the real "true"/"false" string shape instead of a Python bool,
  now asserting both "Healthy" and "Not healthy" appear and neither raw
  "true" nor "false" does).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.389
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "check the hub health status" should show
  "Healthy"/"Not healthy" for Zigbee and Z-Wave, never the raw
  "true"/"false".
