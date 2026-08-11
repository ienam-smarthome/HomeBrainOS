# 0.10.411

## Why this release

A live-testing pass against the real hub, run immediately after 0.10.410
shipped, surfaced three issues: one pre-existing device-control gap the new
test session happened to hit, and two real regressions caused by making
deterministic answer templates opt-in.

## Fixed

**"Turn off the hallway lights" (or any "`<room>` lights"/"`<room>`
switches" phrasing) failed to resolve at all.** The device-name resolver
only had two multi-device shortcuts: an exact "the lights"/"all lights"
house-wide match, and a bare room name with no qualifier. A room name
followed by a plural kind word ("hallway lights") fell through to ordinary
per-name fuzzy matching, which correctly found nothing named "the hallway
lights" and reported every "Hallway *" device -- including Hallway TRV, a
thermostat that isn't a light -- as an undifferentiated disambiguation
menu. `device_control_service.py` now recognises a trailing bare
"light(s)"/"switch(es)" word on a single `device_names` entry, and when
the remaining text matches a real room, resolves it as a room + kind
request instead: "the hallway lights" now turns off every light in the
Hallway and only the lights, the same way an explicit `device_kind` from
the model already would. A real device name that merely ends in "Light"
(e.g. "Kitchen Light") is unaffected -- only a genuine room match triggers
this path.

**Reasoning-mode "check the hub health status" answers stopped mentioning
Zigbee/Z-Wave radio status.** 0.10.410 made the deterministic hub-health
template (which always included radio status -- the entire point of
0.10.409) opt-in via `deterministic_reads_enabled`. With it off by
default, the model has to decide for itself which tool answers a hub-health
question, and `homebrain_hub_info_snapshot`'s description never mentioned
radio status at all, so the model reached for `hub_read_diagnostics`
instead (which does not carry it) and the radio lines silently vanished
from the answer. The data was always there -- this is a tool-description
and prompting gap, not a missing-tool gap. `hub_info_tool()`'s description
now explicitly states it is the only tool with Zigbee/Z-Wave radio status,
and the system prompt now has an explicit HUB HEALTH rule: call
`homebrain_hub_info_snapshot` with `scope='full'` for any hub-health
question and report radio status alongside memory/uptime, not instead of
it.

**A causal "why" question's second reasoning round (added in 0.10.410)
didn't reliably lead to an actual investigation.** Live test: "why did the
shower light turn off this morning?" got its second round as designed, but
the model just re-narrated the same switch-only event list instead of
checking whether the shower's motion sensor correlated in time -- a second
round alone doesn't make a model investigate further on its own initiative.
The orchestrator now injects an explicit host hint immediately after a
causal-bypassed `homebrain_device_history` result, prompting the model to
consider a related sensor (motion, contact, button) in the same room
before answering, and to say plainly when no supporting sensor data exists
rather than asserting an unsupported cause.

## Validation

- `python -m pytest -q` -- 847 passed. New coverage: three
  `test_device_control_service.py` tests for the room+kind-suffix pattern
  (turns off both Hallway lights and excludes the TRV; "hallway switches"
  selects the opposite device set; a real device literally named "Kitchen
  Light" is unaffected), plus two `test_reasoning_first_reads.py` tests
  confirming the causal-investigation hint is actually injected into the
  model's second-round messages and that `hub_info_tool()`'s description
  mentions Zigbee/Z-Wave radio status.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.411
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
