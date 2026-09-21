# Hubitat MCP AI 0.14.21

## Routine dimmer control and correct command-shape handling

- Fix a live 0.14.20 failure when setting two Living Room lights to 100%.
- Treat Hubitat `setLevel` as a routine device command, including camelCase
  command names emitted by the model.
- Inspect every command inside a batched `hub_call_device_command` request so a
  routine batch no longer inherits the gateway's broad destructive hint and asks
  for an unnecessary confirmation.
- Preserve fail-closed behaviour for mixed batches: if any contained command is
  sensitive, the whole batch still requires confirmation.
- Normalize common model-emitted command parameter objects into the positional
  arrays required by the Hubitat MCP gateway:
  - `setLevel {"level": 100}` -> `parameters: [100]`
  - `setColorTemperature {"temperature": ...}` -> one positional value
  - `setColor {...}` -> one map argument wrapped in the parameter array
- Add deterministic immediate `set_level` control so requests such as
  **set living room lights to 100%** can bypass the model/tool-discovery loop,
  resolve the room lights, send `setLevel`, and verify the live `level`
  attribute.
- Keep dimmer level bounded to 0-100.
- Mark generic confirmed-action execution failures with
  `mutation_verification_failures`, so the final request outcome is **failed**
  rather than a contradictory **Success** badge.
