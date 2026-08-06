# Hubitat MCP AI 0.10.344

## Added

- Advisory automation requests ("recommend useful automations", "review
  my automations", etc.) now include real gap analysis, not just a relist
  of existing status. Devices with a safety-relevant capability
  (`WaterSensor`, `SmokeDetector`, `CarbonMonoxideDetector`) whose label
  isn't referenced by name in any automation are flagged as an unmonitored
  gap -- fully grounded in retrieved device and automation data, nothing
  invented. E.g. "Linptech Kitchen lux (CarbonMonoxideDetector,
  SmokeDetector, WaterSensor)" if nothing in the automation list names it.
- `snapshot(advisory=True)` now also fetches the live device inventory
  (`hub_read_devices` / `hub_list_devices`) alongside the existing
  automation/rule fetches, purely for this cross-reference. The literal
  status-listing path (`advisory=False`) is unchanged and does not make
  this extra call.

## Context

- Requested after comparing the 0.10.343 advisory output (which only
  relisted existing broken/disabled automations) against a reference
  example that did genuine device-to-automation gap analysis -- e.g.
  flagging that several multi-capability sensors with `WaterSensor` had
  no leak-alert automation, or that a `Security: Front door open alert`
  rule existed but was disabled. This adds the safety-sensor half of that
  gap analysis as a bounded, grounded first step.

## Scope, stated honestly in the response itself

- This is a name-match heuristic against existing automation names -- not
  certainty. An automation could functionally cover a device without
  naming it in its label, which would produce a false "uncovered" flag.
- Deliberately narrow to three safety-relevant capabilities, not
  general-purpose "what automations should I add" reasoning across the
  full device inventory (e.g. correlating TRVs with missing schedules, or
  Octopus Energy live-rate data with load-shifting opportunities) -- that
  remains real, larger, unattempted work, and the response says so.

## Validation

- Adds `tests/test_automation_status_advisory.py` coverage for:
  `_uncovered_safety_devices()` correctly including/excluding devices
  based on capability and name-match; the advisory message including or
  omitting the gap section depending on whether devices were passed; and
  two new `snapshot()` integration tests (previously zero direct test
  coverage existed for `snapshot()` itself) confirming the device fetch
  only happens on the advisory path.
- `python3 -m pytest -q` (545 passed).
- `python3 scripts/validate_addon.py` and `analyze_imports.py` both clean.
