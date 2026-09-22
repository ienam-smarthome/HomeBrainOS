# Hubitat MCP AI 0.16.13

## Prefer the corrected causal subject history after recovery

0.16.12 introduced deterministic START/END native-log correlation, but live
testing exposed a handoff bug between the 0.16.11 history recovery and the
0.16.12 causal timeline.

A causal subject can legitimately have two successful
`homebrain_device_history` receipts in the same request:

1. the first attribute-less mixed history page, which may infer `switch` but
   still establish zero bounded intervals;
2. the host-generated scoped retry for the same canonical device, which can
   recover the real switch interval.

The old causal timeline selected the first successful history receipt whenever
`observedIntervals` existed as a list. An empty list therefore qualified and
could shadow the corrected retry that followed.

For the live Dehumidifier 2 case this meant:

```
first receipt:
  attributeInferred = true
  observedIntervals = []

corrected retry:
  attribute = switch
  observedIntervals = [22:07:37 -> 22:38:13]
```

The causal timeline chose the first receipt, derived no boundary windows, and
0.16.12 never ran its native-log START/END collector. The request then fell back
to the older room/location/model provenance path and eventually asked for
generic logs using `since: 90m`.

## Selection rule

0.16.13 keeps the causal subject anchored to the first qualifying canonical
device history, but ranks later histories for that same subject by evidence
strength:

1. bounded observed interval;
2. open/unbounded active transition;
3. otherwise-valid empty temporal history.

Ties prefer the later receipt so a deterministic retry can supersede stale
first-pass evidence.

Histories belonging to a different device/controller are not allowed to replace
the anchored subject even if they also contain temporal intervals.

## Golden regression

The regression reproduces the exact live sequence:

```
receipt 1: Dehumidifier 2
  inferred switch
  intervalCount = 0

receipt 2: Dehumidifier 2
  explicit switch
  intervalCount = 1
  22:07:37.107+0100 -> 22:38:13.489+0100
```

The causal native-log layer must then derive:

```
START  2026-09-22T21:07:27.107Z .. 21:07:47.107Z
END    2026-09-22T21:38:03.489Z .. 21:38:23.489Z
```

A second regression verifies that a later controller history cannot steal the
subject role from Dehumidifier 2.

## Expected live behavior

After installing 0.16.13, the same causal request should retain the 0.16.11
inferred-state retry when needed, then immediately enter the 0.16.12 native-log
path.

Expected counters when the mirrored Ikea Rodret pattern is still present:

```
causal_inferred_attribute_retry: 1
causal_native_log_reads: 2
causal_native_log_correlations: 2
causal_repeated_controller_pattern: 1
investigative_finalization: 1
```

When repeated native-log provenance is sufficient, the weaker
`causal_room_plan`, `causal_location_read`, and
`causal_completion_retry` path should not be needed.
