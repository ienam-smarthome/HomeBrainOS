# Hubitat MCP AI 0.10.265

- Made structured tool effects authoritative for mutation classification and
  sensitive-action confirmation.
- Removed the legacy argument-token mutation and sensitivity gates.
- Allowed known read and routine sub-operations to override broad gateway
  annotations without weakening sensitive or destructive handling.
- Kept unknown management operations fail-closed as sensitive writes.
- Added end-to-end regression coverage for manage-gateway reads, routine device
  commands, and confirmed sensitive device commands.
