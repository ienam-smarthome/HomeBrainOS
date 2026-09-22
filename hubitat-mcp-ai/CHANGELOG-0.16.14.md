# Hubitat MCP AI 0.16.14

## One-round final reasoning for explicit switch-causal questions

0.16.13 live validation established the intended causal path:

- deterministic subject history;
- two host-derived native-log boundary reads;
- repeated physical controller/input correlation;
- one grounded final answer.

The remaining latency was mostly provider time because the request still spent an
initial model round choosing `homebrain_device_history`, then a second provider
round synthesizing the already-deterministic evidence.

For the validated Dehumidifier 2 run:

```
model_rounds: 2
provider: 6.0 s
total: 10.6 s
```

0.16.14 removes that first provider/tool-selection round for one deliberately
narrow class of causal request.

## Identity-grounded subject prefetch

Before the first provider call, HomeBrain may prefetch causal subject history
when all of these conditions are true:

1. the request is classified as causal;
2. the wording explicitly names exactly one authoritative device identity;
3. the wording explicitly describes an ON/OFF switch transition;
4. the resolved device actually advertises switch capability/state or on/off
   commands;
5. the identity match is unique and above conservative fuzzy thresholds.

The matcher supports minor spelling errors in an otherwise unique canonical
device name. A numeric mismatch such as asking about "Dehumidifier 3" when only
1 and 2 exist is rejected rather than guessed.

Generic device-kind labels such as "switch" or "light" are not sufficient
single-token identities.

Broader causal questions such as:

```
Why is Dehumidifier 2 using so much power?
Why is the room humid?
```

remain on the established model-routed path.

## Same evidence pipeline, earlier

The optimization does not create a second causal implementation.

The host-generated prefetch calls the same:

- `homebrain_device_history`;
- DeviceHistoryService resolver and temporal analysis;
- 0.16.11 inferred-state recovery where needed;
- 0.16.13 causal subject selection;
- 0.16.12 dual native-log START/END correlation;
- FinalAnswerCoordinator and synthesis validators.

For an explicit switch transition, the prefetch requests:

```json
{
  "name": "<canonical device label>",
  "attribute": "switch",
  "limit": 3
}
```

DeviceHistoryService already defines that small explicit state-history query as
a bounded seven-day latest-transition search while internally fetching enough
switch rows for interval analysis.

## One provider round when native provenance is sufficient

If subject history yields a material interval and repeated START/END native-log
provenance is sufficient, HomeBrain skips the general provider tool-selection
loop and goes directly to the existing no-tools final synthesis.

Expected live metrics for the Dehumidifier 2 golden case:

```
model_rounds: 1
causal_subject_prefetch: 1
causal_native_log_reads: 2
causal_native_log_correlations: 2
causal_repeated_controller_pattern: 1
investigative_finalization: 1
```

The weaker room/location/completion path should remain absent.

If the prefetch establishes no subject interval, HomeBrain also keeps the
existing fail-closed behavior and finalizes without inventing a cause.

If identity matching is ambiguous, unsupported, unavailable, or the native-log
correlation is insufficient, the ordinary 0.16.13 model-driven investigation
remains available.

## Rollback

Set:

```yaml
causal_subject_prefetch_enabled: false
```

to restore the previous model-selected subject-history path without reverting
the release.

## Observability

Adds:

- `causal_subject_prefetch`

This counter proves that HomeBrain selected the causal subject deterministically
before the first provider round.
