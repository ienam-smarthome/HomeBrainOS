# Hubitat MCP AI 0.10.192

## Complete 24-hour Hubitat log issue scan

- Uses separate server-side `error` and `warn` filters with `since=24h` and
  `limit=500` instead of fetching the default latest 100 mixed-level rows.
- Deduplicates overlapping results and groups recurring entries by app or
  device source.
- Shows error, warning, source and time-window metrics.
- Includes the latest representative warning/error for each source so repeated
  device check-in, bridge reconnect and protocol warnings are visible.
