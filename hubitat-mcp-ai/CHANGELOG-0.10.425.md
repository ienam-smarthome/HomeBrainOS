# 0.10.425

## Why this release

Continuing the audit-and-harden pass: with the app disable/enable flow
confirmed working, this release digs into the risk the reasoning-mode
migration itself (0.10.410) flagged in its own release notes -- that nine
read-only question categories (yesterday's counts, motion activity, hub
health, firmware status, location/mode history, "why" questions, and more)
now default to letting the model reason over live tool data instead of a
fixed template, and that correctness for these depends on guardrails that
had never had to carry this much weight alone. Cross-checking real data
pulled directly from a live Hubitat hub against every assumption in
`device_history_service.py`, `hub_info_service.py`, and related code found
the field shapes are all correct -- but surfaced one real, code-level gap
independent of any specific live bug report.

## Fixed

**The model had no anchor for "now" when reasoning about relative dates.**
Reasoning-mode question categories (default since 0.10.410) hand
"yesterday"/"today"/"this morning"/"last night" style questions straight
to the model with no server-side date math at all -- unlike the
still-present opt-in deterministic paths (`parse_count_yesterday` and
friends, restored via `deterministic_reads_enabled: true`), which compute
the "yesterday" window themselves from `datetime.now().astimezone()`. In
reasoning mode the model had to infer "now" purely from tool-result
timestamps or its own assumptions, with nothing telling it the actual
current date, time, or UTC offset -- a silent reasoning error (off by a
day, or a timezone) that would produce a plausible-looking but wrong
answer, exactly the kind of gap a live spot-check can't reliably catch on
its own.

The system prompt now opens with an explicit `CURRENT DATE AND TIME` line
(day of week, date, time, and UTC offset), computed the same way the
deterministic path already does, so reasoning mode is at least as
well-anchored for relative-date questions as the path it replaced by
default -- not a regression from it, and no longer silently ungrounded.

## Validation

- `python -m pytest -q` -- 875 passed. New coverage in
  `tests/test_agent_prompt_policy_manifest.py`
  (`test_system_prompt_anchors_the_model_to_a_concrete_current_date_and_time`)
  pins the anchor's presence, exact formatting, and that it appears before
  the rest of the prompt's guidance. `build_system_prompt` now accepts an
  optional `now` override for exactly this kind of deterministic test.
  Confirmed the test fails against the pre-fix code (reverted locally to
  verify, reproducing a `TypeError` for the new keyword argument) before
  restoring the fix.
- Cross-checked real event/mode/device data pulled directly from a live
  Hubitat hub against `device_history_service.py`'s field-mapping
  assumptions (`name`/`value`/`description`/`date`/`isStateChange`) --
  confirmed correct, no code change needed there.
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.425
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
