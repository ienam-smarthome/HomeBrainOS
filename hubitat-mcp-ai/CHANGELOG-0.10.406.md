# 0.10.406

## Why this release

Ships the remaining two Tier 1 findings from the 2026-08-10 full code review
(the other two -- location-privacy redaction and device-claim prefix
collision -- shipped in 0.10.405): a hub-health unit lookup that always fell
back to hardcoded defaults, and a shared success-check helper that missed a
string `"false"` success flag. Both were reproduced directly before fixing.

## Fixed

**Hub Info resource units always fell back to hardcoded defaults, ignoring
the device's actually-reported unit.** `hub_info_service.py`'s `snapshot()`
called `merge_device_identity()` on the live Hub Info device -- which
flattens its `"attributes"` list into a plain `{name: value}` dict -- and
only *then* called `device_attribute_units()` on that same, already-merged
device. `device_attribute_units()` only understands the original list shape
(`[{"name": ..., "unit": ...}]`) and silently returns `{}` for anything else,
so `attribute_units` was always empty and `temperature_unit`,
`free_memory_unit`, and `database_size_unit` always fell back to the
hardcoded/inferred defaults (`"°C"`, inferred MB/KB, `"MB"`) regardless of
what the hub actually reported -- the same class of bug this codebase has
already found and fixed once (a Fahrenheit hub mislabelled `°C`). The
existing test passed only because its mocked device happened to report units
matching the hardcoded defaults. Fixed by capturing `attribute_units` from
the raw, list-shaped live device *before* the merge step flattens it, and
using that captured value afterward instead of recomputing on the merged
device. New test reports Fahrenheit/kilobytes/gigabytes (units that diverge
from every hardcoded default) to prove the real reported unit now threads
through.

**Shared `tool_succeeded()` missed a string `"false"` success flag.**
`mcp_client.py`'s `tool_succeeded()` -- the single source of truth
`device_query_service.py` and `device_control_service.py` both delegate
to -- used a strict `data.get("success") is False` identity check, so a
response shaped like `{"success": "false"}` (string, not JSON boolean) passed
straight through as success. This is the same already-documented pattern
this codebase has fixed for several adjacent fields (`zbHealthy`/`zwHealthy`,
`update_available`, `hub_alerts`, the `changed` flag). Added a small
`_is_false_flag()` helper that recognises both the JSON boolean and the
case-insensitive string form, used at both the top-level and one-level-nested
checks. Also fixed `device_history_service.py`'s `history()` and
`location_events()`, which independently duplicated the same strict check
at two call sites instead of using the shared helper at all -- both now
delegate to `mcp_client.tool_succeeded()`.

## Validation

- `python -m pytest -q` -- 787 passed (6 new: 1 for the hub-info unit fix,
  3 for the string-"false" success-flag fix in
  `test_tool_succeeded_consistency.py`, 2 for the same fix's
  `device_history_service.py` call sites).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.406
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
