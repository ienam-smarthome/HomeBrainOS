# Hubitat MCP AI 0.16.25

## Bounded secondary correlation for external reporting sources

0.16.24 made bridge/device switch-boundary provenance fast and safe: when no
direct command producer exists, HomeBrain can identify the reporting path
without claiming that the bridge/device itself was the initiating cause.

The remaining gap was diagnostic depth. A live Bedroom 1 Light comparison showed
that useful repeated timing relationships existed in same-room controller and
FP300 history, but 0.16.24 intentionally stopped as soon as the reporting source
was established.

0.16.25 adds a bounded deterministic follow-up only for that reporting-source
case.

## Trigger condition

The secondary pass runs only when all of the following are true:

- the user asked an explicit ON/OFF causal question;
- direct command-producer correlation is not sufficient;
- the requested switch boundary has a non-self structured producer;
- that producer is a device/bridge reporting source rather than an app.

Direct command-producer cases and app-produced state boundaries keep the existing
immediate fast path.

## No extra subject-history read

The primary causal subject read already asks Hubitat for up to 50 scoped switch
rows. 0.16.25 retains a bounded 16-row correlation view from that same fetched
page under a host-private hint.

This means repeated-transition analysis does not pay for a second subject
history request and does not enlarge the public/model tool schema.

## Bounded room investigation

For an external reporting-source case HomeBrain performs:

1. one exact-room structural discovery;
2. at most one highest-ranked button/controller history;
3. at most one highest-ranked MotionSensor/PresenceSensor history.

The controller and sensor histories run concurrently. No illuminance,
temperature, humidity, location, native-log or broad device fan-out is added by
this path.

## Deterministic correlation rules

Controller events are matched to the nearest observed switch boundary within the
existing two-second controller window.

Motion/presence START correlations use a five-second bounded window so repeated
patterns such as:

```text
light ON
1.2 s later -> FP300 active

light ON
4.4 s later -> FP300 active
```

can be surfaced without turning timing into causation.

OFF correlations retain the existing bounded inactive-before-end logic.

The analysis also records whether the specific requested transition has a
matching controller or sensor edge. A repeated pattern across earlier
transitions is therefore not silently applied to a latest transition that does
not fit it.

## Evidence-language contract

The deterministic answer separates:

- direct evidence: no command producer, physical/reporting source, downstream
  triggered listeners;
- controller timing: which ON or OFF boundaries the checked controller aligns
  with;
- sensor timing: how many observed transitions align and their signed deltas;
- repeated pattern: whether multiple ON transitions occurred before Hubitat
  recorded the sensor active edge;
- unresolved hypothesis: an upstream/outside-Hubitat relationship may be
  consistent with the timing, but the evidence does not prove the sensor caused
  the device change and does not identify a specific external hub or automation.

This deliberately avoids wording such as "the FP300 directly caused the light".

## Bedroom 1 live-shape regression

The regression models the observed pattern:

- latest requested ON at 22:11:04 has no nearby FP300 active edge;
- earlier ON at 21:18:26 is followed by FP300 active 4.4 seconds later;
- earlier ON at 20:58:17 is followed by FP300 active 1.2 seconds later;
- an FP300 inactive edge occurs 80 ms before an observed OFF boundary;
- the checked Bedroom 1 dimmer aligns with OFF boundaries but not those ON
  transitions.

Expected synthesis therefore says the repeated ordering is compatible with an
upstream/outside-Hubitat relationship involving the FP300, while explicitly
noting that the latest requested ON does not fit that sensor-edge pattern and
that no specific Aqara/Hue automation is proven.

## Performance contract

The reporting-source path remains zero-model and zero-native-log when the
bounded deterministic evidence is available.

It adds one room-filter tool plus at most two local history tools. The two
controller/sensor history reads are concurrent and the global MCP concurrency
limit remains unchanged.

## Metrics

Adds:

```text
causal_reporting_source_correlation
```

and reuses:

```text
causal_room_plan
causal_provenance_read
causal_provenance_aligned
causal_sensor_read
causal_sensor_aligned
```

so live tests can distinguish direct provenance from bounded secondary
correlation work.

## Regression coverage

0.16.25 adds tests for:

- preserving multiple subject switch transitions from the already-fetched source
  page;
- repeated controller/sensor correlation against those transitions;
- OFF-only controller alignment not being cited as ON provenance;
- two FP300 active edges occurring after earlier ON transitions;
- an FP300 inactive edge shortly before an OFF transition;
- the latest requested ON explicitly not matching the repeated FP300 pattern;
- repeated positive sensor timing rendered as an upstream-compatible hypothesis,
  not proof;
- no specific external hub or automation being named from timing alone;
- zero provider/model rounds;
- zero native-log reads;
- one bounded reporting-source correlation pass.
