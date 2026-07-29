# Hubitat MCP AI 0.10.226

- Adds a clickable **Install firmware update** action whenever a firmware-status answer offers an available update.
- Interprets “yes,” “yes please,” “proceed,” and “do it” as the offered firmware action while that offer is active.
- Keeps the destructive firmware confirmation gate in place before calling Hubitat.
- Sends a bounded recent conversation history with WebUI requests so contextual follow-ups work.
- Stores the latest eight user/assistant turns in session storage and restores them across normal page refreshes.
