# Hubitat MCP AI 0.10.342

## Fixed

- A time expression could arrive smuggled into a `homebrain_control_devices`
  call's `device_names` or `room` argument -- e.g. "hallway lights at
  11:11pm" -- because the tool has no dedicated time parameter for the
  model to put it in. This produced a confusing "no candidate similar
  enough" failure (the literal string "hallway lights at 11:11pm" doesn't
  match any real device name), even though "Hallway Light 1" / "Hallway
  Light 2" both genuinely exist.
- `DeviceControlService.execute()` now detects a smuggled time expression
  before doing any resolution work and refuses with a clear explanation,
  rather than either silently executing immediately (which would ignore
  the requested time and act *now* instead of at 11:11pm -- a worse
  outcome than the confusing failure) or leaving the corrupted name to
  confuse device resolution. It names what it understood as the target,
  states the requested time, and explains that one-off future-scheduled
  actions aren't supported yet (only immediate commands or recurring
  daily rules via `rule_authoring_service.py`).
- Extracts the clock-parsing regex (`_clock`/`_AT_TIME`) that previously
  lived only inside `rule_authoring_service.py` into a new shared
  `time_expressions.py` module, so `device_control_service.py` doesn't
  duplicate the same parsing logic. `rule_authoring_service.py` now
  delegates to it; its own tests are unchanged and still pass, confirming
  no behavior change there.

## Found via

- Live testing against the real house: the reported prompt was "turn on
  hallway lights at 11:11pm", which resolved as `Unresolved` against
  `Hallway TRV` / `HallwayCAM (MQTT)` / `Tuya Local WiFi Switch/Plug Test`
  -- none of which are lights, confirming the device name string itself
  was corrupted rather than genuine ambiguity.

## Validation

- Adds `tests/test_device_control_service.py` (first dedicated test file
  for this module -- it previously had none): the smuggled-time refusal
  for both `device_names` and `room`, confirmation that zero hub calls are
  made when refusing, a normal immediate-command regression check, and the
  pre-existing invalid-argument validation.
- Adds `tests/test_time_expressions.py` covering the extracted module
  directly.
- `python3 -m pytest -q` (531 passed).
- `python3 scripts/validate_addon.py` and `analyze_imports.py` both clean.
