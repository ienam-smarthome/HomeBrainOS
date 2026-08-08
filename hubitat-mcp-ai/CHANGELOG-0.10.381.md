# 0.10.381

## Why this release

Live testing after 0.10.380 worked through device control, rules, rooms,
apps, and confirmation-flow checks -- everything passed except one: "turn
on Livingroom Light 2" succeeded, and the immediate follow-up "turn it
off" came back "Unresolved" with an unrelated disambiguation prompt
instead of turning the same device back off. Reported live, with the
explicit expectation that the assistant "should have remembered" the
device it had just acted on.

## Fixed

**A pronoun follow-up to a device-control command ("turn it off", "switch
it on") did not resolve to the device just controlled.** The read-side
follow-up path already solved this for readings -- after "what's the
kitchen temperature?", a follow-up "what's its humidity?" correctly
reuses the resolved device via a per-session `_selected_devices` slot.
Nothing wrote to that slot after a *control* command, though:
`_routine_control_outcome` never recorded which device a successful "turn
on X" actually landed on, and `routine_control_arguments()` has no
pronoun awareness at all -- it hands `"it"` straight through as a literal
`device_names` entry, which `DeviceControlService`'s fuzzy name resolver
has no way to match, producing exactly the live-observed "Unresolved"
result with an unrelated disambiguation offer.

The fix has two parts, both in `homebrain_agent.py`:

- `_routine_control_outcome` now records the resolved device's label into
  `self._selected_devices[session_key]` whenever a control command
  resolved to exactly one device and succeeded -- the same session slot
  the read-side follow-up already uses, so both sides of "the thing we
  were just talking about" agree on one source of truth. A command that
  matched more than one device (a room-wide "turn off the kitchen
  lights", or "turn on hallway light and kitchen light") deliberately
  does *not* seed this slot -- there is no single "it" to remember, and
  guessing which one the user meant next would be worse than making the
  follow-up ask again.
- A new `_resolve_pronoun_control_target` helper substitutes a bare
  pronoun (`it`, `it's`, `its`, `that`, `that device`, `this`, `this
  device`) with the session's last-selected device *before*
  `DeviceControlService` ever sees it, using a shared `is_pronoun_reference`
  helper promoted out of `contextual_read_fast_path.py` (previously a
  private set only that module's read-side parsers could see). When
  nothing has been controlled or selected yet in a session, the pronoun is
  left as-is and resolution fails exactly as it did before this release --
  there is nothing honest to substitute, and a pronoun follow-up must
  never borrow a *different* session's last-controlled device.

This only changes behaviour for the deterministic instant control fast
path (`routine_control_arguments`) -- scheduled control ("turn it off at
10pm") and the internet-access block/allow path are unaffected; both
already have their own distinct target-resolution flows.

## Validation

- `python -m pytest -q` -- 675 passed (3 new: a pronoun follow-up reuses
  the just-controlled device within the same session; a pronoun follow-up
  in a session that never controlled a device is left unresolved rather
  than borrowing another session's device; a multi-device control command
  does not seed a pronoun target).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.381
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
- Live re-check pending: "turn on Livingroom Light 2" followed immediately
  by "turn it off" should now turn the same device back off instead of
  returning "Unresolved".
