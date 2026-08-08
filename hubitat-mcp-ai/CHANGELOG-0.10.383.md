# 0.10.383

## Why this release

Live-tested immediately after 0.10.382: "turn off the lights" correctly
turned off all 13 real lights in the house, but the reporting made it
look like the assistant had no idea which of them were actually on --
every light was named as "Turned off", including any that were already
off before the command ran. Reported live alongside a question about
whether the assistant can tell which lights are on at all.

## Improved

**Device-control results now distinguish devices that actually changed
state from devices that were already in the requested state.** The
command itself is unchanged -- it is still dispatched to every matched
device regardless of its cached state, on purpose: HomeBrainOS's device
cache can be a little stale, and skipping a device because a stale
reading claimed it was "already off" risks silently failing to comply
with an explicit "turn off the lights" for a light that is actually still
on. What changes is the *reporting*.

`DeviceControlService.execute()`'s per-device dispatch now reads the
target's cached (or, for `toggle`, live) "switch" attribute before
sending the command and compares it against the requested state, tagging
each result `changed` and `already_in_state`. A device with no known
prior reading defaults to `changed=True` -- silence about prior state is
never read as "already in state" and dropped from the summary, only an
explicit matching reading is. `deterministic_tool_presenter.py`'s control
message now splits on this flag: devices that actually flipped state are
named as before ("Turned off Kitchen Light and Bedroom 1 Light."), and
any devices that were already in the requested state are called out
separately ("2 were already off: Toilet Light and Hallway Light 1."),
with a plain "Nothing to do -- every matched device was already off."
when nothing needed to change. A result with no `changed` flag at all
(an older caller, or an unusual code path) falls back to the prior
wording exactly, so this is additive rather than a behaviour change for
anything outside device control.

## Note

The house's "lights" observed in this test pass are bridged Matter
devices, not Zigbee -- the earlier note in 0.10.382 about mesh/radio
timing applies the same way to a Matter bridge relaying commands to its
fabric, not specifically to Zigbee.

## Validation

- `python -m pytest -q` -- 684 passed (5 new: changed vs already-in-state
  devices are split into separate clauses; an all-already-in-state result
  reports "Nothing to do"; a result without any changed flags keeps the
  prior wording; a device whose cached state already matches the command
  is still dispatched to, just flagged; a device with no known prior
  state defaults to reported as changed).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.383
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "turn off the lights" with some lights already
  off should now report only the ones that actually turned off, with a
  separate note for the ones that were already off.
