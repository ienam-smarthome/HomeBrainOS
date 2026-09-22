# Hubitat MCP AI 0.16.0

## Capability-grounded semantic world model

0.16.0 extends the 0.15 semantic-agent architecture so the reasoning model can
interpret natural language against the actual home's identity/capability
vocabulary without receiving Hubitat protocol details.

### Semantic world context

- Add `semantic_world_model.py`.
- Project cached/live identity data into bounded semantic context containing:
  - canonical room names
  - canonical device labels
  - semantic device kinds
  - semantic abilities such as `switch`, `brightness`,
    `color_temperature`, `heating_setpoint`, `fan_speed`, and common
    sensor abilities
- Never expose device IDs, raw command names, command arguments, or current
  state values to the semantic planner.
- Mark the projection explicitly as `live_state: false`; it is identity and
  capability context only.
- Prefer the existing cheapest safe identity source. A warm identity snapshot
  is reused; a cold request can populate the same bounded identity source the
  deterministic executor would need anyway.

### Capability-grounded thermostat semantics

The typed semantic plan now supports:

- `set_temperature`
- `adjust_temperature`
- `thermostat` targets

Natural-language examples include:

- "make Bedroom 1 warmer"
- "lower the living room temperature a little"
- "set Bedroom 1 to 20.5 degrees"
- "raise Bedroom 1 temperature by half a degree"

The semantic model still does not execute these actions or author Hubitat
payloads.

### Deterministic thermostat execution

HomeBrain's deterministic control adapter now:

1. resolves only devices that explicitly advertise a heating-setpoint ability;
2. excludes generic Thermostat devices that do not expose a heating setpoint;
3. reads live `heatingSetpoint` before any relative adjustment;
4. applies the configured semantic step;
5. clamps the target to the guarded 5-35 range;
6. compiles the standard `setHeatingSetpoint` command;
7. sends positional parameters in the expected array form;
8. verifies the final `heatingSetpoint` through `waitFor`;
9. reports before/after setpoints and preserves the source temperature unit when
   the device supplies one.

If the live setpoint cannot be read, relative adjustment fails closed and no
mutation is sent.

### Policy

- `semantic_default_temperature_step: 1.0`
- small semantic temperature changes use half the configured default;
- large semantic temperature changes use twice the configured default;
- explicit deltas remain explicit;
- heating-setpoint mutations remain routine device controls, while locks,
  security, firmware, internet-access controls, and rule authoring stay on
  their established guarded paths.

### Evaluation and observability

- Extend the semantic model-evaluation corpus with capability-grounded
  thermostat paraphrases.
- The standalone semantic planner evaluation runner now accepts per-case world
  context without executing devices.
- Add metrics for capability-grounded semantic contexts and semantic thermostat
  controls.

### Validation

Regression coverage includes:

- semantic ability derivation from capabilities/attributes/commands;
- proof that planner world context contains no device IDs, wire commands, or
  current-state values;
- world-context bounding;
- fractional thermostat setpoints/deltas;
- semantic default/small/large temperature compilation;
- live setpoint reads for relative changes;
- thermostat-only target filtering;
- safe setpoint clamping;
- fail-closed behaviour when live state is unavailable;
- exact `setHeatingSetpoint` positional payload and `waitFor` verification;
- natural thermostat result presentation;
- end-to-end semantic thermostat routing through the capability world.
