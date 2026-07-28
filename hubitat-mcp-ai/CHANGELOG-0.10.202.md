# Hubitat MCP AI 0.10.202

- Send Gemini function responses with the supported `user` role instead of the
  rejected `tool` role.
- Apply confirmation rules to the selected gateway operation, allowing
  read-only `hub_manage_devices` queries without confirmation while retaining
  confirmation for mutations.
- Restore response metadata, timing, a confirmation button, and expandable
  technical details in the WebUI dashboard.
