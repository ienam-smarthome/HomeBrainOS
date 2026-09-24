# Hubitat MCP AI 0.16.32

## Boundary-scoped provenance wording and cached causal candidate planning

The live 0.16.31 Hallway verification proved the zero-model clarification path:

```text
why did hallway lights turn on?
-> Hallway Light 1 / Hallway Light 2
model_rounds: 0
tool_calls: 1
total: 3 ms
```

The selected-device continuation also remained deterministic, but the live trace
showed two refinements.

## Boundary-scoped command provenance wording

A reporting-source answer previously began:

```text
Hubitat did not record a command-on producer for Hallway Light 1.
```

That wording was too broad because the same evidence page could contain older
`command-on` rows. The intended claim was only that no command producer aligned
with the requested ON boundary.

0.16.32 now says:

```text
Hubitat did not record a command-on producer aligned with this ON transition
for Hallway Light 1.
```

This keeps the claim scoped to the transition being investigated without
changing the underlying provenance rules.

## Cached causal candidate planning

The 0.16.31 Hallway continuation spent about one second on a whole-home bulk
live-context read used only to rediscover Hallway controller and occupancy
candidates. The authoritative identity cache was already warm.

0.16.32 reuses that fresh structural identity snapshot for bounded secondary
candidate selection when it contains sufficient metadata:

- room and label identity;
- controller capabilities;
- motion/presence capabilities;
- attribute-shape evidence for occupancy-capable rows.

The same existing candidate ranking is used, including exact-room preference,
label affinity, controller ranking, and occupancy-source filtering.

If a room/label-associated MotionSensor or PresenceSensor row has no cached
attribute shape at all, HomeBrain falls back to the existing live room filter.
This prevents the optimisation from dropping a real occupancy source when the
cache is structurally too sparse.

## What remains live

Only candidate discovery is cached. Evidence used to explain the event remains
live and bounded:

- selected-device switch history;
- requested command-on/command-off provenance;
- controller event history;
- motion/presence event history;
- bounded subject event history used for recovery-pattern analysis.

No model round is introduced and no causal correlation is upgraded into proof.

## Metric

Adds:

```text
causal_cached_candidate_plan
```

A live Hallway retest should show this counter when the cache is suitable and
should no longer contain the whole-home bulk live-context / room-filter pair in
the evidence receipts.

## Regression coverage

Tests verify that:

- cached identity metadata produces the same top controller and occupancy
  candidates as the existing live room filter;
- sparse occupancy identity metadata forces the safe fallback;
- the deterministic reporting-source path records
  `causal_cached_candidate_plan`;
- cached candidate planning avoids `hub_list_devices` in the regression MCP;
- boundary wording is explicitly scoped to the requested ON transition;
- the provider remains unused and native-log fallback remains unnecessary.
