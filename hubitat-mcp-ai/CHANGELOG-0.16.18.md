# Hubitat MCP AI 0.16.18

## Direct command provenance for OFF questions

0.16.17 made an adjacent Hubitat `command-on` event with explicit
`producedBy` metadata sufficient for an explicit turn-on question. It already
collected and correlated `command-off` rows, but the host intentionally did not
yet use those rows as a deterministic final answer for questions such as:

```text
Why did Dehumidifier 2 turn off?
```

0.16.18 completes that symmetry.

## Transition-aware sufficiency

The command-provenance layer now evaluates the transition the user actually
asked about:

- `on` requires direct producer metadata on the observed START boundary;
- `off` requires direct producer metadata on the observed END boundary;
- unsupported/ambiguous transition names are not treated as sufficient.

The original `command_producer_turn_on_sufficient()` helper remains as a
compatibility wrapper around the new transition-aware contract.

## OFF-focused deterministic answer

For the golden closed interval:

```text
06:57:23.292 command-on
  Produced By: Ikea Rodret (Livingroom): button 2 pushed
        ↓ 99 ms
06:57:23.391 switch=on

08:27:23.518 command-off
  Produced By: 01. Humidity Controller
        ↓ 83 ms
08:27:23.601 switch=off
```

an explicit turn-off question now leads with the END-boundary evidence:

```text
Hubitat records the OFF command for Dehumidifier 2 as produced by
01. Humidity Controller.
```

The answer then reports the 83 ms command-to-state interval and, when the
matching START boundary is also available, includes the observed run duration
and ON producer as context. It does not confuse the earlier ON producer with the
cause of the later OFF transition.

The existing caveat remains: **Produced By identifies the Hubitat app/action
that issued the command, not the person who initiated that action.**

## Zero-log / zero-model fast path

When authoritative OFF command provenance is available and deterministic causal
finalization is enabled, HomeBrain can answer without:

- historical `hub_get_logs` calls;
- room/controller fan-out;
- provider/model synthesis.

Target metrics for the closed Dehumidifier 2 example:

```text
causal_subject_prefetch: 1
causal_command_producer_reads: 2
causal_command_producer_provenance: 1
causal_deterministic_finalization: 1
investigative_finalization: 1

causal_native_log_reads: absent / 0
model_rounds: absent / 0
provider timing: absent
```

## Upstream MCP dependency

HomeBrain's command-producer path requires the Hubitat MCP server to preserve
the native event `producedBy` field. That upstream mapper currently drops this
metadata and is tracked in:

- kingpanther13/Hubitat-local-MCP-server issue #458

Until that server change is available, 0.16.18 remains backward compatible:
missing command provenance simply falls through to the established native-log
causal path. No direct-provenance claim is synthesized from missing metadata.

## Regression coverage

The 0.16.18 tests verify:

- ON and OFF command-producer sufficiency independently;
- unsupported transitions are rejected;
- an OFF-only producer cannot satisfy an ON question;
- OFF-focused deterministic wording leads with the OFF producer;
- matching ON provenance is retained only as context for the closed run;
- the end-to-end `Why did Dehumidifier 2 turn off?` path performs no
  `hub_get_logs` read and no provider call when direct OFF provenance exists.
