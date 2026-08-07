# 0.10.367

## Fixed

- Whole-home power/energy queries against a dedicated meter device (e.g. an
  Octopus Energy / Home-Assistant-bridged sensor) could take well over two
  minutes because the model discovered the correct attribute name by slow
  trial and error: it would try `power` first, get an error listing the
  device's real attributes, then try `value`, then `valueStr`, each retry
  costing a full slow cloud-model round trip (~20-25s observed per round in
  live testing, 5 tool calls across 6 model rounds, 147.9s total).

## Context

0.10.365 taught the model to look for a dedicated whole-house meter device
before summing monitored plugs, which was correct and worked. It didn't tell
the model which attribute name that meter typically reports under, so once
it found the device it still had to guess. This release tightens that same
system-prompt guidance with an explicit hint: this class of meter device
very often reports its reading as `value` or `valueStr` rather than `power`,
so try those directly instead of guessing `power` first and retrying after
it fails.

**This is a prompt-guidance change, not a deterministic code fix.** It steers
the model's exploration order but does not guarantee it will always pick the
efficient path first. Unlike the 0.10.364/0.10.365/0.10.366 fixes in this
same area (which changed code behavior deterministically), this one can only
be confirmed by live retesting -- please re-run "What's my current power
usage right now?" and check whether the tool-call count and elapsed time
actually drop.

## Validation

- `python -m pytest tests/ -q` -- 610 passed (no new tests added: this is a
  prompt-string-only change with no new deterministic behavior to assert on
  beyond what 0.10.364-0.10.366 already cover).
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py`
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
