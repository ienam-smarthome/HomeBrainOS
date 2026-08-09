# 0.10.390

## Why this release

Proactive full-codebase review requested after the recent string of live
hub-health bugs (0.10.387-0.10.389), all sharing one root cause: Hubitat
consistently transmits values the code assumed were real Python/JSON
types (booleans, lists) as strings instead. A structured review across
the whole add-on found several more instances of the exact same bug
class, all in the deterministic presentation layer, that hadn't yet been
hit live but were sitting in exactly the same shape.

## Fixed

**Hub alerts silently swallowed when reported as a string.**
`_hub_health_outcome` (`homebrain_agent.py`) only recognised `hub_alerts`
as a Python list. `device_query_service.py`'s own empty-alerts sentinel
check (`hub_alerts not in (None, "", "[]", [])`) proves the real Hub Info
driver reports `hubAlerts` as a **string**, not a list -- a genuine active
alert reported that way would have failed `isinstance(alerts_raw, list)`
and been silently reported as "healthy with no active alerts", masking
exactly what this feature exists to catch. A string value is now parsed
as JSON first (covers a driver that serialises a real list into a
string), falling back to treating the whole non-empty string as one alert
message; the string sentinel `"[]"` (and empty/none) still correctly
reads as healthy.

**Unit-doubling guard extended to every hub-resource field, not just
temperature.** The temperature field was guarded this session against a
baked-in unit producing a duplicate ("46.9 °C °C"), but free memory,
database size, and CPU percent go through the identical
`hub_info_service.py` passthrough and had no equivalent guard. A single
`_append_unit()` helper now covers all four.

**String `"false"`/`"true"` boolean flags treated as their literal Python
truthiness instead of their intended meaning, in four presenter checks.**
Hubitat/upstream tool results consistently transmit boolean-ish values as
strings (already confirmed live for the zbHealthy/zwHealthy hub-health
flags) -- a bare `bool(x)` on the string `"false"` is `True` (non-empty
strings are always truthy), and `x is False`/`not x` never correctly
catch a string form either. A new `_coerce_bool()` helper now normalises
an actual bool or a `"true"`/`"false"` string to a real bool everywhere
this mattered:
- Firmware `update_available` -- previously could claim an update was
  available when a string `"false"` was reported.
- Control-command `success` -- previously could report a failed command
  as succeeded when reported as a string `"false"`.
- Device-history `success` -- previously could report a failed history
  lookup as succeeded for the same reason.
- Per-device `changed` flag -- previously could misreport an
  already-in-state device as freshly changed.

## Validation

- `python -m pytest -q` -- 703 passed (11 new: hub alerts reported as a
  JSON-shaped string, a plain-text string, and the real "[]" empty
  sentinel all resolve correctly; free memory and database size no longer
  double a baked-in unit; firmware/control/device-history/changed flags
  all correctly interpret a string `"true"`/`"false"` the same way they
  interpret a real bool).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.390
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- This release closes findings #1-3 from a full-codebase review conducted
  this session; findings on text parsing, Rule Machine capability
  filtering, and the public API's session_id default are tracked
  separately for follow-up releases.
