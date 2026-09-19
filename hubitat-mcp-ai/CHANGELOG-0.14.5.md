# Hubitat MCP AI 0.14.5

## Manual Pushover report delivery

- Replace the placeholder Pushover test action with **Send report to Pushover**.
- Send the latest stored System Check through the same formatter used by the
  scheduled morning notification.
- Include the Hub/Devices/Automations/Logs hierarchy, attention/new/resolved
  totals, and leading actionable findings.
- Keep manual delivery read-only: it does not rerun or modify the health audit.
- Return a clear instruction to run System Check first when no stored report is
  available.
