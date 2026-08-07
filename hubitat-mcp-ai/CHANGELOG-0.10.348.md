# Hubitat MCP AI 0.10.348

## Fixed

- **Every scheduled rule request was rejected with "does not advertise the
  required command," even for devices that plainly support it.** Live
  testing of 0.10.347 found "turn on livingroom light 1 every day at
  11:05" and "turn on livingroom light 1 at 11:05" both declined with
  "**Livingroom Light 1** does not advertise the required command: on.
  Nothing was queued." A live `hub_get_device`/`hub_list_devices(detailed=
  true)` check on the same device showed `commands: ["off", "on",
  "refresh", "setLevel", "startLevelChange", "stopLevelChange"]` -- the
  command was there all along.

  Root cause: `RuleAuthoringService._commands()` reads the `commands` key
  off the device dict it gets back from `DeviceQueryService`, but that
  dict is assembled from two sources, and neither one actually carried
  `commands`:
  - The primary read (`DeviceQueryService._live_devices()` ->
    `hub_read_devices` / `hub_list_devices`) passes no `detailed` flag at
    all, so Hubitat's own tool returns bare `currentStates` only -- no
    `commands`, no `capabilities`.
  - The identity-enrichment read (`HubitatMCPClient.get_cached_devices()`)
    does pass `detailed: True`, but pairs it with an explicit `fields`
    projection -- `["id", "name", "label", "room", "capabilities",
    "attributes"]` -- that never included `"commands"`.

  So every device object this service (and anything else relying on the
  same identity cache for command lists) ever inspected had no `commands`
  key from either source. `_commands()` fell back to an empty set, and
  `required.issubset(supported)` was `False` unconditionally -- a 100%
  false-rejection rate for schedule creation, on every device, regardless
  of what it actually supports. This was previously masked because the
  0.10.346 dispatch-order bug and the 0.10.347 discovery-gate bug (fixed
  in the two prior releases) meant the code almost never reached this
  check in production; fixing those surfaced this one immediately on the
  very next live test.

  Fixed by adding `"commands"` to the `fields` projection in
  `HubitatMCPClient.get_cached_devices()`. Verified live: the identical
  `hub_list_devices` call with `"commands"` added to `fields` returns the
  full command list.

## Context

- This is the second bug found in two rounds of live-testing the
  scheduling feature added in 0.10.346, immediately after the discovery-
  gate fix in 0.10.347 let requests reach this deeper check for the first
  time. Every fix so far in this line has been found by actually creating
  (or attempting to create) rules against a live hub and checking the
  hub's own state afterward, not by trusting the app's own response
  message -- the existing unit-test fakes for this code path hand-place a
  `commands` key directly on their fake device dicts, which is more
  generous than the real MCP server's field-projection behavior and did
  not catch either this bug or the 0.10.347 one.

## Added

- `tests/test_device_manifest_cache.py`: updated the existing
  `get_cached_devices()` argument-shape assertion to include `"commands"`
  in the expected `fields` list.
- `tests/_entity_first_orchestrator_cases.py`:
  `test_rule_authoring_sees_commands_from_identity_enrichment_not_bare_device_list`
  -- full orchestrator-level regression test with a fake MCP that mirrors
  the real split precisely (bare `hub_read_devices` response with no
  `commands`/`capabilities`, `get_cached_devices()` carrying them
  separately), asserting the command check now passes and the proposed
  rule action carries the correct command.

## Validation

- `python -m pytest -q` -- 560 passed (559 from 0.10.347 + 1 new).
- `python scripts/validate_addon.py` -- OK.
- `python scripts/validate_release_consistency.py` -- OK at 0.10.348.
- `python scripts/analyze_imports.py` -- zero orphan modules.
- Live-verified against the reported failure: `hub_list_devices` for
  Livingroom Light 1 with `detailed: true` and `fields` including
  `"commands"` returns the full command list on the real connected hub,
  matching what the fixed code will now request.
