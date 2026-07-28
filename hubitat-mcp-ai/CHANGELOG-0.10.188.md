# Hubitat MCP AI 0.10.188

## Diagnostics routing and structured health evidence

- Routes HomeBrain diagnostics requests to recent request-trace evidence rather than generic home-attention synthesis.
- Clearly states when Home Assistant Supervisor and add-on log files were not inspected.
- Preserves `offline`, `stale` and `quiet` as structured device-health kinds end-to-end.
- Prevents `Quiet, not offline` from being misclassified by substring matching.
- Deduplicates health evidence by device ID, falling back to normalized labels only when required.
- Keeps quiet event-age rows out of offline and stale fault counts.
- Verifies final attention counts against the authoritative structured health kinds.
