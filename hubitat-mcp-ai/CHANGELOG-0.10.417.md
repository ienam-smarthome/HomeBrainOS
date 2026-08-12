# 0.10.417

## Why this release

Two more live-testing findings: a WebUI dashboard cleanup request, and a
real functional bug -- "disable humidity controller app" (a Hubitat
app/automation, not a device) was being deterministically hijacked into a
doomed device-name lookup, surfacing a "Which device do you mean" prompt
listing a security camera and a NUC box for a request that was never
about a device at all.

## Fixed

**"disable X app" / "enable X app" phrasing is no longer treated as an
internet-block/allow device request.** `parse_immediate_internet_access_intent`'s
`_BLOCK_INTERNET`/`_ALLOW_INTERNET` patterns have an unconstrained target
group, so "disable humidity controller app" fullmatched and was
dispatched to `homebrain_resolve_device` with
`required_command="blockInternet"` -- guaranteed to fail, since no device
is literally named that, and (on the currently deployed build) surfaced
unrelated devices as clarification choices. There is no deterministic
app-disable path in this codebase; the correct tool
(`hub_manage_native_rules_and_apps` / `hub_set_rule_paused`) is only
reachable through the model's own tool-calling loop. "app"/"apps"
wording now excludes this deterministic fast path the same way
"automation"/"rule"/"schedule" already do, letting these requests fall
through to the model loop where the real tool is available.

## Changed

**WebUI dashboard cleanup**, per direct request: the "Switches on" stat
tile is removed, and the remaining four (Active rooms, Lights on, Motion
active, Low batteries) are reordered to that sequence. The "Hub
resources", "Device health", and "Weather" shortcut buttons (plain NLP
queries with no live data behind them) are replaced with "Open sensors"
(which doors/windows are open) and "Firmware update" (is a hub firmware
update available) -- the pre-existing "Hub health" shortcut already
covers general hub diagnostics, so these three were redundant with it.

## Validation

- `python -m pytest -q` -- 864 passed. New coverage in
  `test_internet_access_hardening.py` ("disable"/"enable ... app" wording
  falls through to `None` instead of being parsed as an internet-access
  target) and `test_webui_render_contract.py` (dashboard tile order and
  removal, shortcut button replacement, and no leftover `dashSwitches`
  reference in the status()-update script -- a stray reference there
  would silently abort every subsequent tile update in the same
  try block).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.417
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
