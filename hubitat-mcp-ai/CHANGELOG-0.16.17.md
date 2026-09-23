# Hubitat MCP AI 0.16.17

## Authoritative command-producer causal provenance

0.16.16 correctly handled live/open causal starts, but a later same-day rerun
exposed a more durable Hubitat evidence source than native logs.

The Dehumidifier 2 state history still showed the morning interval:

```
06:57:23.391  switch=on
08:27:23.601  switch=off
```

while both historical `hub_get_logs` boundary queries returned zero rows.

Hubitat's device Events history, however, still retained the command records and
their **Produced By** metadata:

```
06:57:23.292  command-on
Produced By: Ikea Rodret (Livingroom): button 2 pushed

08:27:23.518  command-off
Produced By: 01. Humidity Controller
```

That metadata is stronger than timestamp-only log correlation because it records
which Hubitat app/action issued the device command.

0.16.17 makes command-event producer metadata the first causal provenance layer
for explicit switch transition questions.

## Preserve command-event provenance

DeviceHistoryService now preserves bounded metadata from Hubitat event rows:

- `type`;
- `source`;
- `triggered`;
- `physical`;
- `digital`;
- `deviceId`;
- `installedAppId`;
- `producedBy`.

Hubitat commonly supplies `producedBy` as an HTML anchor. HomeBrain strips the
markup and retains only a normalized structure:

```json
{
  "label": "Ikea Rodret (Livingroom): button 2 pushed",
  "id": "3700",
  "type": "app"
}
```

Raw HTML is not copied into evidence.

## Scoped command reads

For host-prefetched switch-causal history, HomeBrain now requests exact command
event names in addition to the switch rows:

```
attribute=command-on
attribute=command-off
```

These reads run concurrently and avoid a noisy generic event page where power,
energy and RTT updates could crowd older command rows out of the newest result
set.

For a currently-open ON interval, only `command-on` is needed.

A zero-row command filter is not replaced by an expensive generic sweep.
Existing native-log provenance remains the fallback.

## Direct boundary correlation

`causal_command_provenance.py` joins an authoritative command row to the
adjacent observed switch boundary.

For the golden morning interval:

```
06:57:23.292 command-on
  producedBy = Ikea Rodret (Livingroom): button 2 pushed
        ↓ 99 ms
06:57:23.391 switch=on

08:27:23.518 command-off
  producedBy = 01. Humidity Controller
        ↓ 83 ms
08:27:23.601 switch=off
```

A produced `command-on` adjacent to the observed ON boundary is sufficient
direct provenance for the user's turn-on question.

The OFF command producer is retained as complementary evidence explaining how
the run ended, but is not used as the cause of the earlier turn-on.

## Causal evidence priority

The effective causal hierarchy is now:

1. Hubitat command event with explicit `producedBy`;
2. native-log physical controller -> command timing;
3. controller event-history timing;
4. rule/app execution evidence;
5. configuration/navigation context.

This keeps direct command-source metadata above inference from timing.

## Deterministic answer

When command producer provenance is sufficient and deterministic finalization is
enabled, HomeBrain can answer without:

- historical `hub_get_logs` calls;
- room/controller fan-out;
- provider/model synthesis.

The answer states that Hubitat records the ON command as produced by the named
action, reports command-to-state timing, includes the OFF command producer when
available, and preserves the caveat that **Produced By identifies the Hubitat
app/action issuing the command, not the person who initiated that action**.

## Fallback

If command producer metadata is unavailable, incomplete, or the upstream command
filter returns no rows, HomeBrain continues into the established 0.16.16
native-log path unchanged.

The existing rollback controls continue to apply:

```yaml
causal_deterministic_final_enabled: false
causal_subject_prefetch_enabled: false
```

## Observability

Adds:

- `causal_command_producer_reads`
- `causal_command_producer_provenance`

For the closed Dehumidifier 2 morning run, the target metrics are:

```
causal_subject_prefetch: 1
causal_command_producer_reads: 2
causal_command_producer_provenance: 1
causal_deterministic_finalization: 1
investigative_finalization: 1

causal_native_log_reads: absent / 0
model_rounds: absent / 0
provider timing: absent
```

## Regression coverage

The 0.16.17 tests verify:

- Hubitat `producedBy` HTML is sanitized and structurally parsed;
- scoped `command-on` and `command-off` rows are collected alongside switch
  history;
- the command producer survives technical evidence reduction;
- the ON producer aligns 99 ms before the ON state boundary;
- the OFF producer aligns 83 ms before the OFF state boundary;
- the deterministic renderer distinguishes the turn-on source from the later
  Humidity Controller turn-off source;
- the end-to-end agent path performs no native-log read and no provider call
  when direct command provenance is present.
