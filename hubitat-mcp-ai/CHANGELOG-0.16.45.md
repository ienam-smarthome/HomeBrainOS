# Hubitat MCP AI 0.16.45

## Explain configured-trigger visibility during topology fallback

The 0.16.44 Hallway live proof showed the topology-aware planner working, but it
still had to read Hallway FP300 sensor + Hallway Soft Sensor instead of Hallway
FP300 sensor + Hallway Aqara P1. The answer correctly described the configured
Aqara M3 route, yet it did not explain why P1 was not part of the Hubitat
evidence budget.

0.16.45 makes that distinction explicit without adding any discovery I/O.

### What changed

- topology-aware causal planning now records configured source-sensor visibility
  inside the already-safe Hubitat motion/presence candidate pool;
- the evidence payload distinguishes:
  - configured source sensors;
  - configured sources available in the safe Hubitat candidate pool;
  - configured sources unavailable from that pool;
  - the actual two bounded sensor-history selections;
  - any derived/composite sensor used as a fallback;
- when a configured source is unavailable and a derived signal fills the bounded
  evidence slot, the user-facing answer adds a concise **Trigger visibility**
  line;
- the wording is deliberately scoped: unavailable means not present in the
  current safe Hubitat occupancy candidate pool. It does **not** claim that the
  sensor is absent from Aqara M3, SmartThings, or the upstream automation;
- adds `causal_topology_sensor_fallback` to Technical Details;
- no extra MCP reads, broader inventory discovery, or model round is introduced.

### Hallway example

For the current Hallway topology:

- Aqara M3 “Hallway Lights ON” is configured from Hallway FP300 or Hallway Aqara
  P1;
- Hallway Soft Sensor is a derived/composite signal from those source sensors;
- if P1 is not available in HomeBrain's safe Hubitat motion/presence candidate
  pool, HomeBrain may continue to read FP300 + Soft Sensor;
- the answer now states that P1 was not available from that Hubitat evidence pool
  and that Soft Sensor was used as the bounded topology fallback.

### Causal boundary

This is observability only. It does not convert configured topology into
execution provenance and does not weaken the existing rule that direct Hubitat
command provenance outranks timing correlation.
