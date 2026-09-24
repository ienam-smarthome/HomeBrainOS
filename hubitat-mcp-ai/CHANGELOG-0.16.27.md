# Hubitat MCP AI 0.16.27

## Preserve authoritative boundary provenance for short intervals

A live 0.16.26 Bedroom 1 Light investigation exposed a narrow regression.

The newest observed ON interval was only about 12 seconds long:

```text
14:58:47.954 switch=on
  producedBy: Matter Hue Bridge Pro

14:58:59.777 switch=off
  producedBy: Matter Hue Bridge Pro
```

There was no `command-on` producer.

The generic causal timeline deliberately marks intervals under five minutes as
non-material unless stronger command/controller evidence is already present.
That threshold is useful for weaker contextual reasoning, but
`correlate_boundary_producers()` was incorrectly applying the same filter to
direct structured switch-boundary provenance.

As a result, the authoritative Hue/Matter producer on the 12-second boundary was
discarded, the deterministic reporting-source path never activated, and the
request fell back to model exploration.

Observed failure shape:

```text
causal_subject_prefetch: 1
causal_command_producer_reads: 1
causal_boundary_producer_provenance: 0
causal_reporting_source_correlation: 0
model_rounds: 3
tool_calls: 11
total: ~45.8 s
```

## Fix

0.16.27 separates direct boundary provenance from generic timeline materiality.

Structured switch-boundary `producedBy` is now eligible for deterministic
correlation for any observed bounded interval duration.

The five-minute materiality rule remains unchanged for weaker timeline/context
reasoning. Only direct authoritative boundary-producer correlation bypasses that
duration threshold.

This means a brief physical transition such as:

```text
switch=on
type=physical
producedBy=Matter Hue Bridge Pro
```

can still activate the reporting-source path even if the light turns off a few
seconds later.

## Safety

The change does not relax producer requirements:

- the boundary must still be an observed switch transition;
- it must carry structured non-empty `producedBy`;
- self-produced device boundaries remain insufficient;
- reporting-source provenance remains distinct from proof of the initiating
  action;
- direct command provenance retains higher priority;
- native-log/model fallback remains available when stronger evidence is absent.

## Regression coverage

0.16.27 adds an end-to-end regression using the live short-interval shape:

```text
off -> on -> off
latest ON duration: ~12 seconds
command-on rows: 0
boundary producer: Matter Hue Bridge Pro
```

The required result:

```text
model_rounds: 0
causal_boundary_producer_provenance: 1
causal_deterministic_finalization: 1
causal_native_log_reads: 0
```

and the answer must identify Matter Hue Bridge Pro as the reporting path without
promoting it to the exact initiating action.
