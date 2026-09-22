# Hubitat MCP AI 0.16.8

## Provider-free semantic routine controls

Live 0.16.7 testing showed that host grounding and deterministic execution were
correct, but clear semantic requests such as:

```
increase hallway brightness
make Hallway Light 1 and Hallway Light 2 brighter
```

still spent roughly 5–7 seconds in the reasoning provider before reaching the
same deterministic control adapter.

0.16.8 adds a narrow host semantic fast path for clear, anchored brightness and
heating requests. It recognizes unambiguous relative and absolute forms, builds
the same typed SemanticPlan used by the model path, then runs the existing host
grounding and deterministic verification unchanged.

Examples now eligible for zero-model planning include:

- `increase hallway brightness`
- `lower hallway brightness a little`
- `raise bedroom 1 brightness by 15%`
- `dim bedroom 1 by 10%`
- `make kitchen much brighter`
- `turn the living room lights up`
- `make bedroom one warmer`
- `lower the living room temperature a little`
- `raise Bedroom 1 temperature by half a degree`
- `set Bedroom 2 temperature to 20.5 degrees`

The fast path deliberately does not handle questions, future/recurring
requests, or pronoun-only targets such as `make it brighter`; those continue
through contextual/model planning.

## Grounding remains authoritative

The parser only identifies intent. It does not choose Hubitat IDs or bypass
capability checks.

Targets still pass through the complete host identity world introduced in
0.16.7. Room grounding, canonical device binding, multi-device selection,
capability checks, live precondition reads, command dispatch, and verification
remain deterministic.

Spoken room numbers are normalized for host matching, so wording such as
`bedroom one` can bind to canonical room `Bedroom 1` without a provider
round.

## Expected live effect

A clear request such as `increase hallway brightness` should now show:

```
semantic_fastpath_plans: 1
semantic_target_grounded: 1
semantic_relative_controls: 1
model_rounds: 0
model: null
```

while preserving the same final deterministic control arguments:

```json
{
  "room": "Hallway",
  "command": "adjust_level",
  "device_kind": "light",
  "delta": 20
}
```

This targets the largest latency component observed in 0.16.7 without changing
MCP session/concurrency semantics.
