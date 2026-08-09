# 0.10.392

## Why this release

Third of four grouped releases closing Tier 1 findings from the
proactive full-codebase review conducted this session (0.10.390 shipped
hub info & presenter string/unit accuracy, 0.10.391 shipped text parsing
& device resolution accuracy). This release covers Rule Machine
capability filter safety.

## Fixed

**Scheduled-rule `capabilityFilter` was chosen by a fixed capability
priority list, not by what command the rule actually schedules.**
`RuleAuthoringService._capability_filter()` previously scanned a
device's capabilities and returned the first one matching a fixed
priority order (`Switch` > `Lock` > `DoorControl` > `GarageDoorControl`,
else the first capability found) with no regard for the command the
rule was actually scheduling. A device that advertises both `Switch`
(e.g. a virtual on/off proxy) and `GarageDoorControl` would get
`capabilityFilter: "Switch"` for a scheduled `close`/`open` rule purely
because `Switch` sits first in the priority list -- but Hubitat's
`runCommand` action requires the `capabilityFilter` to be a capability
that actually exposes the scheduled command, so `Switch` cannot execute
`close`/`open` and the rule would silently fail to do anything at its
trigger time.

`_capability_filter()` now takes the command(s) this rule schedules
(`intent.start_command`, plus `intent.end_command` for a window) and, in
the device's own reported capability order, prefers whichever capability
is documented to expose all of them (`Switch`: on/off, `Lock`:
lock/unlock, `DoorControl`/`GarageDoorControl`/`Valve`: open/close).
Commands with no standard capability mapping -- `blockInternet` /
`allowInternet`, which are driver-specific and not part of any
documented capability's command set -- fall back to the original
fixed-priority selection unchanged, so existing internet-access rules
are unaffected.

## Validation

- `python -m pytest -q` -- 709 passed (3 new: a device advertising both
  `Switch` and `GarageDoorControl` now gets `GarageDoorControl` for a
  scheduled close/open rule instead of `Switch`; a device advertising
  both `Switch` and `Lock` gets `Lock` for a scheduled lock command;
  `blockInternet`/`allowInternet` -- unmapped to any standard capability
  -- still correctly falls back to the original fixed-priority
  selection).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.392
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- This release closes finding #7 from the full-codebase review conducted
  this session. The public API's session_id default is tracked
  separately as the final grouped release.
