# Hubitat MCP AI 0.16.21

## MCP Rule Server 4.4.1 provenance compatibility

Upstream Hubitat-local-MCP-server issue #458 is fixed in MCP Rule Server
**4.4.1** by PR #459 / merge commit `7129072`.

That release changes device-event provenance from raw Hubitat HTML into
structured rows:

```text
producedBy: {name, appId}
producedBy: {name, deviceId}
triggered:  [{name, appId, handler}, ...]
type:       command | physical | digital | ...
```

HomeBrain's 0.16.17/0.16.18 causal path already understands direct command
producer provenance, but two compatibility details needed tightening for the
new upstream shape.

## Safe structured metadata handling

The event normalizer previously used scalar set-membership checks when deciding
whether optional metadata was present. A structured `triggered` list is
unhashable in Python and could therefore raise `TypeError`.

0.16.21 changes that test to a scalar-safe null/empty-string check so lists and
dicts are preserved without error.

## Producer type inference

MCP 4.4.1 returns:

```json
{"name":"01. Humidity Controller","appId":3995}
```

or:

```json
{"name":"Dehumidifier 2","deviceId":"4222"}
```

without a separate producer `type` field inside `producedBy`.

HomeBrain now infers:

- `appId` -> producer type `app`
- `deviceId` -> producer type `device`

while continuing to accept the older raw-HTML representation.

## Causal fast path

With MCP 4.4.1 installed, the direct command-producer path can now activate
against the real upstream response for questions such as:

```text
Why did Dehumidifier 2 turn on?
Why did Dehumidifier 2 turn off?
```

For the previously observed interval:

```text
06:57:23.292 command-on
  producedBy: Ikea Rodret (Livingroom): button 2 pushed
        ↓ 99 ms
06:57:23.391 switch=on

08:27:23.518 command-off
  producedBy: 01. Humidity Controller
        ↓ 83 ms
08:27:23.601 switch=off
```

the expected deterministic path remains:

```text
causal_subject_prefetch: 1
causal_command_producer_reads: 2
causal_command_producer_provenance: 1
causal_deterministic_finalization: 1
causal_native_log_reads: 0
model_rounds: 0
```

## Regression coverage

0.16.21 adds tests using the exact MCP 4.4.1 structured shapes and verifies:

- structured `{name, appId}` producers normalize to app identity;
- structured `{name, deviceId}` producers normalize to device identity;
- structured `triggered` lists survive normalization without error;
- direct ON/OFF command producer evidence still correlates to the observed
  switch boundaries;
- the end-to-end causal answer finalizes without `hub_get_logs` or a provider
  round when MCP 4.4.1 provenance is present.

## Upgrade order

1. Update MCP Rule Server to **4.4.1**.
2. Update HomeBrain to **0.16.21**.
3. Refresh MCP tools / reconnect the HomeBrain MCP session.
4. Retest the Dehumidifier 2 ON/OFF causal questions.
