# Hubitat MCP AI 0.10.46

- Adds a deterministic, session-scoped firmware update confirmation workflow.
- Presents clickable **Yes - update hub** and **No - cancel** actions in Home Assistant.
- Expires confirmation after two minutes and consumes it before issuing the write.
- Calls `hub_update_firmware` exactly once only after explicit confirmation.
- Adds cancel, expiry, cross-session, duplicate-submit, and rejection regression coverage
  to the blocking release gate.
