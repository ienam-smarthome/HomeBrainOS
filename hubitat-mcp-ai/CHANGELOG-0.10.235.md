# Hubitat MCP AI 0.10.235

- Adds an authoritative Hub Info snapshot tool for firmware, CPU, memory,
  temperature, uptime, database size, and hub-health questions.
- Invokes the Hub Information Driver's `updateCheck` command before reporting
  firmware availability and polls its asynchronous result.
- Uses the driver's `refresh` command for current resource telemetry.
- Removes the conflicting generic `hub_get_info` tool from Hub Info requests.
- Keeps firmware installation separate and protected by explicit confirmation.
- Presents verified Hub Info results deterministically without another
  model-generated interpretation round.
