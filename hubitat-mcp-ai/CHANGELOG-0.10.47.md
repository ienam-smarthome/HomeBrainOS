# Hubitat MCP AI 0.10.47

- Creates and verifies a recent Hubitat backup before issuing a firmware update.
- Reuses the guarded backup service with best-practice acknowledgment, idempotency,
  recent-backup verification, and timeout polling.
- Blocks the update when backup creation or verification fails.
- Distinguishes a definite MCP policy rejection from a genuinely uncertain timeout.
