# Hubitat MCP AI 0.14.4

## Manual Pushover test

- Add a **Send Pushover test** button beside **Run system check now**.
- Add a dedicated `POST /api/pushover/test` endpoint that uses the saved add-on
  Pushover settings.
- Send a clearly labelled test message without running or modifying the System
  Check snapshot.
- Show successful delivery or a bounded configuration/API error directly in the
  System Check card.
- Keep scheduled morning notifications and manual test notifications separate.
