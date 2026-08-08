# 0.10.380

## Why this release

A broad audit pass across the rest of the system -- device control beyond
on/off, rules and scheduling, rooms/logs/diagnostics, apps/integrations/
code management, and hub settings/administration -- requested after the
internet-access hardening pass, to find issues before they're
live-reported rather than after. Five parallel reviews covered each area
against both the source and this house's real live state (89 devices, the
actual rule list, app list, room list). This release fixes the single
highest-confidence, highest-blast-radius defect found: a real bug in the
confirmation approval flow that affects nearly every sensitive Hubitat
gateway except Rule Machine. The remaining findings are documented below
as a prioritized follow-up list rather than rushed into this release --
several require real design decisions (unit handling for thermostat
setpoints, a rule-name resolver analogous to the device resolver) that
deserve their own focused pass rather than being bolted on here.

## Fixed

**`ConfirmationPolicy.approved_arguments()` only injected the upstream
`confirm:true` flag for `hub_manage_rule_machine` -- every other sensitive
gateway's confirmation flow was silently broken.** Two independent audit
passes (apps/integrations, and hub settings/administration) found this
independently and converged on the same root cause. Hubitat management
gateways carry their real sub-tool call inside a nested `{"tool": ...,
"args": {...}}` envelope, and it's that nested operation's own
destructive/sensitive handler that requires `confirm:true` after
HomeBrain's own confirmation gate approves the call -- not the gateway
call itself. The code only ever special-cased `hub_manage_rule_machine`
for this. Every other gateway -- `hub_manage_backup`, `hub_manage_radio`,
`hub_manage_variables`, `hub_manage_code`, `hub_manage_native_rules_and_apps`,
`hub_manage_rooms`, `hub_manage_dashboards`, `hub_manage_destructive_ops`,
`hub_manage_mcp`, and confirm-bearing operations on `hub_manage_devices`
(`hub_call_device_swap`, `hub_call_device_replace`, `hub_create_device`) --
never received the flag. A user's explicit "yes" would queue and dispatch
the call, but Hubitat's own confirm gate would then reject the upstream
write for lacking `confirm:true` -- silently breaking the confirmation
flow for a hub-DB restore, a Zwave/Zigbee radio change, a variable delete
another rule depends on, an app/driver code edit, a room delete, a
dashboard delete, a hub reboot/shutdown, and more. `confirmed_failure_report`
(added in 0.10.375) does catch the resulting failure and report it
honestly rather than claiming false success, so this was never a silent
data-corruption risk -- but it broke the actual mechanics of "approve once,
it executes" for every one of these operations.

Not every nested operation has a confirm field, though: `hub_call_device_command`
verifies success via `waitFor`-based state checking instead, Rule Machine
runtime control (`hub_set_rule_paused`/`hub_call_rule`/
`hub_set_rule_private_boolean`) is routine rather than destructive, and the
legacy custom-rule engine's `hub_update_custom_rule` has no confirm field
at all. The fix is a precise allowlist of nested operation names confirmed,
by directly inspecting each gateway's live MCP schema, to declare their own
confirm parameter -- not a blanket "inject into every nested args object,"
which was tried first during this pass and immediately caught by the
existing `test_sensitive_manage_write_still_waits_for_confirmation` test:
it broke device-command dispatch (e.g. an unlock) by sending an unrequested
`confirm` key to a schema that never declared one.

## Audit findings deferred to follow-up (not fixed this release)

Ranked roughly by how likely each is to actually bite a live user, given
what this house's real inventory contains:

- **Rule duplicate-detection only matches byte-identical generated
  names.** This hub's real rule list already has functionally-duplicate
  rules under different naming conventions (`"Block Nest hub @9am"`,
  `"Media: Turn OFF TV"`) that a fresh "block the nest hub at 9am daily"
  request would not recognise as a duplicate, since it compares against
  the newly-generated name only. Needs a fuzzy-match pass over existing
  rule names, not just exact casefold equality.
- **Rule pause/resume/delete/trigger have no deterministic name-to-appId
  resolution**, unlike device targeting's `homebrain_resolve_device`. This
  hub's real rule list has near-identical names (`"Block Tab S9 FE
  (Daily)"`/`"(Start)"`/`"(End)"`) that a spoken "pause the tab s9 rule"
  has no deterministic way to disambiguate among.
- **Thermostat/TRV setpoint and mode commands (`setHeatingSetpoint`,
  `setThermostatMode`, etc.) have zero deterministic handling or prompt
  guidance**, unlike on/off/toggle. This house has 5 real climate-control
  devices. Needs careful design around unit handling (the TRVs are
  Tuya-based and may report/accept °C) before a fast path is safe to add.
- **Dimmer `setLevel` and fan `setSpeed`/`cycleSpeed` have no
  deterministic path, range validation, or `waitFor` verification.**
  Already flagged as a known gap in 0.10.376; still open.
- **LIVE HUB LOG RULES have no deterministic time-window parsing** --
  `since` is generated by the model with no bounds-checking, unlike the
  deterministic time handling that exists for device control and contact
  history.
- **App/rule status reconciliation (ACTIVE/DISABLED/PAUSED/BROKEN) has a
  real deterministic fast path (`AutomationStatusService`) that correctly
  handles this house's actual disabled apps literally named `"Living Room
  1 (Active)"`, but only fires on narrow trigger phrasing** ("is the
  automation active" style, not "is Living Room 1 active?"). Outside that
  phrasing, status falls to open-ended model reading of raw app JSON with
  only prompt-text guidance against the misleading name.
- **Mode/HSM disambiguation is entirely model-driven** -- "arm the house"
  is genuinely ambiguous between `hub_set_hsm` and `hub_manage_mode`, with
  no deterministic resolver forcing a check of current state first.
- A device (`"Block Google-TV-Streamer"`) that legitimately supports both
  real on/off and blockInternet/allowInternet was flagged as a potential
  routing ambiguity for plain "turn off" phrasing that doesn't trigger the
  block/allow guard -- on review this appears to be intended behaviour
  (the device genuinely has independent on/off and block/allow commands),
  not a bug, but is noted here in case it proves otherwise in practice.

## Validation

- `python -m pytest -q` -- 672 passed (3 new: confirm-bearing gateway
  operations beyond Rule Machine now get the flag injected, verified
  against every gateway/operation pair confirmed via live schema
  inspection; operations without a confirm field -- device command
  dispatch, RM runtime control, legacy custom-rule update -- are
  confirmed to stay untouched, closing the exact regression the
  blanket-injection approach introduced and caught mid-pass).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.380
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: a confirmed backup restore, radio change,
  variable delete, or room/dashboard delete should now actually execute
  after approval instead of failing with an unexplained upstream
  rejection; device on/off/lock/unlock dispatch is unaffected (confirmed
  by the existing regression test, not a live-tested claim this round).
