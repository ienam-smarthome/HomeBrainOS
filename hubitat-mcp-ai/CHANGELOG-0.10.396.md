# 0.10.396

## Why this release

First of four grouped releases closing Tier 2 findings from the
proactive full-codebase review conducted earlier this session (Tier 1's
eight high-confidence findings shipped as 0.10.390-0.10.395). This
release covers two cases of the same underlying problem: identical logic
duplicated across two files, silently drifting out of sync.

## Fixed

**Light detection diverged between two independent implementations.**
`device_state_summary.is_light_device()` did a crude substring search
over `str(capabilities)` for "light"/"bulb" only. `device_query_service`'s
own `_matches_device_kind("light")` check was already more thorough --
capabilities intersecting `{"light", "bulb", "colorcontrol",
"colortemperature"}`, plus a label check for "lamp"/"bulb"/" light" --
but that logic was never shared. A color bulb advertising only
`ColorControl`/`ColorTemperature` (a real, common driver shape), or a
device labelled "Bedroom Lamp" with no light-ish capability token at
all, could be correctly classified as a light in one code path
(`_matches_device_kind`, used by device ranking/aggregation) and wrongly
excluded in the other (`is_light_device`, used throughout
`device_control_service.py`'s "all lights on/off" routing and the
compact device manifest). Both now share one `capability_names()` +
`is_light_device()` implementation in `device_state_summary.py`;
`device_query_service.py` calls it directly instead of re-deriving the
same formula.

**`_tool_succeeded` disagreed on a partial-failure response shape.**
`DeviceControlService._tool_succeeded` and `DeviceQueryService
._tool_succeeded` were independently implemented and diverged on
`{"success": true, "error": "..."}`: the control path treated any
present `error` field as failure regardless of `success`, while the
query path only treated `error` as failure when `success` wasn't
explicitly `True` -- so the identical tool response was reported as a
failed control command by one code path and a successful read by the
other. `DeviceQueryService`'s version also never checked one level of
nesting (`result`/`data`/`output`) the way the control path's did. Both
now delegate to a single `mcp_client.tool_succeeded()`, which always
treats a present `error` field as failure and checks nested payloads
consistently.

## Validation

- `python -m pytest -q` -- 722 passed (9 new: a color bulb with only
  ColorControl/ColorTemperature and a lamp with no light-ish capability
  token are both now recognised by `is_light_device()`; an ordinary
  switch is still excluded; `_matches_device_kind("light")` and
  `is_light_device()` are cross-checked to agree on four fixtures; the
  shared `tool_succeeded()` and both classes' `_tool_succeeded` are
  cross-checked to agree on a clean success, an explicit failure, a
  nested failure, a transport-level error, and the partial-failure shape
  that used to diverge).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.396
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- This release closes findings #9-10 from the full-codebase review
  conducted this session (Tier 2). Write-safety gating for
  `hub_manage_virtual_device`/`hub_manage_mode`, pagination/token-
  estimator robustness hardening, and apostrophe-free hub-health/
  firmware phrasing are tracked separately as the remaining three
  grouped releases.
