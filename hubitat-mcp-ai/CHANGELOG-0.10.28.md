# Hubitat MCP AI 0.10.28

## Runtime and Web UI version alignment

- Fixes the Web UI header incorrectly showing v0.10.23 after newer add-on updates.
- Stops the PWA installer from overwriting the authoritative runtime release version.
- Makes the rendered header use the entrypoint release version.
- Refreshes the service-worker cache namespace so older cached HTML is discarded.
- Keeps the Home Assistant manifest, FastAPI runtime, status API and Web UI aligned.
