# 0.10.410

## Why this release

A live-testing comparison showed HomeBrainOS answering "why did the shower
light turn off this morning?" with a fixed disclaimer ("these events confirm
reported changes, but do not by themselves identify what caused them"),
while a general-purpose reasoning model given the same raw event data
produced a real causal investigation (motion-sensor correlation, automation
identification). Digging into why revealed two separate, compounding
problems, not one:

1. Nine read-only question categories (relative-that before/after, motion
   activity, count/list-yesterday, last/why-contact, location/mode events,
   mode-last-entered, hub health, firmware status) were intercepted by a
   hand-coded regex parser and answered from a fixed template *before the
   model ever saw the prompt* -- correct, but rigid, and an ever-growing
   list of bespoke parsers for every new phrasing.
2. Independently, `homebrain_device_history` calls were cut off by an
   unconditional early-return the instant the tool call succeeded, handing
   back the same canned disclaimer and ending the loop -- this fired
   regardless of *how* the tool was invoked, so it caught the "why" question
   above even though no dispatch branch in (1) was ever involved; the model
   itself called the tool and was still cut off before it could reason over
   the result.

This release makes deterministic answer templates opt-in rather than the
only path, and narrowly fixes the early-return so causal "why" questions get
a real second reasoning round.

## Changed

**Nine read-only question categories now default to reasoning through the
model instead of a fixed template.** A new `deterministic_reads_enabled`
option (default `false`) gates the dispatch branches for: relative-that
before/after, motion activity, count/list-yesterday, last-contact/why-contact,
location/mode events, mode-last-entered, hub health, and firmware status.
With the new default, these questions fall through to the general
native-function-calling loop, which calls the *exact same underlying tools*
(unchanged) and reasons over the result itself, instead of being answered
from a fixed template before the model is even invoked. Setting
`deterministic_reads_enabled: true` in the add-on's configuration restores
the previous all-template behaviour with no code change -- an explicit
rollback lever if reasoning-mode answers are ever less reliable for your
hub. Device control (turn on/off, lock/unlock, set level), firmware
install, and immediate internet-access block/allow remain deterministic
unconditionally, regardless of this setting -- these are writes with
real-world side effects and are not part of this change.

**A genuinely causal "why did X happen" question now gets a second
reasoning round instead of being cut off after one tool call.**
`mcp_agent_orchestrator.py`'s tool-calling loop no longer applies its
early-return-with-template behaviour to `homebrain_device_history` calls
when the user's prompt is asking "why" and the call succeeded -- the model
can now synthesize a real answer from the fetched events (or investigate
further with additional tool calls) instead of always receiving the fixed
disclaimer. Plain "what happened" questions (no "why") are unaffected and
still get the exact same templated, hallucination-safe summary as before.

**Location/mode-event questions are now reachable through a declared tool,
not just the deterministic dispatch branch.** Previously, "when did we last
enter Away mode?"-style questions were answerable *only* via the
deterministic dispatch branch, which called the MCP client directly --
there was no tool declared to the model for this data at all. A new
`homebrain_location_events` tool is now declared by default (alongside the
other ten safe-read tools), so the model can fetch this data itself in
reasoning mode; the deterministic dispatch branch continues to work
unchanged when `deterministic_reads_enabled: true`.

## Validation

- `python -m pytest -q` -- 842 passed. Existing tests in
  `test_homebrain_agent.py` covering the 9 gated rows now explicitly pass
  `deterministic_reads_enabled=True`, preserving full coverage of the
  still-present (opt-in) deterministic path. A new
  `tests/test_reasoning_first_reads.py` (4 tests) pins the new default
  behaviour: hub-health questions now invoke the model, location-events
  questions are reachable via the new tool, causal "why" questions get a
  second reasoning round with the disclaimer text absent, and non-causal
  "what happened" questions keep the exact prior template.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.410
- `python scripts/analyze_imports.py` -- `orphan_modules: []`

## Rollback

Set `deterministic_reads_enabled: true` in the add-on's configuration to
restore the exact pre-0.10.410 all-deterministic-template behaviour for the
nine gated question categories, with no code change required.
