# 0.10.416

## Why this release

Live testing right after 0.10.415 merged confirmed "What's my current
power usage?" now correctly reports the whole-house Octopus meter. But
two very similarly worded questions asked in the same session, "what's
the current whole house power" and "what's the whole house power",
produced a broken "Unresolved" clarification instead of an answer --
"Which device do you mean: Octopus Meter Current Power, Octopus Meter
Energy Week, or Front Door?" and, even more obviously wrong, "Which
device do you mean: Google Chromecast+, Weather Open-Meteo, or Shower
Light?" for a question about power.

## Fixed

**These phrasings were never reaching the model's tool-calling loop at
all.** `contextual_read_fast_path.py`'s `_NAMED_ATTRIBUTE` regex requires
a device name before the trailing attribute word ("power"), and with no
real device name in the sentence, its non-greedy name group backtracked
onto the aggregate-scope qualifier phrase itself -- "whole house" /
"current whole house" -- and treated that as a literal device name to
resolve. This is the exact same backtracking failure mode already fixed
for bare "the"/"current" (see `is_pronoun_reference`); "whole house",
"whole home", "entire house", and "entire home" (with or without a
leading "current") are now recognised the same way, so these questions
fall through to the model's tool-calling loop, where the 0.10.414/415
whole-house-meter guidance already handles "current power usage"
correctly.

**Even within that broken path, the offered candidates made no sense.**
`device_target_resolver.py`'s "missing" outcomes (nothing scored above
the confidence floor) were still handing back the raw top-3 by fuzzy
score, unfiltered by that same floor -- so a near-zero-scoring phrase
like "whole house power" could surface arbitrary, unrelated devices
(a front door lock, a Chromecast, a weather integration) as if they were
plausible guesses, because ties were broken alphabetically rather than by
relevance. Both "missing" branches now filter their reported alternatives
to the confidence floor already used to decide the outcome, mirroring the
padding fix already applied to the "ambiguous" branch for a real
"HallwayCAM" regression -- a "missing" resolution with unrelated
candidates below the floor now correctly reports "I could not find a
device named ..." instead of offering a choice.

## Validation

- `python -m pytest -q` -- 861 passed. New coverage in
  `test_contextual_read_fast_path.py` (whole-house/whole-home aggregate
  phrases fall through to `None`, not a literal device name) and
  `test_device_target_resolver.py` (a "missing" resolution reports zero
  alternatives rather than below-floor padding).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.416
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
