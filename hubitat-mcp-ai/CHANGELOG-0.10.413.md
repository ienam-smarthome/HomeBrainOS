# 0.10.413

## Why this release

A broader "final pass" of live testing (fridge-door history, presence,
whole-house power usage, low batteries, hub health, and a side-by-side
comparison against a more capable model's hub-health answer) surfaced
three more gaps in the reasoning-first refactor: a needlessly verbose
history answer, a fully-failing power-usage question, and a completeness
gap in the hub-health answer relative to what the pre-0.10.410 deterministic
path used to include.

## Fixed

**"When was the fridge door last opened?" returned a 15-event dump
instead of a direct answer.** This is the same early-return template that
the causal "why" bypass deliberately does not apply to for non-causal
questions -- and it does not, since widening that bypass would let the
model narrate over the same unfiltered, noisy event list (including
unrelated housekeeping events like ipAddress/networkStatus) with no safety
net. Instead: `homebrain_device_history`'s tool description and its
`attribute`/`limit` argument descriptions now explicitly instruct the
model to scope a "last X" question to one attribute and a small limit, and
`_present_device_history` now leads with a one-line "Most recent: X was Y
at TIME" summary -- but only when the call was actually scoped to one
attribute, since an unfiltered multi-attribute fetch's newest event is not
reliably the reading the user asked about.

**"What's my current power usage?" failed outright** with "I could not
produce a valid structured action." The whole-house meter on the test hub
reports its reading only via a `valueStr` attribute, with no attribute
literally named `power` -- the system prompt already explained this
exact scenario, but the `homebrain_filter_devices`/`homebrain_query_devices`
tool schemas' own `attribute` descriptions only listed "power, temperature,
humidity, battery", giving the model no schema-level signal to retry with
`value`/`valueStr`. Both tool descriptions now mention this fallback
directly, matching the system prompt.

**Hub-health answers were less complete than before 0.10.410.** A live
side-by-side comparison against a more capable model's answer to the same
question showed HomeBrainOS omitting hub alert status and Matter status
entirely -- both of which the pre-0.10.410 deterministic path
(`_hub_health_outcome`, now opt-in) always included. `_present_hub_info`
now leads a `resources`/`full`-scope answer with the same alert-headline
parsing logic (the driver reports `hubAlerts` as a string, not a list, and
this is parsed as JSON first, falling back to treating a non-empty string
as one alert), and includes a Matter status row alongside Zigbee/Z-Wave
when the driver reports it.

## Validation

- `python -m pytest -q` -- 854 passed. New coverage in
  `test_deterministic_tool_presenter.py`: an attribute-scoped device-history
  call leads with a "Most recent" summary while an unscoped multi-attribute
  call does not; an active hub alert (both JSON-array-as-string and bare-string
  forms) is surfaced as a headline; Matter status renders as its own row.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.413
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
