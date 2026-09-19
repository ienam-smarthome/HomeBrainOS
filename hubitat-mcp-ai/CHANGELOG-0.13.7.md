# Hubitat MCP AI 0.13.7

## One bounded motion/presence causal correlation

0.13.7 is the final focused causal-planning improvement after comparing the
0.13.6 Bedroom 3 result with a stronger external analysis.

0.13.6 fixed controller boundary direction, preserved the full overnight light
timeline, and allowed logs plus app configuration in one provenance round. The
remaining gap was evidence selection: several material light turn-ons remained
unexplained even though a same-room presence/motion source could materially test
the trigger hypothesis.

### Capability-grounded trigger sensor hints

The exact-room device filter now emits a second bounded evidence-source hint class:

- `controllerCandidates` for button-capable devices; and
- `triggerSensorCandidates` for devices that explicitly advertise
  `MotionSensor` or `PresenceSensor`.

Trigger sensors are selected from capability metadata, not label guesses.

A lux/temperature-only sensor is therefore not eligible merely because its name
contains "Sensor".

Within the capability-grounded set, exact room metadata is preferred, with
presence/motion/soft-sensor wording used only as a stable tiebreaker.

### One sensor read only when turn-ons remain unresolved

Controller evidence remains first.

After the highest-ranked controller history has been checked, HomeBrain examines
the structured causal timeline. If material START transitions remain unresolved,
it may fetch exactly one highest-ranked same-room motion/presence history.

If controller evidence already explains the material starts, this extra read is
skipped.

There is no room-wide sensor fan-out.

Metrics:

- `causal_sensor_read`
- `causal_sensor_aligned`

### Signed transition correlation

The selected sensor history is correlated deterministically against subject
boundaries.

For a subject START:

- motion=`active` or presence=`present` must fall within ±2 seconds.

For a subject END:

- motion=`inactive` or equivalent absence may precede the subject off edge by
  up to 45 seconds, modelling a bounded delayed-off pattern.

Each correlation records:

- subject interval index;
- START/END role;
- subject timestamp;
- sensor timestamp;
- signed delta; and
- sensor attribute/value.

The signed delta convention is:

`sensor timestamp - subject boundary timestamp`

A positive START delta therefore means the controlled device changed before
Hubitat recorded the sensor active edge.

### Repeated pattern guidance

A single close sensor edge remains correlation.

When multiple subject START transitions repeatedly align with the same
motion/presence source, the host tells final reasoning that the repeated pattern is
materially stronger than a one-off environmental coincidence.

When two or more of those START correlations show the subject changing before
Hubitat records the sensor active edge, final reasoning may state that this ordering
argues against a Hubitat automation reacting to that recorded edge and may support
an upstream/outside-Hubitat trigger.

It must not name a specific external hub or automation unless topology/configuration
evidence independently supports that extra step.

### Deliberately excluded evidence

This change does not:

- query multiple environmental sensors;
- use illuminance/temperature-only devices as trigger candidates;
- promote timing alone to proof of a named automation;
- replace controller/button provenance when a START-aligned physical event already
  explains the transition; or
- add a new model round.

The sensor read is host-owned inside the existing causal evidence layer, before the
existing single provenance round.

## Regression coverage

0.13.7 adds tests for:

- same-room MotionSensor/PresenceSensor candidate selection;
- lux/temperature-only sensor exclusion;
- the motion sensor winning over the T1-style non-motion sensor shape;
- deterministic history arguments for the selected sensor;
- repeated START alignment with positive ~70 ms signed deltas;
- delayed END alignment after inactive edges;
- repeated-pattern upstream/outside-Hubitat guidance without naming a hub; and
- causal sensor metrics.

## Live acceptance target

For the same Bedroom 3 investigation:

- model rounds should remain around 4;
- one additional motion/presence history read is allowed only because material
  turn-ons remain unresolved;
- the selected device should be the capability-grounded motion/presence source,
  not the illuminance/temperature T1 sensor;
- repeated light-on / sensor-active and sensor-inactive / light-off timing should
  be surfaced with signed deltas;
- a repeated subject-before-sensor pattern may support "likely upstream/outside
  Hubitat" wording;
- a specific Aqara/Matter-side cause remains unproven unless configuration/topology
  evidence supports it; and
- the existing logs + relevant app/rule detail provenance round remains intact.
