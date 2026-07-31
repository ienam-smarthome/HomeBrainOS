# Hubitat MCP AI 0.10.259

- Detect automation records that expose conflicting source-state signals.
- Add `status_conflict`, `conflicting_statuses`, and the raw `active` signal to each structured automation item.
- Add a top-level `conflict_count` to automation-status responses.
- Mark conflicts in the text fallback so upstream Hubitat inconsistencies are visible instead of silently hidden by precedence.
- Add regression tests for conflict detection and reporting.
