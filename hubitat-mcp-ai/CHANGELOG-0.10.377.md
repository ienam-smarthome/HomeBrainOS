# 0.10.377

## Fixed

Live bug report, caught immediately: asking "block the tv" turned the TV's
power off instead of blocking its internet access. Investigating against
the real hub found two compounding gaps.

First, there is no deterministic path anywhere in the codebase for an
*immediate* block/allow-internet request. `RuleAuthoringService` already
recognises "block X"/"allow X" as valid Rule Machine action verbs, but its
own `_intent()` gate requires either an "at &lt;time&gt;" clause or a
"from X to Y" window before it will even look at the prompt -- both the
single-trigger and window grammars are scheduling-only by construction.
A bare "block the tv" matches neither, so it fell straight through every
deterministic path in the codebase to the model's own tool-selection
loop -- and with no "block internet" tool call available to reach for,
the model interpreted "block" as "turn off" and dispatched a plain power
command instead. That's actively wrong for a parental-control-style
feature, not just imprecise: turning a device's power off is trivially
reversed and is not equivalent to blocking its network access.

Second, even a scheduled "block the tv at 10pm" would likely have
resolved the wrong device. The real hub has two devices both plausibly
named "tv": a plain power-switch labelled exactly "TV", and a separate
network-integration device labelled "Block Google-TV-Streamer" that is
the only one of the two that actually advertises `blockInternet`/
`allowInternet`. Ordinary name resolution picks the exact-label switch
every time (confidence 1.0, no contest) -- `RuleAuthoringService` only
checks whether the *resolved* device supports the required command
*after* resolving by name alone, so it would have rejected the switch
with "does not advertise the required command" rather than trying the
streamer device that was sitting right there.

## Fix approach

Added `parse_immediate_internet_access_intent()` to `request_classification.py`:
a narrow `fullmatch` over "block X"/"disable X"/"allow X"/"enable X"
phrasing that explicitly excludes anything carrying an `AT_TIME` clause, a
"from X to Y" window, or explicit rule-authoring language ("automation",
"rule", "schedule") -- those all still route to `RuleAuthoringService`,
completely unchanged. This only ever catches the immediate case that
previously had no deterministic handling at all.

Added `device_target_resolver.device_commands()` and
`resolve_capable_device_candidate()`: the latter filters candidates down
to devices that actually advertise the required command *before* running
the existing name-resolution scoring, rather than resolving by name first
and checking capability afterward. Against the real "TV" vs. "Block
Google-TV-Streamer" pair, this finds the streamer directly instead of
picking the switch and then failing.

Added `UnifiedMCPAgent._internet_access_outcome()` in `homebrain_agent.py`,
wired in right after the firmware fast paths. Resolves the target through
`resolve_capable_device_candidate`, then dispatches
`blockInternet`/`allowInternet` directly via `hub_call_device_command`
with `waitFor`-based verification against the `internetAccess` attribute
(confirmed live: the real device reports `internetAccess: "allowed"` and
supports `blockInternet`/`allowInternet` as commands, unlike `switch`,
which is what on/off verification already uses) -- the same
verified-dispatch pattern already used for on/off/toggle device control,
just with the attribute name the real network-integration device
actually reports. Ambiguous or missing-capability resolutions get the
same disambiguation-prompt/clear-error handling every other deterministic
control path already uses, rather than silently substituting a different
device.

This release deliberately only touches the *immediate* (non-scheduled)
case. `RuleAuthoringService`'s own resolution (used for "block X at
&lt;time&gt;"/"...from X to Y") still resolves by name first and validates
capability after, so a scheduled block/allow request could still pick the
wrong device today -- left as a follow-up rather than risking a change to
that heavily-tested, broadly-scoped resolution path in the same release
as the urgent immediate-case fix.

## Validation

- `python -m pytest -q` -- 660 passed (9 new: `test_live_soak_correctness.py`'s
  `parse_immediate_internet_access_intent` positive/negative matches;
  `test_device_target_resolver.py`'s `device_commands` shape-handling test
  and two `resolve_capable_device_candidate` tests (one reproducing the
  exact "TV" vs. "Block Google-TV-Streamer" pair from the live hub, one
  covering the no-capable-device case); `test_homebrain_agent.py`'s five
  full-agent integration tests using the exact real device shapes pulled
  from the live hub -- immediate block finds the streamer not the switch
  and never touches the model, immediate allow targets the same device,
  an unconverged dispatch reports uncertainty rather than silent success,
  a scheduled "at 10pm" request is left untouched for RuleAuthoringService,
  and a request with no capable device gets a clear error instead of a
  wrong device).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.377
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "block the tv" against the real hub should now
  resolve to "Block Google-TV-Streamer" (device 6923) and report
  "internet access blocked" with `"model": null`; "allow the tv" should
  unblock the same device; "block the tv at 10pm" should still reach
  RuleAuthoringService exactly as before (unaffected by this release).
