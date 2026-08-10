# 0.10.400

## Why this release

Live-testing follow-up after the four Tier 2 releases (0.10.396-0.10.399)
surfaced a fresh wording bug in the hub health answer, not part of the
original code review: a radio the user deliberately disabled from the
hub's own Settings page was reported as "Not healthy," reading as an
alarm for a normal, intentional configuration.

## Fixed

**A deliberately-disabled radio was labelled "Not healthy" instead of a
neutral state word.** Confirmed live: the hub's own Settings pages show
"Z-Wave is disabled" (with an Enable button) while Zigbee and Matter show
"enabled" / Status: "ONLINE" / "Online". `homebrain_agent.py`'s
`_hub_health_outcome` renders the Hub Info driver's `zbHealthy`/
`zwHealthy` attributes as "Healthy"/"Not healthy" -- but that attribute
cannot distinguish "deliberately disabled" from "enabled but genuinely
malfunctioning," both report `false`. Labelling a disabled radio "Not
healthy" therefore reads as a fault when there isn't one, and used
different vocabulary than Matter's own already-live "online" string in
the same status table. `health_word()` now renders "Online"/"Offline"
instead of "Healthy"/"Not healthy" -- a neutral state word this
attribute actually supports and consistent with Matter's phrasing,
without claiming a "disabled" state the data can't verify (a more
precise disabled-vs-offline distinction would require pulling from the
hub's radio-management tool instead of the Hub Info driver, which the
user opted to defer as a bigger follow-up rather than fold into this
quick wording fix).

## Validation

- `python -m pytest -q` -- 731 passed (1 new:
  `test_hub_health_query_does_not_label_a_disabled_radio_as_unhealthy`
  confirms a disabled Z-Wave radio and an enabled Zigbee radio both
  render as Online/Offline, never "Healthy"/"Not healthy"; the existing
  `test_hub_health_query_reports_cpu_percent_and_human_radio_health`
  updated to match the new wording).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.400
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Found via live testing after the Tier 2 batch shipped, not part of the
  original full-codebase review's findings list.
