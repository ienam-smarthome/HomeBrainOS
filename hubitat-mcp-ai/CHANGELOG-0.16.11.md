# Hubitat MCP AI 0.16.11

## Causal inferred-state retry before empty-subject stop

0.16.10 correctly protected switch-scoped history, causal UTC log windows,
configuration-vs-execution evidence, and broad inventory detours. Live testing
still exposed one remaining sequencing gap:

```
Why did Dehumidifier 2 turn on?
```

The model called:

```json
{"name":"dehumidifier 2"}
```

without an explicit history attribute. The first mixed 20-row event page
contained one recent `switch=off` row but not the older `switch=on` row,
because RTT, power, energy and power-factor telemetry had crowded it out.

HomeBrain correctly inferred `attribute=switch` from that page, but then
immediately applied the causal empty-subject stop because the single switch row
could not form a bounded interval. The 0.16.10 switch-scoped retrieval logic was
therefore never reached.

0.16.11 fixes that ordering deterministically.

## New host retry

For a causal request only, after a successful
`homebrain_device_history` call, HomeBrain now performs one host-generated retry
when all of these structural conditions hold:

- the model did not explicitly request an attribute;
- the returned mixed page inferred exactly one supported binary state attribute;
- no bounded interval was established;
- the source event page filled the requested bounded page.

The retry:

- reuses the canonical resolved device label;
- sets the inferred binary attribute explicitly;
- raises the history limit to the local 50-row ceiling;
- preserves the same history horizon;
- consumes no additional model round or model-directed read budget.

For the live Dehumidifier 2 case, the host-generated retry becomes:

```json
{
  "name": "Dehumidifier 2",
  "attribute": "switch",
  "limit": 50,
  "hours_back": 24
}
```

That invokes the 0.16.10 switch-scoped upstream path, allowing the older
`switch=on` boundary to remain visible even when the generic event stream is
dominated by metering telemetry.

## Empty-subject stop remains fail-closed

The causal stop itself is not weakened.

If the scoped retry still establishes no bounded or open active interval,
HomeBrain still stops before expanding into controller, sensor, location, app,
rule or log evidence. This preserves the current-turn causal fence and avoids
constructing a causal story for an event that current evidence did not
establish.

## Observability

Adds:

- `causal_inferred_attribute_retry`

This counter proves that the host recovered an inferred-state causal subject
before applying the empty-subject stop.

## Regression coverage

The 0.16.11 regression reproduces the live shape:

1. a full generic event page containing one recent `switch=off` row and noisy
   RTT/power/energy events;
2. deterministic inference of `switch`;
3. zero bounded intervals on the first pass;
4. one host-generated scoped retry;
5. recovery of the 22:07:37 -> 22:38:13 Dehumidifier 2 interval.

It also verifies that no retry is generated when an interval already exists or
when the original page was not full.
