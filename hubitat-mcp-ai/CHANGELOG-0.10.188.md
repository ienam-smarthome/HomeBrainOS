# Hubitat MCP AI 0.10.188

## Diagnostics routing and health evidence reconciliation

- Routes requests to inspect HomeBrain logs, errors or warnings to deterministic
  recent request diagnostics instead of whole-home attention analysis.
- Clearly states that Supervisor and add-on log files were not inspected when only
  HomeBrain request traces are available.
- Reconciles semantic attention output with authoritative device-health evidence.
- Counts only explicit negative health states as offline, keeps genuine telemetry
  failures stale and suppresses quiet event-age rows from fault totals.
- Rebuilds the summary from reconciled facts so headline counts match the evidence.
