# 0.10.378

## Fixed

Live re-test of 0.10.377 surfaced two more gaps in the same immediate/
scheduled internet-block area, both found within minutes of deploying:

First, a scheduled request -- "block the tv at 10pm" -- was rejected
outright with "**TV** does not advertise the required command:
blockinternet. Nothing was queued." This was the exact gap
0.10.377's changelog flagged and deliberately deferred:
`RuleAuthoringService.propose()` resolves its target by name alone
(`DeviceQueryService.resolve_device({"name": ...})`), then checks
capability only *after* resolving -- so against a house with both a
plain power-switch labelled exactly "TV" and a separate
network-integration device labelled "Block Google-TV-Streamer", it
always picked the exact-label switch and then rejected it, never
trying the streamer device that was sitting right there in the same
inventory.

Second, and a genuine regression introduced by 0.10.377 itself:
"block the tv in 30 mins" resolved to "Which device do you mean:
Block Google-TV-Streamer, Block CAM-Camera-G100-42EA, or Block
CAM-Camera-G100-7B37?" -- completely wrong. Neither `AT_TIME` nor the
window pattern recognise relative-delay phrasing like "in 30 mins"
(both only match a clock time or a "from X to Y" range), so
`parse_immediate_internet_access_intent()` was catching it as an
immediate request and swallowing "tv in 30 mins" whole as the device
name, which then failed to resolve against the real inventory.

## Fix approach

- `device_query_service.DeviceQueryService.resolve_device()` now
  accepts an optional `required_command` argument that scopes
  candidates to devices actually advertising that command *before*
  name resolution runs, mirroring the existing `kind_hint` scoping
  immediately above it in the same method.
- `RuleAuthoringService.propose()` passes `required_command` through
  when (and only when) the compiled intent's start command is
  `blockInternet`/`allowInternet` -- deliberately scoped to just this
  command pair so ordinary scheduled on/off rules resolve exactly as
  they did before, byte-for-byte unaffected.
- `request_classification.parse_immediate_internet_access_intent()`
  now also excludes a relative-delay clause ("in 30 mins", "in an
  hour", "in 2 hrs") the same way it already excludes `AT_TIME`/window/
  rule-authoring language. Nothing in the codebase implements a
  relative-delay schedule today, so this restores the pre-0.10.377
  behaviour of falling through to the model for that specific,
  currently-unsupported phrasing, rather than mishandling it
  deterministically.

## Validation

- `python -m pytest -q` -- 662 passed (5 new: two relative-delay
  negative-match cases in
  `test_immediate_internet_access_intent_matches_only_unscheduled_block_allow`;
  `test_rule_authoring_service.py`'s
  `test_scheduled_block_finds_the_capable_device_not_the_exact_name_match`
  reproducing the exact live "TV" vs. "Block Google-TV-Streamer" pair
  for the scheduled grammar, and
  `test_scheduled_on_off_resolution_is_unaffected_by_capability_scoping`
  confirming ordinary on/off scheduled rules are untouched).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.378
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "block the tv at 10pm" should now resolve to
  "Block Google-TV-Streamer" and queue the scheduled block/allow rule
  pair; "block the tv in 30 mins" should no longer produce a garbled
  device-name resolution failure (falls through to the model, since no
  relative-delay scheduling exists yet); "block the tv" and "allow the
  tv" (the immediate case) are unaffected by this release and already
  confirmed working live.
