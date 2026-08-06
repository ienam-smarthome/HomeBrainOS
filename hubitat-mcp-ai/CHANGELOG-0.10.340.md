# Hubitat MCP AI 0.10.340

## Fixed

- `device_target_resolver.resolve_device_candidate()` could report a
  genuinely nonexistent device category as "ambiguous" instead of
  "missing" whenever the house had 2+ devices (i.e. always). The
  token-incompatibility guard in `_score()` already caps a mismatched-kind
  score at 0.69 as a deliberate "not a real match" signal, but nothing
  downstream checked that floor once more than one candidate existed --
  only the single-candidate path did. Found via live testing against a
  real 84-device house: asking about a nonexistent "Garage Door" resolved
  as ambiguous among `Fridge Door` / `Front Door` / `Bedroom 1 TRV` at
  confidence 0.69, and unrelated queries like "EV Charger" or "Sprinkler"
  scored as low as 0.42 while still returning device guesses.
- Adds a `missing_floor` parameter (default 0.70, just above the
  token-incompatibility cap) to `resolve_device_candidate()`. When the top
  ranked score falls below it, the request now classifies as `missing`
  (and increments `device_resolution_missing`, per 0.10.338) instead of
  `ambiguous`, regardless of candidate count.

## Validation

- Adds `tests/test_device_target_resolver.py::test_genuinely_absent_device_type_is_missing_not_ambiguous`,
  using a heterogeneous mixed-device-kind inventory (the existing `LIGHTS`
  fixture is lights-only, which is exactly why this gap went uncaught --
  a lights-only inventory never produces the "several irrelevant
  candidates from different kinds" shape that triggers it).
- Adds `test_same_kind_ambiguity_is_unaffected_by_the_missing_floor` and
  `test_exact_and_semantic_matches_still_resolve_in_mixed_inventory` to
  confirm the fix doesn't affect genuine ambiguity (same-kind devices,
  e.g. two hallway lights) or exact/semantic matches.
- `python3 -m pytest -q` (515 passed).
- `python3 scripts/validate_addon.py` and `analyze_imports.py` both clean.
