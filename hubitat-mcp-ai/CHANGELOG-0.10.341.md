# Hubitat MCP AI 0.10.341

## Added

- `rule_authoring_service.py` now recognises single daily triggers with no
  auto-revert window: "turn on Bedroom 1 Light every day at 7am", "lock
  Front Door every day at 10pm", etc. Previously the compiler only
  recognised auto-reverting window schedules ("turn X off from A to B,
  reverting to on at B") -- a plain single-time trigger, arguably the most
  natural way to phrase a daily schedule, had no path through the
  deterministic compiler at all and always fell through to the general
  model-driven route.
- New pattern mirrors the window grammar's four verb families
  (on/off, lock/unlock, close/open, block/allow internet) as one-shot
  actions, each requiring and verifying exactly one advertised command,
  emitting exactly one atomic `hub_set_rule` action through the same
  `rule_machine_proposal_error` validation and duplicate-name check as the
  window path.

## Fixed

- Window-schedule goal extraction broke whenever the daily marker
  ("daily" / "every day" / "everyday") appeared *before* the time clause
  instead of after it -- e.g. "block internet every day from 10pm to 6am"
  silently failed to compile (fell through to the general model path)
  while "block internet from 10pm to 6am every day" worked, purely due to
  word order. Both orderings are equally natural phrasing. The goal slice
  now has the daily marker stripped alongside the authoring-verb prefix
  before pattern matching, fixing this for both the window and the new
  single-trigger path.

## Found via

- Live testing against a real 84-device Hubitat house (not synthetic
  fixtures): pulled real device labels, rooms, and advertised commands via
  `hub_get_device`/`hub_list_devices`, and fed realistic phrasing through
  the actual deployed grammar to find both gaps above.

## Validation

- Adds 8 new tests to `tests/test_rule_authoring_service.py`: single-trigger
  compilation (3 phrasing variants), command-verification rejection using a
  real contact sensor with no lock command, duplicate-rule prevention for
  single triggers, and daily-marker order-independence for the window path
  (both orderings, parametrized).
- `python3 -m pytest -q` (522 passed).
- `python3 scripts/validate_addon.py` and `analyze_imports.py` both clean.
