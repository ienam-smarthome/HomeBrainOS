# Hubitat MCP AI 0.10.218

- Requires real `hub_get_logs` evidence through the read-only diagnostics
  gateway before answering hub-log questions.
- Defaults general log checks to the most recent 30 minutes and 100 entries,
  while respecting user-supplied level, source, device, app, and time filters.
- Reports the queried window, entry count, warning/error counts, and
  representative timestamps.
- Retries once when Ollama attempts to answer without fetching logs, then
  refuses to fabricate a summary if live retrieval still does not occur.
