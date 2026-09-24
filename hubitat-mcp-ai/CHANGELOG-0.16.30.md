# Hubitat MCP AI 0.16.30

## Preserve causal intent across device clarification

A live 0.16.29 Hallway investigation exposed two related problems after the new
room-kind resolver correctly returned:

```text
Hallway Light 1
Hallway Light 2
```

Selecting `Hallway Light 1` did not continue the original causal question.
Instead, the selected label was treated as a new generic request. The result fell
back to model-led investigation, native logs, app navigation, and configuration
reads.

Observed live shape:

```text
model_rounds: 3
causal_native_log_reads: 1
tool_calls: 14-17
total: ~24-25 s
```

The same current-turn event evidence could then be synthesized inconsistently:
one answer correctly described the latest ON as a physical/external transition
reported through Matter Hue Bridge Pro, while another incorrectly upgraded the
Hallway app from a triggered listener to the direct initiating automation.

0.16.30 fixes both issues.

## Causal clarification continuation

When a causal switch-transition request produces device choices, HomeBrain now
stores the original causal objective with that clarification.

Example:

```text
Why did hallway lights turn on?
-> Hallway Light 1 / Hallway Light 2
```

Selecting:

```text
Hallway Light 1
```

now resumes an equivalent concrete causal objective:

```text
Why did Hallway Light 1 turn itself on?
```

This re-enters the existing deterministic causal-subject / command-producer /
boundary-producer pipeline instead of treating the choice label as a standalone
history request.

A new metric records this path:

```text
causal_clarification_resume
```

For a bridge/device boundary with sufficient evidence, the resumed request is
expected to remain zero-model and zero-native-log.

## Hard triggered-listener attribution guard

Hubitat device-event metadata separates:

- `producedBy`: structured producer/reporting-source provenance;
- `triggered[]`: listeners invoked by the state event.

For a physical state event such as:

```text
type: physical
producedBy: Matter Hue Bridge Pro
triggered:
  - Hallway (💡 1/2 On)
  - SenseCap D1 Settings
```

an app appearing only in `triggered[]` is downstream evidence. It is not direct
proof that the app initiated the transition.

0.16.30 adds a deterministic synthesis validator that prevents a triggered-only
app from being described as:

- the direct trigger;
- the cause;
- responsible for the transition;
- the producer of the state event.

The localized correction states that the app is a downstream listener and that
the physical event itself was produced by the bridge/device.

## Independent app provenance remains valid

The guard does not block a genuine app attribution when separate current-turn
evidence independently records that app as a direct producer, for example:

```text
command-on
producedBy:
  type: app
  id: 4012
  label: Hallway (💡 1/2 On)
```

Direct command or app-produced boundary provenance continues to outrank
triggered-listener semantics.

## Synthesis instruction

The final causal synthesis contract now explicitly states that `triggered[]`
contains listeners invoked by the state event. When a physical event is
`producedBy` a bridge/device, an app present only in `triggered[]` must be
described as downstream.

This reduces the chance of a repair round being needed, while the deterministic
validator remains the hard correctness backstop.

## Regression coverage

0.16.30 adds tests proving that:

- a causal clarification stores the original objective;
- choosing `Hallway Light 1` resumes the original ON investigation;
- the resumed request reaches causal subject prefetch;
- boundary producer provenance is used;
- deterministic causal finalization occurs;
- model rounds remain zero on the sufficient bridge-provenance path;
- native-log reads remain zero;
- Matter Hue Bridge Pro is kept as reporting path;
- `Hallway (💡 1/2 On)` remains downstream;
- a bad model draft claiming the triggered-only app directly caused the ON is
  deterministically rejected;
- a separately proven direct app command producer is not blocked by the guard.

## Scope

0.16.29 room-kind resolution is unchanged. 0.16.30 does not add multi-device
history merging; it only makes a selected clarification continue the original
causal objective correctly and prevents downstream listener metadata from being
promoted into direct causation.
