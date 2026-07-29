# Hubitat MCP AI 0.10.229

## High-level light and switch control

- Adds the native `homebrain_control_devices` tool for routine `on`, `off`, and
  `toggle` commands.
- Resolves either an exact Hubitat room or exact device labels against the live
  short-TTL device snapshot before sending any command.
- Fails closed when a target is missing or ambiguous, so partial name guesses
  cannot control an unintended device.
- Executes multi-device room commands concurrently through
  `hub_manage_devices`.
- Returns a deterministic command receipt immediately after execution, avoiding
  a second Ollama synthesis round for faster control.
- Keeps routine light and switch control confirmation-free while preserving the
  existing sensitive-action gate for locks, security devices, garage doors, and
  destructive operations.

