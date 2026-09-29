# Hubitat MCP AI 0.16.62

## Performance wording and metric compatibility

- Outcome-causality localization now starts at the full certainty/relation phrase and strips a trailing conjunction before preserving a measured prefix, preventing malformed output such as `is likely the; ...`.
- A prefix is retained as a measured fact only when it actually contains bounded numeric/measured evidence; otherwise the whole unsupported causal sentence is replaced with the existing neutral grounding statement.
- `hub_get_performance_stats` receives a narrow compatibility normalization for the affected upstream `databaseSizeKB` label. The numeric value is preserved without scaling and exposed as `databaseSizeMB`, while `databaseSizeRaw` retains the legacy field name and value for provenance.
- Future upstream results that already provide `databaseSizeMB`, non-numeric legacy values, failed tool calls, and unrelated tool results remain untouched.
- No additional Hubitat calls are introduced.

## Regression coverage

Focused tests reproduce the 0.16.61 dangling `is likely the;` failure and the live `databaseSizeKB: "166"` unit-label mismatch, and verify future-correct/non-numeric/unrelated payloads remain unchanged.

Release metadata is aligned across the add-on version, release-note index, repository summary, and runtime module map.
