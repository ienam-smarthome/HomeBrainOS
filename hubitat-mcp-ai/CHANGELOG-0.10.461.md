# Hubitat MCP AI 0.10.461

## Investigative history: preserve reasoning and remove the slow room-scan path

Live 0.10.460 testing exposed two different issues that only appear on richer
history questions.

A normality-style question could produce useful model analysis and then lose it at
the API boundary because the unverified-duration guard replaced the entire answer
with a one-line deterministic duration correction. A causal/investigative question
could also spend most of its latency on a full detailed device inventory simply to
find other devices in the same room.

0.10.461 fixes both while keeping deterministic history arithmetic and source
integrity rules unchanged.

### Localized duration correction

For an unverified event stream, a correctly rounded duration can remain in the
model answer when the same sentence explicitly presents it as an estimate or
recorded observation.

If the model states a wrong duration or upgrades the evidence to exact/continuous
language, HomeBrain now replaces only the unsafe duration/continuity sentence.
Other grounded observations, comparisons and cautiously worded correlations are
preserved.

Zero-interval unverified history keeps the stricter deterministic serializer.

### Investigative-history contract

History questions involving cause/trigger/reason, normality/expectation,
comparison, or correlation now receive an explicit evidence contract after the
subject history read:

- device history proves recorded transitions, not their cause;
- causal attribution should use a materially relevant independent source when
  available;
- normal/abnormal claims must not invent a generic baseline;
- objective event patterns may be described even when a stronger normality
  judgement is not established;
- comparisons/correlations require the relevant second side;
- unrelated exhaustive reads are discouraged.

Straight factual temporal questions keep the 0.10.460 evidence-sufficiency fast
path.

### Structural filters use hubitat://context

`homebrain_filter_devices` now uses the complete bulk live-context resource for
structural fields such as room, label, id and capabilities instead of falling back
to a detailed `hub_list_devices` inventory.

This directly addresses the live 0.10.460 causal run where filtering
`room contains Bedroom 3` forced a 12.449-second full inventory read.

Filter matches now include compact capabilities and seed request-local resolved
identity by exact label/id. If the model then asks for history on a returned
related sensor, DeviceHistoryService can reuse the known device id instead of
issuing another targeted label lookup. Required-command checks still fail closed
when compact identity does not include command metadata.

## Validation targets

Regression tests cover:

- structural room filtering through `hubitat://context` with no full inventory;
- compact capabilities on returned room matches;
- request-local history reuse for a related sensor discovered by a filter;
- preserving non-duration investigative prose when an unsafe duration sentence is
  corrected;
- leaving a correctly qualified unverified estimate unchanged; and
- supplying the investigative-history evidence contract while keeping callable
  tools available for normality questions.
