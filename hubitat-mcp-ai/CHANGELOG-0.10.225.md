# Hubitat MCP AI 0.10.225

- Replaces the expanded active-room, room inventory, and Hub Info dashboard sections with one compact Active rooms tile beside Lights on.
- Keeps structured room and Hub Info data available to the API and AI without occupying dashboard space.
- Allows natural-language requests to install an available Hubitat firmware update through `hub_update_firmware`.
- Verifies update availability first, requires explicit session confirmation, warns that the hub may restart, and invokes the firmware tool exactly once with `confirm=true`.
- Preserves the MCP server's backup requirement and never bypasses a backup guard.
