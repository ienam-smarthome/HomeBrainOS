# 0.10.394

## Why this release

Live-tested against 0.10.390-0.10.393 immediately after that grouped
Tier 1 batch. "Turn off the lamp" against a real ~84-device house
surfaced a genuinely unrelated device -- "HallwayCAM (MQTT)", a camera
-- as a third disambiguation choice alongside the two real lamps ("Big
lamp", "My Floor Lamp"). Not one of the 20 findings from the earlier
full-codebase review; found through direct WebUI testing this round.

## Fixed

**Ambiguous-device disambiguation could pad its choice list with a
completely implausible candidate.** `resolve_device_candidate()`'s final
"ambiguous" branch built its list of choices to offer the user from the
overall top-3 scoring devices in the whole inventory (`ranked[:3]`),
with no minimum-plausibility check -- only the *first two* places in
that ranking are guaranteed to be real contenders (the branch is only
reached once the top score already clears the confidence floor used
elsewhere in this same function to reject a genuinely absent device
category outright). A third-place device can still be whatever happened
to score highest among everything left in the inventory, even when
that score is nowhere near a real match. Live-reproduced: "the lamp"
scored 0.9 against both real lamps but only 0.43 against "HallwayCAM
(MQTT)" -- well below the 0.70 confidence floor already used elsewhere
in this function -- yet the camera was still offered as a button
alongside the two real lamps. Alternatives offered in this branch are
now filtered to only candidates that clear the same confidence floor,
so a genuinely implausible device can no longer be presented as though
it were a real choice.

## Validation

- `python -m pytest -q` -- 711 passed (1 new: "the lamp" against a
  mixed inventory containing two real lamps and one unrelated camera
  device now offers only the two lamps, never the camera, and the
  camera's name is confirmed absent from both the alternatives list and
  the disambiguation message).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.394
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
