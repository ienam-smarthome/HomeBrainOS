# Hubitat MCP AI 0.16.25

## Bounded secondary correlation for bridge-reported switch events

0.16.24 made external bridge/device switch-boundary provenance fast and safe.
The Bedroom 1 Light live test then showed a useful next layer: HomeBrain could
correctly say that Matter Hue Bridge Pro was the reporting path, but it stopped
before checking nearby controllers and occupancy sensors that might corroborate
a broader pattern.

0.16.25 adds that secondary investigation without weakening the evidence model
or reintroducing a provider/model round.

## Activation is deliberately narrow

Secondary correlation runs only when all of the following are true:

- the user asked an explicit ON/OFF causal question;
- no sufficient direct command producer already finalized the answer;
- the requested switch boundary has structured non-self `producedBy`;
- that producer is a device/bridge rather than an app.

Direct command provenance and app-produced boundaries keep the existing fast
stop and do not pay for room/sensor correlation.

## More subject transitions without another subject read

Explicit causal subject history now keeps up to 12 recent switch transitions
instead of 3.

The underlying bounded Hubitat history read was already fetching a larger
source batch, so this exposes more of the existing current-turn history to the
deterministic correlator rather than adding a second subject-history query.

This allows repeated-pattern analysis across several recent intervals.

## Bounded same-room evidence

For an external bridge/device reporting-source case, HomeBrain performs:

1. one exact-room filter;
2. at most one ranked button/controller history;
3. at most one ranked PresenceSensor/MotionSensor history.

Controller and sensor histories run concurrently.

The room filter remains capability-grounded. Candidate labels alone never create
a capability claim.

## Presence-first sensor ranking

Within the same room, a device advertising `PresenceSensor` now ranks ahead
of a device advertising only `MotionSensor`.

This is capability-based rather than FP300-specific. It is useful for occupancy
lighting because persistent mmWave/presence sources often provide the more
relevant state transition.

Room match still outranks label affinity, and label semantics remain only a
stable tiebreaker after capability + room matching.

## Deterministic correlation windows

Controller events:

```text
±2 seconds around switch interval boundaries
```

Presence/motion events:

```text
ON/start: ±5 seconds
OFF/end: sensor inactive/not-present up to 5 seconds before the boundary
```

The signed timing is preserved in the synthesized evidence.

## Evidence semantics

Secondary correlation is never promoted to direct causal proof.

The deterministic answer separates:

- direct command producer, when present;
- switch boundary reporting source;
- downstream Hubitat listeners;
- controller timing correlation;
- motion/presence timing correlation;
- bounded external-automation hypothesis.

If repeated ON boundaries align with one presence/motion source, and multiple
light transitions occur before Hubitat records the sensor active edge, HomeBrain
may say that a shared upstream/outside-Hubitat automation involving that sensor
is a **plausible hypothesis**.

It must also state that:

- the timing does not prove the sensor directly caused the light;
- the timing does not identify a specific external platform;
- controller non-alignment only weighs against that controller for the checked
  transitions; it does not prove it was never involved.

## Bedroom 1 target behavior

For the observed Bedroom 1 topology, the intended answer shape becomes:

```text
- no Hubitat command-on producer was recorded;
- Matter Hue Bridge Pro is the reporting path into Hubitat, not proof of the
  initiating action;
- Bedroom 1 (Lights Off) and SenseCap D1 Settings are downstream reactions;
- compare recent Bedroom 1 dimmer events with the recent light boundaries;
- compare the highest-ranked same-room presence source with several recent ON/OFF
  boundaries;
- if repeated signed timing exists, describe it as corroborating correlation
  and a plausible external-automation hypothesis, not as direct cause.
```

## Metrics

0.16.25 adds:

```text
causal_secondary_correlation
causal_secondary_room_read
causal_secondary_controller_read
causal_secondary_sensor_read
causal_secondary_repeated_sensor_pattern
```

Direct command-provenance cases should not emit these counters.

## Regression coverage

0.16.25 adds tests for:

- PresenceSensor ranking ahead of MotionSensor in the same room;
- one subject switch-history read retained while exposing 12 recent transitions;
- a Bedroom 1 Hue-bridge reporting-source scenario;
- one bounded controller history;
- one bounded presence history;
- repeated sensor START correlation;
- signed 4.4 s / 1.2 s post-light sensor edges;
- an ~80 ms sensor-inactive edge before an OFF boundary;
- zero provider/model rounds when bounded bridge correlation is sufficient;
- zero native-log reads for the bounded bridge path;
- wording that calls the external-automation interpretation a plausible
  hypothesis rather than proof.
