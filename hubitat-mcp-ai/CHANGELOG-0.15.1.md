# Hubitat MCP AI 0.15.1

## Fix relative/absolute brightness writes against the current Hubitat MCP schema

A live 0.15.0 trace showed that semantic planning and live precondition reads were
correct, but every `setLevel` mutation was rejected immediately by the upstream
MCP gateway.

The upstream `hub_call_device_command` schema requires:

- `parameters[]` values to be strings
- `waitFor.expectedValue` to be a string

HomeBrain 0.15.0 kept brightness targets as numbers all the way into the wire
payload, for example:

```json
{
  "command": "setLevel",
  "parameters": [70],
  "waitFor": {"attribute": "level", "expectedValue": 70}
}
```

0.15.1 preserves numeric values internally for arithmetic and reporting, then
converts only at the MCP transport boundary:

```json
{
  "command": "setLevel",
  "parameters": ["70"],
  "waitFor": {"attribute": "level", "expectedValue": "70"}
}
```

The Hubitat MCP server then normalizes the declared NUMBER command parameter
before dispatching it to the device.

### Diagnostics

Failed command evidence now includes the upstream error text when available,
rather than recording only `adjust_level <device>: failed`. This makes future
wire/schema failures directly visible in the request trace.

### Regression coverage

Tests now assert the actual upstream MCP wire contract for both absolute and
relative brightness control, including string command parameters and string
wait-for values.
