# HomeBrain 0.17.45 — One-pass evidence-scoped lockout synthesis

## Problem addressed

The 0.17.44 focal event selector and targeted read-only collector established
how to join the 12 October physical button 1 push, app 1251 OFF command, light
OFF transition, persisted 300-minute setting, and bounded historical app logs.
Despite having those sources, the shared orchestration loop could still run
up to nine additional tool-selection rounds. The previous live benchmark used
four provider rounds and 18 tool calls, with provider time dominating latency.

## New behavior

- A deterministic `collected_lockout_ready_for_synthesis` gate evaluates the
  **current request** evidence receipt, not the model's narrative. It requires:
  named light and app ID; selected OFF matching the focal OFF; independently
  verified physical/manual provenance; successful targeted light and controller
  history reads; a successful persisted settings read; and an attempted,
  successful time-bounded application log read. Missing or failed evidence does
  **not** trigger the shortcut.
- When that exact evidence set exists for a single lockout investigation, the
  agent skips exploratory model/tool-selection rounds and calls the existing
  final-answer coordinator once. Current settings and log entries remain
  separate from actual historical lockout enforcement, which may remain
  unverified even with zero returned logs.
- Multiple-objective queries are excluded from this narrow shortcut.
- A named `lockout_prefetch_sufficiency_stop` request counter makes the
  path measurable. The global nine-round fallback stays unchanged for all
  other investigations.

This release does **not** shorten the initial model's provider latency, promise
a duration improvement, change Hubitat app 4019 from 300 to 3 minutes, or
change device/rule settings. No mutation commands or journal retention changes.

## Validation and release test

Regression tests exercise missing light/app evidence, controller failure,
missing settings, absent app logs, multi-objective fallthrough, and the
orchestrator short-circuit without invoking a model tool-selection round.
CI must pass before merge. Following installation, repeat the identical
read-only 0.17.43 three-test review; compare `model_rounds`, `tool_calls`,
provider timing, selected manual OFF, 300-minute current setting and the
separate unknown historical enforcement outcome. If the new counter is absent,
the safe fallback path was used rather than implying optimization success.
