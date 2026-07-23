# Hubitat MCP AI 0.10.49

- Forces a new Hubitat backup after explicit firmware-update confirmation.
- Verifies that backup through the hardened backup workflow before issuing the update.
- Does not rely on filename-date inference, which can disagree with the MCP server's
  authoritative admin-write backup registry.
