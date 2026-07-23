# Hubitat MCP AI 0.10.48

- Calls `hub_get_info` before creating a firmware-update confirmation.
- Displays the installed Hubitat version, available version, and release channel.
- Offers Yes/No only when authoritative evidence says an update is available.
- Reports up-to-date or unreadable status without sending a firmware command.
