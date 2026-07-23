# Hubitat MCP AI 0.10.64

- Retries `hub_update_firmware` exactly once when a fresh backup was independently verified but the MCP firmware guard still reports `BACKUP REQUIRED`.
- Waits four seconds for the MCP backup index to settle.
- Does not create another backup or repeat the destructive confirmation.
- Returns a specific backup-index-lag message if the single retry remains blocked.
