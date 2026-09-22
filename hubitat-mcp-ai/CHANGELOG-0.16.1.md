# Hubitat MCP AI 0.16.1

## Fix capability-grounded brightness false negatives for ordinary dimmers

A live 0.16.0 request to increase Hallway brightness returned **Needs input**
without making any tool call because the semantic world model said the Hallway
contained no brightness-controllable devices.

The root cause was architectural rather than phrase-specific: brightness was
only exposed when a device was already classified as a "light". Many real
Hubitat wall dimmers advertise `Switch` + `SwitchLevel` + `setLevel` and
may be labelled simply "Hallway Main", "Landing", etc. They are genuinely
brightness-capable even though they never advertise a literal `Light`
capability or include "Light" in the label.

### Semantic capability fix

- Add a single `is_brightness_device()` capability predicate.
- Recognize semantic brightness from level control
  (`SwitchLevel`, `ChangeLevel`, `setLevel`, or a `level` attribute)
  even when the device is not label/capability-classified as a light.
- Keep fail-closed exclusions for identities with stronger non-light level
  semantics:
  - `FanControl` / `setSpeed`
  - shades/door-position controls
  - audio volume
  - thermostat/setpoint devices
- Use the same brightness predicate in both:
  - semantic world construction/planning
  - deterministic device-control target matching

This removes a class of planner/executor disagreement where the AI either could
not see a real dimmer or could see a capability that the executor later rejected.

### No Hallway-specific patch

There is no room-name or phrase exception. The same ontology applies to any
unlabelled dimmer in any room.

### Evaluation and regression coverage

- Add an unlabelled Hallway dimmer fixture:
  `Switch + SwitchLevel + setLevel`, no literal `Light` capability.
- Verify its room advertises `brightness` to the semantic planner.
- Verify deterministic `adjust_level` matches and controls those dimmers.
- Verify a `SwitchLevel + FanControl` fan is **not** reinterpreted as a light.
- Verify a `SwitchLevel + WindowShade` shade is **not** reinterpreted as a
  brightness device.
- Add a semantic model-evaluation case for
  **"increase hallway brightness"** against capability-grounded Hallway context.
