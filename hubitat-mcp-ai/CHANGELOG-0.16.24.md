# Hubitat MCP AI 0.16.24

## Authoritative switch-boundary provenance

0.16.23 generalized the direct causal fast path across ordinary switch-capable
devices. Live tests then exposed two real integration patterns that do not fit a
strict command-before-state model:

1. a bridge-backed light with no `command-on` event at all, but a structured
   physical switch boundary produced by the Hue bridge;
2. a Tuya-local fan where the switch state was timestamped 13 ms before the
   matching command row even though both independently named the same app
   producer.

0.16.24 handles those cases without weakening the evidence model.

## Corroborated tiny timestamp inversions

The existing command-event correlation remains directional by default: a later
command cannot explain an earlier state transition.

A very small negative command-to-state delta is now eligible only when all of
the following are true:

- the command is within 250 ms after the state boundary;
- the command producer is an app;
- the switch boundary itself independently carries structured `producedBy`;
- the boundary producer is the same app as the command producer.

That means timing alone still cannot rescue a later command.

For the observed Fan Switch case:

```text
21:59:59.735 switch=on
  producedBy: 01. Humidity Controller

21:59:59.748 command-on
  producedBy: 01. Humidity Controller
```

HomeBrain can now treat the 13 ms inversion as recording order rather than a
different later action, because the state boundary independently corroborates
the same producer.

## Boundary-event provenance

HomeBrain now reads structured producer metadata directly from requested switch
boundaries.

When a non-self producer is present and no stronger direct command correlation
is available, the deterministic finalizer can answer from that boundary
evidence without escalating through multiple native-log/model rounds.

Producer semantics are deliberately separated:

- app producer: direct state-event provenance identifying the app recorded as
  producer of the boundary;
- device/bridge producer: reporting-source provenance only, not the exact
  initiating action.

Self-produced MQTT/device state events remain insufficient on their own and keep
the established deeper fallback path.

## Bridge reporting-source wording

The Bedroom 1 Light live test had:

```text
command-on events: 0

switch=on
type: physical
producedBy: Matter Hue Bridge Pro
triggered:
  Bedroom 1 (Lights Off)
  SenseCap D1 Settings
```

The prior fallback took about 39.7 seconds, 6 model rounds and 11 tool calls and
described the bridge too strongly as the cause.

0.16.24 instead produces a deterministic bounded conclusion:

- no command-on producer was recorded;
- the physical ON state event was reported/produced through Matter Hue Bridge
  Pro;
- this identifies the reporting path into Hubitat;
- it does not identify whether the initiating action was a Hue button, Hue app,
  Hue-native automation, or another bridge-side action;
- Hubitat apps listed under `triggered` are downstream listeners, not evidence
  that they initiated the state change.

## Human-readable long durations

The causal duration formatter no longer emits long values such as:

```text
approximately 1273 minutes
```

for multi-hour intervals.

Long intervals now remain human-readable, for example:

```text
approximately 21 hours 13 minutes
approximately 2 hours 24 minutes
```

Exact minute-aligned intervals keep exact wording.

## Expected live behavior

Bedroom2 (MQTT):

```text
tool_calls: 3
causal_command_producer_reads: 1
model_rounds: 0
causal_native_log_reads: 0
```

Fan Switch with corroborated 13 ms inversion:

```text
tool_calls: 3
causal_command_producer_reads: 1
causal_command_producer_provenance: 1
model_rounds: 0
causal_native_log_reads: 0
```

Bedroom 1 Light bridge/reporting-source case:

```text
tool_calls: 3
causal_command_producer_reads: 1
causal_boundary_producer_provenance: 1
model_rounds: 0
causal_native_log_reads: 0
```

## Regression coverage

0.16.24 adds tests for:

- the live Fan Switch 13 ms state-before-command ordering;
- matching app boundary producer required before accepting that inversion;
- mismatched later commands remaining rejected;
- bridge/device boundary provenance rendered as reporting source, not initiator;
- downstream `triggered` apps described as reactions rather than causes;
- self-produced switch boundaries remaining insufficient by themselves;
- zero provider/model rounds for sufficient boundary provenance;
- zero native-log reads for sufficient boundary provenance;
- long causal durations rendered in hours/minutes.
