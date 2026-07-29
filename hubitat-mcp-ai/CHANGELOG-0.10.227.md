# Hubitat MCP AI 0.10.227

- Adds the deterministic local `homebrain_active_rooms` tool.
- Defines an active room consistently as motion active or at least one light switched on.
- Shares the active-room calculation between the dashboard and AI tool path.
- Prevents the agent from incorrectly searching for a generic `active=true` device attribute.
- Returns live grouped room names and activation reasons from an authoritative device snapshot.
