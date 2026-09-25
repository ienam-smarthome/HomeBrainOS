# Hubitat MCP AI 0.16.43

## Model composite occupancy topology

The Hallway live investigation exposed an important topology detail: Hallway Soft
Sensor is not an independent motion source. Aqara M3 derives it from the same
Hallway occupancy inputs used by the upstream lighting automation: Hallway FP300
and Hallway Aqara P1.

0.16.43 teaches the deterministic causal layer that distinction.

### What changed

- causal_known_automations_json can now describe derivedSensors with their
  source devices and an optional semantic kind such as occupancy.
- The shipped Hallway topology records:
  - source trigger Hallway FP300 (Hubitat alias Hallway FP300 sensor);
  - source trigger Hallway Aqara P1;
  - derived occupancy signal Hallway Soft Sensor;
  - targets Hallway Light 1 and Hallway Light 2.
- A direct configured source-trigger edge remains stronger evidence than a derived
  sensor edge.
- If only the derived sensor aligns with the requested transition, HomeBrain can
  still identify the configured Aqara route as topology-consistent, while stating
  that it cannot tell which underlying source sensor fired.
- The concise causal answer now adds a **Composite signal** explanation and avoids
  presenting the soft sensor as a second independent confirmation.
- When composite topology is available, the older generic shared-reporting-path
  sentence is suppressed to avoid repeating a weaker explanation.
- Technical metrics add causal_composite_sensor_match.

### Metric safety fix

0.16.42 introduced causal_known_automation_match at the orchestrator/presenter
layers but did not add it to the fixed RequestMetrics.ALLOWED_COUNTERS set.
That could raise an unsupported-counter error when a live known-automation match
actually occurred. 0.16.43 registers both:

- causal_known_automation_match
- causal_composite_sensor_match

and adds regression coverage for their request-metric and presentation paths.

### Causal boundary

Composite topology is configuration evidence, not execution provenance. A derived
signal can support the same upstream Aqara/SmartThings route, but it cannot prove:

- that the external automation executed for this exact transition;
- which underlying source sensor caused the automation;
- that a derived sensor is an independent confirmation of one of its own sources.

Direct Hubitat command provenance remains stronger than all configured external
topology and timing correlation.

### Expected Hallway proof

For a future Hallway Light 1 causal investigation, Technical Details may contain
both a direct source-trigger match and a Hallway Soft Sensor derived match. The
main answer should explicitly state that the soft sensor is derived from Hallway
FP300/Hallway Aqara P1 and is not independent evidence.
