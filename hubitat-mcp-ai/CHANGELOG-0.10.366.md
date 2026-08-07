# Hubitat MCP AI 0.10.366

## Fixed

- **"Show current power" on a specific, already-identified device said
  "does not report a current power value" despite the reading being
  right there.** Live retesting after 0.10.365 found a *third* spot with
  the same underlying shape of gap as the earlier power-usage bug:
  `DeviceQueryService._attribute_value()` -- the lookup behind single-
  device contextual attribute reads ("what's the fridge temperature"
  style questions) -- only recognises a fixed alias list per attribute
  (`power` -> `power`/`activePower`/`powerMeter`). "Octopus Meter Current
  Power" has none of those; its reading only exists as `valueStr`
  ("231 W"). Fixed with a new, deliberately **opt-in** fallback parameter
  (`allow_generic_value_fallback`) that checks `valueStr`/`value` as a
  last resort -- wired into the single-device contextual-read call site in
  `homebrain_agent.py` only. It is explicitly NOT enabled for the cross-
  device ranking/aggregation path in `query_devices()` (used for "highest
  power device" style questions across many devices at once): a bare
  `value` attribute isn't reliably about the attribute being asked for
  when scanning many different device types, and turning it on there
  could wrongly sweep an unrelated device's own differently-meaning
  generic reading into a ranking. Also fixed a rendering bug this
  surfaced: naively appending the usual "W" unit on top of `valueStr`
  (which already reads "231 W") would have produced "231 WW" -- the
  presenter now omits the unit suffix specifically when the value came
  from `valueStr`, since it's already human-formatted.

## Context

This closes out the same investigation as 0.10.364/0.10.365's power-usage
fixes, found by continuing to retest live after each release rather than
assuming the previous fix was complete. Three distinct code paths turned
out to reference an Octopus-style `value`/`valueStr`-only reading
differently: the compact device manifest (fixed 0.10.364), the whole-home
aggregation tool-selection guidance (fixed 0.10.365), and this
single-device contextual attribute lookup (fixed here). Each needed its
own fix because each has a different, deliberate scope of what should be
allowed to fall back to a generic reading.

## Validation

- `python -m pytest -q` -- 610 passed, including
  `test_attribute_value_generic_fallback_is_opt_in_only` and
  `test_attribute_value_named_alias_still_wins_over_generic_fallback`.
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.366.
- `python scripts/analyze_imports.py` -- zero orphan modules.
