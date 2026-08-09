# 0.10.395

## Why this release

Live-tested against 0.10.394 immediately after that fix. "What's the
current temperature" against a real house was offering only 3 of many
real temperature-reporting devices as disambiguation choices ("Livingroom
temp & humidity, Bedroom 1 Meter, or Thermostat"), while a separate
"show all temp sensors" query in the same session confirmed 12 devices
actually report temperature -- Hallway Meter, Bathroom meter, Bedroom 2
TRV, Fridge Meter, Hallway TRV, Livingroom TRV, Hub Info, and Weather
Open-Meteo were all silently missing from the choice list.

## Fixed

**A bare-attribute disambiguation query ("what's the current
temperature", "what's the battery") could silently drop real reporters
from its own choice list, via two independent hardcoded caps.**

1. `DeviceQueryService.resolve_device()`'s bare-attribute guard --
   which widens a bare attribute word into a full disambiguation once it
   detects more than one device reports that attribute -- only ever
   offered the first 3 reporters (`reporters[:3]`, sliced in whatever
   order the inventory happens to return them, not ranked by relevance
   or completeness), even when many more devices genuinely reported the
   attribute. It also only fired when `resolve_device_candidate` had
   already picked one specific device with high confidence by
   name-string similarity -- if that same generic resolver instead
   returned its own "ambiguous" result first (equally plausible for a
   bare attribute word, which isn't really a device name at all), the
   bare-attribute widening never ran, and the generic resolver's own
   3-item, name-similarity-ranked cap was shown instead.
2. Both gaps are now closed: the widening fires whenever the requested
   text normalizes to a known attribute word and the resolution wasn't
   a genuine exact-name match (not only the narrow "confidently picked
   one device" case), and every device that actually reports the
   attribute is offered -- never truncated to a fixed count.

## Validation

- `python -m pytest -q` -- 713 passed (2 new: `resolve_device()`'s
  bare-attribute guard offers all 6 reporters in a fixture designed to
  exceed the old 3-item cap; an end-to-end agent-level test confirms
  "what's the current temperature" against 6 real reporters names every
  one of them in the response, not just the first 3).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.395
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
