# Hubitat MCP AI 0.16.10

## Causal provenance correctness

Live testing against the question:

```
Why did Dehumidifier 2 turn on?
```

exposed several correctness gaps that could cause HomeBrain to stop too early or
promote configuration context into a causal explanation.

This release fixes those gaps before further performance work.

## 1. Recover minor target misspellings from authoritative identity

A targeted Hubitat `labelFilter` lookup can return zero rows for a harmless
misspelling such as:

```
dehumidifer 2
```

even when the canonical device is uniquely present as `Dehumidifier 2`.

When the narrow lookup returns no plausible candidate, read-only device
resolution now falls back to the authoritative structural identity world and
runs the same conservative fuzzy resolver. Ambiguous names still fail closed.

## 2. Protect switch boundaries from noisy event streams

High-churn metering devices can emit enough power, energy, RTT, amperage and
power-factor events to push an older `switch=on` boundary outside the newest
50 generic events.

For `attribute=switch`, HomeBrain now asks `hub_list_device_events` for the
switch attribute upstream first. This keeps the actual on/off state boundaries
visible to temporal analysis.

Because some driver-specific upstream attribute filters have previously returned
false empty results, a zero-row scoped switch result automatically retries once
with the established unfiltered/local-filter fallback.

Other history attributes retain the existing conservative local-filter path.

## 3. Host-owned causal log timezone conversion

Observed Hubitat device timestamps carry the location offset. Native
`hub_get_logs` accepts timezone-aware ISO timestamps, while timezone-free values
are interpreted as UTC.

HomeBrain now derives bounded native-log windows directly from the observed
causal boundary and converts them explicitly to UTC.

Example:

```
subject start: 2026-09-22T22:07:37.107+0100
```

becomes:

```
since: 2026-09-22T21:07:27.107Z
until: 2026-09-22T21:07:47.107Z
```

The host overwrites model-authored `since`/`until` values for the bounded
causal log read, preventing an accidental one-hour DST/offset shift.

## 4. Preserve bounded native-log evidence

Successful `hub_get_logs` results now retain a bounded, redacted set of native
log rows in the technical evidence receipt and final current-turn evidence
ledger. This keeps concrete timestamp/source/message rows visible during final
synthesis instead of reducing the read to only `object fields: logs, count...`.

## 5. App configuration is not execution proof

The causal prompt, evidence ledger and deterministic synthesis validator now
share the same rule:

- app/rule configuration proves association, capability or downstream behavior;
- configuration alone does not establish that the app initiated one observed
  transition;
- aligned controller provenance or direct execution/log evidence outranks
  configuration context.

A draft that calls an app the "most likely cause" while also admitting that no
direct provenance established the trigger is automatically sent through the
causal repair path.

## 6. Block expensive broad-inventory causal detours

An unscoped `hub_list_devices` call through either the read or manage gateway is
not causal provenance and can take tens of seconds on a large hub.

During a causal investigation HomeBrain now blocks that detour. Named subject
resolution uses the targeted/local identity path; genuinely new device discovery
must use a scoped `labelFilter`, `roomFilter` or equivalent.

## Golden regression

The Dehumidifier 2 regression fixture verifies that:

- `dehumidifer 2` can still resolve uniquely to `Dehumidifier 2`;
- the 22:07:37 +01:00 switch-on boundary is not lost behind later metering
  telemetry;
- the corresponding native-log window is 21:07:27Z..21:07:47Z, not 22:00Z;
- configuration-only causal attribution is rejected;
- an aligned physical controller event outranks app configuration.
