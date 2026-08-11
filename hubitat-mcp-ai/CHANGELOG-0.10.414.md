# 0.10.414

## Why this release

Live testing right after 0.10.413 merged showed "What's my current power
usage?" still failing -- not with the old denial message, but with a new,
unrelated one: "I don't see a device mentioned in your last message. Which
device would you like me to look for?" This is a whole-house aggregate
query with no specific device to ask about, so that message could not be
correct. Tracing the evidence trail (5 model rounds, 6 tool calls, every
call reporting `success: true`) found the real gap: 0.10.413 only fixed
`homebrain_filter_devices`'s tool description, and the model did retry
`attribute="valueStr"` there successfully -- but it never carried that
discovered attribute name forward into the following
`homebrain_query_devices` calls, which stayed on `attribute="power"` for
both `count` and `top`. `query_devices()` correctly does not apply the
`value`/`valueStr` generic fallback to its own cross-device scan (that
stays deliberately opt-in, per the existing code comment about not sweeping
in unrelated devices' differently-meaning generic readings), so it returned
a structurally valid but empty result (`count: 0`, `winner: null`) with no
signal to retry. With the tool-round budget then exhausted and nothing
concrete in the transcript, the model's final unconstrained answer
defaulted to a generic "which device" clarification instead of admitting
it found nothing or retrying correctly.

## Fixed

**`homebrain_query_devices` now returns an explicit `hint` field whenever
a query comes back empty and a scanned device actually carries the reading
under `valueStr`/`value`.** The generic fallback itself is still never
applied inside the aggregate scan -- only the *signal* that it would have
mattered is now surfaced, so the model can retry with the concrete
attribute name (`valueStr`, then `value`) instead of silently treating an
empty result as final or asking the user to name a device that was never
ambiguous to begin with. The tool's `attribute` schema description now
tells the model to follow that hint rather than fall back to a
device-clarification question, since this class of query is always a
whole-house/aggregate read.

## Validation

- `python -m pytest -q` -- 856 passed. New coverage in
  `test_device_query_service.py`: an empty `power` scan against a
  valueStr-only meter returns a `hint` naming the fallback attribute; an
  empty scan with no fallback-capable device omits the `hint` field
  entirely (so it never appears for a genuinely correct "no such reading"
  answer).
- `python scripts/run_release_gate.py`
- `python scripts/validate_addon.py`
- `python scripts/validate_release_consistency.py` -- 0.10.414
- `python scripts/analyze_imports.py` -- `orphan_modules: []`
