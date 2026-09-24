# Hubitat MCP AI 0.16.26

## Better bounded candidate selection for reporting-source investigations

0.16.25 added deterministic secondary correlation for bridge/device reporting-source
cases. A live Bedroom 1 Light test showed that the correlation engine worked, but
the bounded candidate selection could still choose the wrong devices:

- a label-affinity controller outside the actual room was later described as
  "same-room";
- a derived Bedroom 1 Soft Sensor could outrank the more relevant occupancy
  source;
- only one controller and one occupancy source were checked;
- HomeBrain did not yet use the light's own detailed event stream to classify
  the repeated level-recovery pattern visible after external ON transitions.

0.16.26 fixes those selection and presentation problems without changing the
direct command/app-provenance fast paths.

## Two bounded controllers and two bounded occupancy sources

For external bridge/device reporting-source cases only, HomeBrain now reads at
most:

- two ranked controller candidates;
- two ranked motion/presence candidates;
- one bounded unfiltered subject-event page.

All secondary histories remain bounded and run through the existing MCP
concurrency limit. Direct command-producer and app-producer cases still finalize
before this work starts.

## Controller ranking

Controller candidates remain capability-grounded: a candidate must advertise a
button capability.

Ranking now uses:

1. exact Hubitat room assignment;
2. label affinity with the subject room;
3. within the same basis, lighting-oriented controller semantics such as
   dimmer/remote/switch ahead of a generic button;
4. stable label ordering.

This does not infer causation from labels. It only determines which bounded
controller histories are worth checking first.

## Truthful room wording

A label-affinity controller outside the subject room is no longer described as
"same-room".

For example, a device labelled `Bedroom 1 button` but assigned to Hubitat room
`Button Controllers` is rendered as a room-associated candidate with its actual
room stated explicitly.

"Same-room" is used only when the returned history's actual room equals the
subject room.

## Occupancy ranking

Motion/presence candidates remain capability-grounded.

Within the same room/affinity basis:

1. `PresenceSensor` outranks a motion-only device;
2. a physical-looking source outranks a derived/virtual/soft sensor only as a
   final tiebreak;
3. no FP300-specific name rule is used.

If a device exposes both PresenceSensor and MotionSensor, HomeBrain requests
`presence` history.

This prevents a derived Soft Sensor from monopolizing the bounded investigation
when a stronger physical occupancy source is available.

## Downstream level-recovery evidence

Reporting-source cases now perform one bounded unfiltered subject-event read.

For level-capable lighting integrations this lets deterministic analysis detect
patterns such as:

```text
physical ON from bridge
+ ~20 ms -> level 100 from bridge
+ ~3 s   -> command-setLevel(45) from a Hubitat app
```

When repeated across several ON transitions, HomeBrain can state that the
`setLevel` command is a downstream recovery/adjustment after the light was
already ON.

The app command is never promoted to the initiating ON cause merely because it
follows the transition.

## Bedroom 1 morning regression

0.16.26 adds a regression based on the observed morning pattern:

- five physical Hue-bridge ON transitions;
- each followed immediately by level 100;
- each followed by `Bedroom 1 (⚪ Lights Off)` issuing `setLevel(45)`;
- no matching FP300 active edge around those ON transitions;
- an FP300 inactive edge shortly before the final OFF;
- two bounded controller candidates whose Hubitat room is `Button Controllers`;
- a physical presence source and a Soft Sensor both available.

The required deterministic result:

- identifies Matter Hue Bridge Pro as reporting path, not initiator proof;
- checks both controller candidates;
- checks both occupancy candidates;
- does not call out-of-room controllers "same-room";
- reports that the checked FP300 does not explain the morning ON transitions;
- can surface the OFF-side inactive correlation without turning it into ON
  causation;
- identifies the repeated post-ON level-recovery action as downstream;
- remains zero-model and zero-native-log.

## Metrics

Adds:

```text
causal_subject_pattern_read
causal_level_recovery_pattern
```

Existing metrics now count each bounded secondary history actually read:

```text
causal_provenance_read
causal_sensor_read
```

## Regression coverage

0.16.26 adds tests for:

- dimmer before generic button within label-affinity controller ranking;
- PresenceSensor before MotionSensor;
- Soft Sensor losing the final tiebreak to a physical occupancy source;
- at most two controller candidates;
- at most two occupancy candidates;
- actual-room wording for label-affinity controllers;
- five repeated ON -> level 100 -> app setLevel recovery sequences;
- downstream recovery explicitly not presented as the ON cause;
- FP300 no-match on the morning ON transitions;
- bounded FP300 inactive-before-OFF evidence;
- zero provider/model rounds;
- zero native-log reads.
