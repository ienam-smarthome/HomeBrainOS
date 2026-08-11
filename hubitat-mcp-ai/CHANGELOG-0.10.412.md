# 0.10.412

## Why this release

A live re-test of the 0.10.411 fixes, run immediately after that release
was merged, showed two of the three fixes working exactly as intended
(the hallway-lights room+kind resolution, and the causal "why" investigation
hint). The hub-health radio-status fix did not change the live answer at
all -- "check the hub health status" still reported firmware, CPU, memory,
temperature, and database size with no mention of Zigbee or Z-Wave.

## Fixed

**"Check the hub health status" still omitted Zigbee/Z-Wave radio status,
even after the 0.10.411 fix.** That fix updated `homebrain_hub_info_snapshot`'s
tool description and the system prompt, on the assumption that the model's
own narration was what needed to mention radio status. It wasn't: every
call to this tool -- regardless of `deterministic_reads_enabled` -- is
already intercepted by `deterministic_tool_presenter.py`'s
`_present_hub_info()` inside `mcp_agent_orchestrator.py`'s tool-calling
loop, which returns a canned firmware+resources string immediately and
never lets the model's own prose run at all. That presenter was never
updated when 0.10.409 added `zigbee_status`/`zwave_status` to the
underlying data, so the exact text the live answers were showing
("Hub firmware X is up to date. Hub resources: ...") was this template,
not model reasoning -- the 0.10.411 prompt/description changes had nothing
to act on. `_present_hub_info()` now renders Zigbee and Z-Wave status
using the same Online/Offline/Disabled wording rules as the original
0.10.409 fix (preferring the driver's explicit enabled/disabled status
attribute over the binary healthy/unhealthy one, and omitting the line
entirely rather than fabricating a status when the driver reports
neither).

## Validation

- `python -m pytest -q` -- 849 passed. New coverage in
  `test_deterministic_tool_presenter.py`: a hub-info result with radio
  fields set now renders both Zigbee and Z-Wave lines with the correct
  status wording, and a result with no radio fields at all omits both
  lines rather than fabricating a status.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.412
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
