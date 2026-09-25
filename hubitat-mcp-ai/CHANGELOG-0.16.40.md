# Hubitat MCP AI 0.16.40

## Reuse warm live-context shape for causal candidate planning

The 0.16.39 Hallway live proof was fast and fully deterministic, but a warm
reporting-source investigation could still fall back to a whole-home live-context
read when the freshest authoritative identity snapshot lacked occupancy attribute
shape.

That fallback is correct but can be redundant: a slightly older live-context
snapshot may still be inside the structural identity TTL and already contain the
attribute names needed to distinguish real motion/presence children from broad-
capability humidity/lux bridge children.

0.16.40 adds a bounded cache-reuse step before the existing live fallback.

### Safety boundary

The optimisation is structural only.

- The freshest identity snapshot remains authoritative for device ID, label,
  room, capabilities, and commands.
- Cached live-context rows are joined only by exact device ID.
- Only attribute shape is borrowed from the cached context.
- Cached state values are not promoted into current causal evidence.
- Controller, motion/presence, subject, and command event histories remain live.
- Writes still invalidate the live-context snapshot.
- If cached context is absent, stale, invalidated, or insufficient, HomeBrain
  uses the existing live room-filter fallback.

### Expected warm-path effect

For the Hallway reporting-source path, when this cache combination is available,
HomeBrain should avoid the extra whole-home live-context plus
`homebrain_filter_devices` discovery pair while preserving the same bounded
controller and motion/presence candidate reads.

The existing `causal_cached_candidate_plan` counter still identifies successful
cached planning. A new counter:

```text
causal_cached_context_shape_plan
```

shows that cached live-context attribute shape was used to make the plan
sufficient.

### Regression coverage

Tests verify that:

1. exact-ID enrichment fills missing motion/presence attribute shape without
   replacing structural identity metadata;
2. broad-capability FP300 humidity/lux children remain excluded from occupancy
   candidates;
3. the end-to-end reporting-source path remains zero-model;
4. the same two controller and two sensor histories are still queried;
5. cached-context shape reuse records its metric and avoids the whole-home device
   refresh;
6. the existing fallback remains available when no suitable cached context exists.
