# Hubitat MCP AI 0.16.15

## Zero-model finalization for strong repeated native provenance

0.16.14 successfully reduced the validated Dehumidifier 2 causal path to one
provider/model round, but live timing remained about 10.6 seconds because the
single final synthesis still cost roughly 5.7 seconds and the causal prefetch
repeated a targeted device-identity lookup that had already been satisfied by
the authoritative identity cache.

0.16.15 removes both costs for one deliberately narrow, already-validated
evidence shape.

## Reuse the already-grounded causal subject identity

The 0.16.14 prefetch already calls `get_device_identities()` to establish one
unique known switch device before any model round. DeviceHistoryService
previously resolved that same canonical label again through
`hub_list_devices(labelFilter=...)`.

The host prefetch now carries the matched structural identity into
DeviceHistoryService through a private execution-only field. The history
service still validates the requested history attribute against that identity,
then reads authoritative device events by stable Hubitat device ID.

The private identity hint is not exposed in the public/model tool schema and is
removed from technical evidence receipts.

If a normal model-selected history call does not have a trusted host identity,
DeviceHistoryService uses the existing targeted resolver exactly as before.

## Deterministic final answer only for the strongest evidence contract

A provider is no longer required merely to paraphrase an already-deterministic
causal result when all of the following have already been established:

- one material subject interval;
- an ON command adjacent to the interval start;
- an OFF command adjacent to the interval end;
- one physical controller/input immediately before the ON command;
- the same controller/input fingerprint immediately before the OFF command;
- the existing native-log sufficiency check passes.

Only that repeated START/END provenance shape is eligible.

The deterministic renderer reports:

- the strongest initiating-control candidate;
- physical controller/input label and button number;
- controller-to-command timing;
- subject ON/OFF command timing;
- downstream app handling that occurs after the ON command;
- approximate observed run duration;
- the existing caveat that repeated timing does not independently prove the
  configured button-to-device mapping or identify the person who pressed it.

If evidence is partial, contradictory, missing one boundary, or otherwise fails
the existing native-log sufficiency test, HomeBrain falls back to the 0.16.14
provider-authored final synthesis.

## Rollback

Set:

```yaml
causal_deterministic_final_enabled: false
```

to retain 0.16.14 causal subject prefetch and native-log correlation while
restoring one provider/model round for the final wording.

The separate 0.16.14 prefetch rollback remains:

```yaml
causal_subject_prefetch_enabled: false
```

## Observability

Adds:

- `causal_deterministic_finalization`

For the validated Dehumidifier 2 case, the intended strong-evidence metrics are:

```
causal_subject_prefetch: 1
causal_native_log_reads: 2
causal_native_log_correlations: 2
causal_repeated_controller_pattern: 1
causal_deterministic_finalization: 1
investigative_finalization: 1
model_rounds: absent / 0
```

The provider timing should be absent because no provider call is required.

## Golden regression

The end-to-end regression now verifies that:

- `dehumidifer 2` uniquely grounds to the cached `Dehumidifier 2` identity;
- no redundant `hub_list_devices` identity lookup occurs;
- one authoritative switch-history read recovers the 31-minute interval;
- two native-log reads establish the repeated Ikea Rodret button-2 pattern;
- no provider request is made;
- the deterministic answer preserves downstream Humidity Controller handling
  and the mapping/person caveats;
- evidence receipts do not leak the private resolved-target hint.

A separate regression keeps the 0.16.14 one-model-round behavior active when
`causal_deterministic_final_enabled: false`.
