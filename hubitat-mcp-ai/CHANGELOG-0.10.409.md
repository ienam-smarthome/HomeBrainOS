# 0.10.409

## Why this release

Live-testing session against the real hub surfaced a genuine reporting bug
outside the 2026-08-10 review's scope: "check the hub health status"
reported a deliberately disabled Z-Wave radio as "Offline" -- the same
wording used for a radio that's enabled but genuinely malfunctioning.

## Fixed

**A deliberately disabled Z-Wave (or Zigbee) radio was reported as
"Offline", indistinguishable from a genuinely malfunctioning one.** Live-
verified against the connected hub, which has Z-Wave turned off from its
own Settings page: the Hub Info driver's `zwHealthy` attribute still reads
the string `"false"` in this case -- the exact reason the 0.10.400 release
renamed this row's wording from "Not healthy" to the neutral "Offline" in
the first place, since `zwHealthy` alone can't tell "disabled" and
"malfunctioning" apart. This release found that the same driver separately
reports a dedicated `zwaveStatus` attribute with the literal string
`"disabled"` for this exact case -- an attribute that does verify it, it
just was never being read. `hub_info_service.py`'s snapshot now also
extracts `zigbeeStatus`/`zwaveStatus`, and `homebrain_agent.py`'s hub
health report prefers that explicit status when the driver reports it,
falling back to the existing Online/Offline wording when it's absent
(older driver versions) or itself reports "enabled". "Z-Wave: Offline" is
now correctly "Z-Wave: Disabled" for this hub.

## Validation

- `python -m pytest -q` -- 838 passed, including two new regression tests
  (`test_hub_health_query_reports_a_deliberately_disabled_radio_as_disabled`,
  `test_hub_health_query_falls_back_to_healthy_binary_without_a_status_attribute`).
  The first was confirmed to genuinely fail against the pre-fix code via
  `git stash` before being included.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.409
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
