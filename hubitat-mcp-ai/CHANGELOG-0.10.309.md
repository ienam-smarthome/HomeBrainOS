# Hubitat MCP AI 0.10.309

## Changed

- Classify a normally returned request with a fail-closed ambiguous device resolution as `refused` rather than `success`.
- Use the existing fixed `device_resolution_ambiguous` counter at the deterministic resolver boundary; no prompt or response-text parsing is introduced.
- Preserve `success` for ordinary completed requests and keep events outside an active request context unrecorded.

## Tests

- Added production-agent coverage for ambiguous resolution outcomes.
- Extended request-metrics regression coverage to confirm privacy-safe classification and unchanged normal success behaviour.
