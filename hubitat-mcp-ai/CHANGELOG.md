# Hubitat MCP AI changelog

## 0.1.11-alpha

- Routes offline/stale device questions directly through the MCP fast path.
- Adds a dedicated Device health result showing offline and stale counts.
- Excludes intentionally disabled devices from stale-device results.
- Avoids the 40-second Ollama wait for the Device health shortcut.

## 0.1.10-alpha

- Automatically rechecks Ollama inference after a stale timeout.
- Keeps the last question visible and restores it after refresh.
