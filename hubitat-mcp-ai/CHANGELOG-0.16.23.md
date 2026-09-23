# Hubitat MCP AI 0.16.23

## Generic switch-device causal language

0.16.22 proved the direct command-provenance path live at approximately
553-754 ms with:

```text
tool_calls: 3
causal_command_producer_reads: 1
mcp_concurrent_peak: 2
model_rounds: 0
causal_native_log_reads: 0
```

The underlying implementation was already based on switch capability rather
than a Dehumidifier-specific device type. 0.16.23 formalizes and tests that
contract across ordinary lights, sockets and fans, while expanding only
unambiguous switch-state wording.

## Capability-generic subjects

The deterministic causal subject path continues to require:

- one uniquely matched known device;
- a supported switch state exposed by `switch`, `Switch`, or on/off commands;
- an explicit ON/OFF-style state transition;
- authoritative switch history plus direct command producer provenance.

No light/socket/fan hard-coded branch is introduced.

Regression coverage now proves the same fast path for representative HomeBrain
device labels:

```text
Bedroom 1 Light
Bedroom2 (MQTT)
Fan Switch (Tuya Local)
```

Each end-to-end case must retain:

```text
tool_calls: 3
causal_command_producer_reads: 1
model_rounds: 0
causal_native_log_reads: 0
```

## Expanded unambiguous transition language

The deterministic seed now understands additional natural switch-state phrases:

```text
turned itself on / off
switched itself on / off
powered itself on / off
came back on
went back off
shut off
shut itself off
shut down
started running
stopped running
```

These map only to ON/OFF state transitions after a unique switch-capable device
has been identified.

## Ambiguity guard

Wording that does not clearly describe switch state remains outside the
deterministic shortcut.

Examples deliberately kept on the normal reasoning path:

```text
Why did Fan Switch stop responding?
Why did Bedroom 1 Light stop reporting power?
Why did Bedroom2 (MQTT) start updating slowly?
```

This prevents generic words such as "start" and "stop" from turning diagnostics,
connectivity or telemetry questions into false ON/OFF causal claims.

## Existing evidence hierarchy remains unchanged

0.16.23 does not alter the causal evidence hierarchy:

1. adjacent command event with direct `producedBy` provenance;
2. native-log physical controller to command timing;
3. controller event-history temporal correlation;
4. app/rule execution evidence;
5. configuration only.

The 0.16.22 two-read concurrency model is unchanged. No additional Hubitat
requests or higher concurrency are introduced.

## Regression coverage

0.16.23 adds tests for:

- light, MQTT socket and fan identities using the same switch fast path;
- turned/switched/powered itself ON/OFF phrasing;
- came back ON / went back OFF;
- shut off / shut itself off;
- started running / stopped running;
- vague start/stop diagnostic wording rejected by the fast path;
- end-to-end generic devices retaining one command-producer read;
- zero provider/model rounds when direct provenance is sufficient;
- zero native-log reads when direct provenance is sufficient.
