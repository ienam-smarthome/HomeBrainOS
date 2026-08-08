# 0.10.384

## Why this release

Direct follow-up question after 0.10.383: "can't turn all lights off at
the moment, will 'turn off all lights except bedroom 2 and bedroom 3'
work?" The honest answer at the time was no -- the "all lights" aggregate
path added in 0.10.382 only recognises a closed set of unqualified
phrases ("the lights", "all lights", etc.) with no concept of an
exclusion clause, so the whole string would have reached per-name fuzzy
resolution as one literal device name and failed exactly like the bare
"the lights" bug 0.10.382 fixed.

## Added

**"Turn off all lights except <room/device>[, <room/device>...]" now
works.** `device_control_service.py` adds `split_all_lights_exclusion()`,
which recognises an "except"/"excluding"/"but not"/"other than" clause
directly after a base phrase, and only acts on it once the base phrase is
itself confirmed to be a genuine `is_all_lights_target()` match -- "turn
off Bedroom 1 except the lamp" is untouched by this, it keeps using
ordinary room resolution exactly as before. Each excluded term is
resolved the same way real device/room names are resolved everywhere
else in this file: a term matching a real room name (`"bedroom 2"`)
excludes every device in that room, otherwise it resolves like an
ordinary device name (`"the toilet light"`). Comma-separated lists work
with or without an Oxford comma ("bedroom 2, bedroom 3 and bedroom 4" and
"bedroom 2, bedroom 3, and bedroom 4" both split into three terms).

If an excluded term can't be resolved to any real room or device, the
whole command is refused with a clear error rather than silently acting
on everything -- including a device the user explicitly asked to leave
alone would be a worse failure than asking them to check the name and
retry.

## Validation

- `python -m pytest -q` -- 688 passed (4 new: excluding rooms leaves
  every device in those rooms untouched; excluding a single named device
  works the same way; an unresolvable exclusion refuses the whole command
  rather than silently including it, and dispatches nothing; an
  Oxford-comma exclusion list parses the same as a plain comma list).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.384
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "turn off all lights except bedroom 2 and
  bedroom 3" should turn off every other light and leave both bedrooms
  untouched.
