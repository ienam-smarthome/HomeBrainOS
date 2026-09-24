# Hubitat MCP AI 0.16.33

## Sensor correlation fidelity and cached-plan fallback visibility

The live 0.16.32 Hallway trace confirmed the boundary-scoped provenance wording:

```text
Hubitat did not record a command-on producer aligned with this ON transition
for Hallway Light 1.
```

It also exposed two correctness details in bounded secondary correlation.

## Prefer the nearest OFF-boundary sensor edge

For the latest Hallway Light 1 OFF boundary:

```text
light OFF:              20:28:40.810
Hallway Soft inactive:  20:28:41.694   (+0.884 s)
older Soft inactive:    20:28:15.306   (-25.504 s)
```

The previous correlator only admitted inactive sensor edges before a light OFF.
It therefore rejected the near-after +0.884 s edge and paired the light with the
older -25.504 s edge.

0.16.33 keeps the established 45-second pre-OFF window but also allows a narrow
2-second post-boundary recording-order slop. Candidate ranking still uses
absolute distance, so the +0.884 s edge wins over the unrelated -25.504 s row.

This is timing correlation only. The change does not promote a near-after edge
into proof that the sensor caused the light transition.

## Preserve sensor reporting-source provenance

Correlated sensor rows now retain structured `producedBy` metadata.

The live Hallway trace shows both:

- Hallway FP300 sensor
- Hallway Soft Sensor

being reported into Hubitat through:

```text
Matter Aqara M3
```

When multiple checked sensors share one reporting source, deterministic synthesis
now explicitly states that their matching timing is **not independent upstream
corroboration**. The shared producer identifies the reporting path, not the
automation or action that initiated the light/device change.

## Direction-aware OFF wording

The old sentence:

```text
inactive edge(s) shortly before observed OFF boundaries
```

is replaced with direction-aware timing such as:

```text
inactive edge(s) correlated with observed OFF boundaries
(0.125s before, 0.884s after, ...)
```

This avoids hiding recording-order inversions.

## Cached-plan fallback metric

0.16.32 introduced:

```text
causal_cached_candidate_plan
```

The first live 0.16.32 Hallway run still used the whole-home bulk context. That
is a valid safe fallback when the fresh structural identity cache is too sparse
to prove motion/presence attribute exposure.

0.16.33 adds:

```text
causal_cached_candidate_plan_fallback
```

so this case is observable separately from a successful cached candidate plan.

A subsequent run while the richer live-context snapshot remains inside the
identity TTL may show `causal_cached_candidate_plan: 1`; if it still falls
back, the new metric makes that behavior explicit for the next optimisation.

## Regression coverage

Tests verify that:

- a +0.884 s inactive edge is preferred over a stale -25.504 s inactive edge;
- structured sensor `producedBy` data survives correlation;
- two sensors reported through Matter Aqara M3 are labelled non-independent;
- rendered OFF correlations expose before/after direction;
- the cached-plan fallback metric is accepted and presented.
