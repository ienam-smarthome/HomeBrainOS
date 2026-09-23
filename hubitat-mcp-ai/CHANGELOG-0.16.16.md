# Hubitat MCP AI 0.16.16

## Deterministic open-start causal provenance

0.16.15 live testing exposed a distinct causal shape from the previously
validated closed interval: Dehumidifier 2 had turned on at 06:57:23 and was
still on when the question was asked.

The subject history correctly reported:

```
openActiveInterval: true
openActiveStart: 2026-09-23T06:57:23.391+0100
```

and native logs established:

```
06:57:23.196  Ikea Rodret button 2 pushed [physical]
06:57:23.275  Dehumidifier 2 turn on command
06:57:23.391  Dehumidifier 2 switch=on
06:57:23.438  Humidity Controller manual-run reaction
```

However, the 0.16.15 deterministic finalizer intentionally required the same
physical controller/input at both START and END. A still-open interval has no
OFF boundary yet, so that repeated-boundary contract could never pass.

The request therefore fell back to provider reasoning, performed three model
rounds, and later misclassified a controller-history read as a new causal
subject, producing a misleading `causal_subject_empty_stop`.

0.16.16 fixes both issues.

## Open START provenance is sufficient for a turn-on question

A currently-open switch interval may now satisfy the strong native-log causal
contract when all of the following are present on its observed START boundary:

- the timeline row is explicitly OPEN;
- the matching subject action is ON;
- an authoritative native-log ON command is adjacent to the observed switch=on
  boundary;
- a physical controller/input event is immediately adjacent to and precedes the
  ON command under the existing native-log correlation bounds.

This applies only to an OPEN interval. Closed intervals retain the stronger
0.16.15 requirement that the same controller/input be corroborated at both the
START and END commands.

## Open-interval deterministic answer

When the open-start contract passes, the zero-model finalizer reports:

- the strongest initiating-control candidate;
- controller/button identity;
- controller -> ON-command timing;
- downstream app handling after the ON command, when present;
- that the current ON interval remains open;
- that no OFF transition, end-boundary corroboration, or completed duration has
  been observed yet;
- the existing caveat that timing does not independently prove the configured
  mapping or identify the person who pressed the control.

The finalizer never invents a duration for an open interval.

## Persist the prefetched causal subject

Causal prefetch now returns its canonical subject key to the orchestrator.

If stronger evidence is not sufficient and HomeBrain falls back to model-guided
investigation, that prefetched subject remains the anchored investigative
subject. A later controller/button history is supporting evidence only; it
cannot become the subject and cannot trigger `causal_subject_empty_stop`.

This directly prevents the 0.16.15 live failure where
`Ikea Rodret (Livingroom)` history was mistaken for the causal subject after
Dehumidifier 2 had already been established.

## Observability

Adds:

- `causal_open_start_provenance`

Expected metrics for the live open Dehumidifier case are:

```
causal_subject_prefetch: 1
causal_native_log_reads: 1
causal_native_log_correlations: 1
causal_open_start_provenance: 1
causal_deterministic_finalization: 1
investigative_finalization: 1
model_rounds: absent / 0
causal_subject_empty_stop: absent / 0
```

Provider timing should be absent.

## Regression coverage

The new open-interval integration regression reproduces the 06:57 live event
shape and verifies:

- no provider call;
- one switch-history request;
- one native-log START-boundary request;
- one open-start correlation;
- deterministic finalization;
- no repeated-controller metric requirement;
- no empty-subject stop;
- no invented duration/end corroboration;
- downstream Humidity Controller wording and mapping/person caveats.

A second regression deliberately removes the physical controller row so causal
prefetch must fall back to model-guided investigation. The model then asks for
Ikea Rodret history, and the test verifies that the controller history cannot
replace the already-prefetched Dehumidifier 2 subject or trigger an empty-subject
stop.
