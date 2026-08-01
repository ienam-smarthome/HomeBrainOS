# Hubitat MCP AI 0.10.264

- Added a structured tool-effect registry with `read`, `routine_write`,
  `sensitive_write`, and `destructive_write` classifications.
- Added the effect to evidence receipts for auditability.
- Added shadow comparison logging against the existing mutation gate without
  changing execution or confirmation behaviour.
- Made unknown management operations fail closed as sensitive writes.
- Added regression coverage for read sub-operations, routine controls,
  sensitive actions, destructive actions, and shadow disagreements.
