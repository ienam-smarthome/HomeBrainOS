# 0.10.26

- Routes all device controls terminally through the typed Control Agent resolver,
  capability validator, MCP executor and fresh-state verifier.
- Excludes device-control candidates from unified AI synthesis regardless of their
  wording complexity.
- Rejects control-success claims when no `hub_call_device_command` or other approved
  mutation tool actually ran.
- Parses prefix ordinal commands such as `Turn off the second hallway light`
  deterministically and resolves the numbered room device before writing.
