# Hubitat MCP AI 0.16.28

## Occupancy candidate validation and recovery-order parsing

The first live 0.16.27 Bedroom 1 Light test confirmed that the short-boundary
provenance fix worked: the request stayed deterministic, model-free, and used
the external Hue reporting-source path.

That live run exposed two narrower secondary-analysis gaps:

1. `Bedroom 1 FP300 humidity` and `Bedroom 1 FP300 lux` were selected as
   occupancy candidates because they inherited broad PresenceSensor capability,
   even though those child devices did not expose a live presence/motion state;
2. the downstream level-recovery matcher recognized
   `ON -> level -> setLevel`, but not the equally valid
   `ON -> setLevel -> resulting level` ordering observed on another transition.

0.16.28 fixes only those two gaps. The 0.16.27 short-boundary provenance logic is
unchanged.

## Require an exposed occupancy state

Motion/presence candidate selection now requires both:

- an advertised occupancy capability; and
- the concrete live state attribute HomeBrain intends to query.

Selection rules:

- PresenceSensor + exposed `presence` -> query `presence`;
- otherwise MotionSensor + exposed `motion` -> query `motion`;
- otherwise the device is not eligible for a bounded occupancy-history slot.

This prevents bridge child devices such as humidity/lux measurements from being
queried as occupancy sources merely because they inherit broad parent
capabilities.

A device advertising both PresenceSensor and MotionSensor can still be used when
only `motion` is concretely exposed; HomeBrain selects `motion` rather than
discarding the real sensor.

## Recovery ordering

The downstream level-recovery detector now recognizes both bounded sequences:

```text
external ON
-> immediate bridge level
-> app setLevel
```

and:

```text
external ON
-> app setLevel
-> resulting bridge level
```

For the first ordering, the level can be described as the initial level.

For the second ordering, the later level is explicitly recorded as a resulting
level and is never mislabelled as an initial level.

The app `setLevel` command still must occur after the ON boundary and remain
within the existing five-second recovery window. Command-first resulting level
events are bounded to two seconds after that command.

## Regression coverage

The existing Bedroom 1 reporting-source regression now includes:

- an FP300 humidity child advertising PresenceSensor but exposing only humidity;
- an FP300 lux child advertising PresenceSensor but exposing only illuminance;
- the real FP300 sensor exposing motion;
- a derived Soft Sensor exposing motion;
- assertions that humidity/lux children are never queried;
- assertions that the real FP300 sensor and Soft Sensor occupy the two bounded
  occupancy slots;
- four level-before-command recovery sequences;
- one command-before-level recovery sequence;
- deterministic wording that distinguishes resulting level from initial level;
- unchanged zero-model / zero-native-log causal finalization.

## Expected live effect

For the Bedroom 1 Light investigation, the bounded secondary pass should no
longer spend sensor reads on:

```text
Bedroom 1 FP300 humidity
Bedroom 1 FP300 lux
```

and should instead investigate concrete occupancy-state devices, including the
real FP300 sensor when it exposes motion/presence state.

The downstream recovery summary should also count command-first recovery
sequences instead of silently missing them.
