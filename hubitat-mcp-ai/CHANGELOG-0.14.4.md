# Hubitat MCP AI 0.14.4

## Manual Pushover report delivery

- Add a **Send report to Pushover** button beside **Run system check now**.
- Add a dedicated `POST /api/pushover/report` endpoint that uses the saved add-on
  Pushover settings.
- Send the latest stored System Check using the same hierarchy, totals, and top
  findings as the scheduled morning notification.
- Do not rerun or modify the System Check snapshot during manual delivery.
- Show successful delivery or a bounded configuration/API error directly in the
  System Check card.
- Keep scheduled morning notifications and manual test notifications separate.
