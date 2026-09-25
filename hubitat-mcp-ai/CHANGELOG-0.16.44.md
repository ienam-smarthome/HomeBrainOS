# Hubitat MCP AI 0.16.44

## Prefer configured source sensors over derived occupancy signals

The 0.16.43 Hallway live proof correctly modeled `Hallway Soft Sensor` as an
Aqara M3-derived occupancy signal from `Hallway FP300` and
`Hallway Aqara P1`, but bounded causal planning still spent its two sensor
history slots on FP300 + Soft Sensor. That could leave the second configured
source sensor, Aqara P1, unread even when it is available to Hubitat.

0.16.44 makes the bounded sensor plan topology-aware.

### What changed

- reporting-source planning now builds the existing capability/attribute-shape
  grounded occupancy candidate pool before applying configured automation
  topology;
- for an automation that targets the requested device transition, configured
  source sensors are preferred over configured derived/composite sensors;
- the planner still performs at most two motion/presence history reads;
- if both Hallway source sensors are available, the expected pair is:
  - Hallway FP300 sensor;
  - Hallway Aqara P1;
- if the second source sensor is unavailable from the safe candidate pool,
  Hallway Soft Sensor can still backfill the bounded slot ahead of unrelated
  room sensors;
- candidate discovery safety is unchanged: topology only reorders candidates
  already admitted by capability and exposed-attribute-shape checks;
- adds `causal_topology_sensor_plan` to Technical Details.

### Causal boundary

This is evidence-selection logic only. It does not turn configured topology into
execution provenance.

A source-sensor event that aligns with the light transition remains timing
evidence. HomeBrain may identify the configured Aqara/SmartThings route, but it
must still say that Hubitat cannot prove the external automation executed that
exact transition unless stronger direct provenance exists.

Derived/composite sensors remain topology evidence and are not counted as
independent confirmations of their own source sensors.

### Expected Hallway live proof

When `Hallway Aqara P1` is exposed to Hubitat as a safe occupancy-history
candidate, a future Hallway Light 1 ON investigation should show:

- `causal_topology_sensor_plan: 1`;
- `causal_sensor_read: 2`;
- live sensor-history reads for Hallway FP300 sensor + Hallway Aqara P1;
- no Hallway Soft Sensor history read solely because it ranked ahead of P1.

If P1 is not available in the safe candidate pool, the fallback remains
FP300 + Soft Sensor rather than forcing a broad or unsafe discovery read.
