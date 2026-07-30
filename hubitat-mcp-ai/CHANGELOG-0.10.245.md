# Hubitat MCP AI 0.10.245

## Resilient MCP reads and unified prompt policy

- Adds configurable retries with exponential backoff for transient MCP
  connection failures, timeouts, and HTTP 5xx responses.
- Restricts automatic retries to read-only and protocol operations so an
  uncertain mutation response cannot duplicate a device command.
- Exposes retry attempts and initial backoff through Home Assistant add-on
  options.
- Extracts prompt construction from the orchestrator into a dedicated policy
  module.
- Replaces phrase-triggered correctness fragments with one compact capability
  contract that consistently covers live reads, controls, firmware, health,
  logs, and whole-home summaries.
- Corrects firmware guidance to use the authoritative Hub Info snapshot and
  replaces nested evidence classification with an explicit mapping.
- Adds regression coverage for transient recovery, non-retryable client
  failures, exhausted retries, and mutation retry safety.
