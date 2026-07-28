# Hubitat MCP AI 0.10.191

## Authoritative hub-log routing and health reconciliation

- Sends `Check logs for any issues` and equivalent bare log queries through the
  deterministic read registry to `hub_get_logs`.
- Filters issue-oriented log requests to warning, error and fatal entries.
- Preserves explicit HomeBrain request diagnostics as a separate evidence
  domain.
- Publishes structured offline/stale/quiet health rows outside size-limited
  debug text.
- Carries authoritative health evidence privately through semantic attention
  reconciliation so confirmed offline devices cannot disappear from the final
  answer when debug JSON is truncated.
