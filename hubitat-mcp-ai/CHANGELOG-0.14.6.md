# Hubitat MCP AI 0.14.6

## Compact System Check and richer Pushover report

- Replace the large coloured System Check summary sentence with a compact
  **System check** label and status badge, leaving the counts and detail cards
  to carry the diagnostic summary.
- Keep the last-check and next-run metadata immediately below the compact
  heading.
- Expand Pushover System Check reports with named sections for offline devices,
  low batteries, broken automations, log findings, other findings, and resolved
  findings.
- Bound each notification section and show a `+N more` marker when a category
  exceeds its display limit, while preserving Pushover's 1024-character message
  limit.
- Keep manual **Send report to Pushover** delivery on the stored audit; it does
  not rerun or modify the System Check.
