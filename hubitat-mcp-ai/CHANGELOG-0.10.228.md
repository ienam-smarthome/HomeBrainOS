# Hubitat MCP AI 0.10.228

- Adds the deterministic local `homebrain_active_switches` tool.
- Shares one non-light switch calculation between the dashboard and AI.
- Defines the Switches on count as `switch=on` while excluding Light/Bulb devices.
- Ensures the AI's reported count exactly matches the devices it lists.
- Prevents switched-on lights such as Bedroom 1 Light from appearing in the non-light switch list.
