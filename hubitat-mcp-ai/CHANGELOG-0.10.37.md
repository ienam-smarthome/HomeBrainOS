# Hubitat MCP AI 0.10.37

- Makes explicit device lookup requests terminal and deterministic.
- Resolves exact device IDs before reading sensor attributes.
- Uses `hub_read_devices` for live values such as illuminance instead of relying on projected inventory.
- Prevents Gemma from replacing authoritative values with missing-value guesses.
