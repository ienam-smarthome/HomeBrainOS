# Hubitat MCP AI 0.16.10

## Batch verified multi-device controls

0.16.9 proved that HomeBrain could run independent MCP requests concurrently,
but live testing showed only a small wall-clock gain. The remaining cost was
dominated by repeated upstream device-command round trips.

The current Hubitat MCP server advertises a native batch form of
`hub_call_device_command`: up to 20 independent `{deviceId, command,
parameters?}` entries can be sent in one `commands[]` request. The server
validates the complete envelope before firing it and reports per-entry outcomes.

0.16.10 uses that contract for compatible multi-device light/switch controls.

## Execution contract

For two or more compatible targets HomeBrain now:

1. resolves canonical devices exactly as before;
2. performs any required authoritative live precondition reads;
3. builds per-device absolute commands locally;
4. sends one `hub_call_device_command` request with `commands[]`;
5. parses the server's per-device `results[]` without replaying failed or
   uncertain entries;
6. verifies the resulting device state separately before reporting success.

Batch dispatch is currently limited to:

- `on`
- `off`
- `set_level`
- `adjust_level`

Toggle and thermostat writes remain on the established per-device path.

## Verification remains exact

The MCP server's multi-device attribute poll applies one common condition to
every supplied device. HomeBrain therefore uses one `deviceIds` verification
poll only when every successfully dispatched device has the same attribute and
same expected value.

Example: two lights both moving from 60% to 80% can be verified together.

When targets differ, for example 80% -> 100% and 60% -> 80%, HomeBrain still
uses one batch mutation but performs per-device verification polls so one
device's acceptable value cannot accidentally verify another device.

A partial batch response is never automatically replayed. Successfully
dispatched entries may already have actuated, so HomeBrain verifies the entries
the server says were sent and reports failed entries individually.

## Feature detection and rollback

The optimization is enabled only when the live MCP gateway catalog advertises
both the relevant batch-command contract and, where used, multi-device
attribute polling.

Older MCP servers therefore keep the existing per-device path automatically.

A manual rollback is also available:

```yaml
mcp_batch_device_commands_enabled: false
```

## Metrics

Adds:

- `device_control_batch_commands`
- `device_control_batch_verifications`

The first counts batched mutation requests. The second counts common-target
multi-device verification polls.

## Expected live trace

For two Hallway lights both starting at 60%:

```
increase hallway brightness
```

should retain the two live level precondition reads, then show one mutation:

```json
{
  "tool": "hub_call_device_command",
  "args": {
    "commands": [
      {"deviceId": "7820", "command": "setLevel", "parameters": ["80"]},
      {"deviceId": "7829", "command": "setLevel", "parameters": ["80"]}
    ]
  }
}
```

followed by one common postcondition verification:

```json
{
  "tool": "hub_get_device_attribute",
  "args": {
    "deviceIds": ["7820", "7829"],
    "attribute": "level",
    "expectedValue": "80",
    "mode": "all",
    "timeoutMs": 5000
  }
}
```

The semantic fast path, fresh identity grounding, and zero-model behaviour from
0.16.7-0.16.9 are unchanged.
