# Hubitat MCP AI 0.16.3

## Host-owned semantic entity grounding

A live 0.16.2 Hallway test exposed a new class of error that was not a language
or transport failure. HomeBrain understood "increase hallway brightness", but
the model selected a similarly named **Hallway dimmer** controller instead of
the **Hallway** room that contains the real dimmable lights.

The Hubitat UI confirmed the distinction:

- `Hallway dimmer` is the Hue/Matter remote/controller parent;
- its child entries are buttons;
- `Hallway Light 1` and `Hallway Light 2` are the real
  `Generic Component Dimmer` actuators in room `Hallway`;
- those real lights expose `Actuator`, `ChangeLevel`, `Light`,
  `Switch`, and `SwitchLevel`, and report a current `level`.

### Entity grounding

The reasoning model still interprets the user's requested action, but HomeBrain
now validates the target against the semantic world before compiling a command.

When:

1. the user explicitly mentions exactly one real room;
2. no full device label is explicitly mentioned; and
3. that room advertises the ability required by the requested action;

the host binds the plan to the canonical room even if the model guessed a
similarly named device.

A fully named device still stays device-scoped.

This is a generic entity-linking rule, not a Hallway-specific phrase patch.

### Tighter brightness ontology

0.16.1 deliberately broadened brightness inference beyond labels containing
"Light". 0.16.3 tightens the *write* side of that ontology:

- a bare state attribute named `level` is no longer sufficient to infer a
  writable brightness actuator;
- non-Light devices must advertise actual level-control capability/command;
- non-Light controller/button components without `Actuator` are excluded even
  if bridge metadata exposes `SwitchLevel` or `setLevel`;
- existing fail-closed exclusions for fans, shades/doors, audio volume, and
  thermostat/setpoint devices remain.

The semantic world and deterministic device executor continue to share the same
`is_brightness_device()` predicate.

### Evaluation

The semantic model-evaluation runner now evaluates the final **grounded**
semantic interpretation rather than raw model output alone. This means a model
can make a recoverable entity-selection mistake and the evaluation still checks
whether HomeBrain's final host-grounded plan is correct.

### Observability

Add the privacy-safe counter:

- `semantic_target_grounded`

so live traces show when HomeBrain corrected/canonicalized a model-selected
entity before execution.

### Regression coverage

Tests cover:

- a Hue-style dimmer remote/controller parent with level-like metadata is not a
  semantic brightness actuator;
- `level` telemetry alone cannot create a writable brightness ability;
- real Hallway dimmer lights remain brightness-capable;
- room-wide Hallway brightness excludes the remote parent and selects the two
  real lights;
- "increase hallway brightness" is grounded to the Hallway room even when the
  model proposes the similarly named Hallway dimmer device;
- "set Hallway Light 1 to 70%" remains correctly device-scoped;
- the standalone semantic evaluation corpus now includes the controller/light
  name-collision scenario.
