# HomeBrainOS 0.18.137 — actionable V2 MCP read failure categories

- An opt-in V2 failed source read now reports a locally classified **failure code** such as `read_timeout`, `mcp_tool_reported_error`, `executor_reported_failure`, `upstream_http_error`, `mcp_protocol_error`, `no_authoritative_result` or `response_identity_mismatch`. Error classes are distinguished without copying remote messages, URLs, credentials or raw tool output.
- Add a bounded `read_failures` array with source receipt ID, tool/sub-operation, verified numeric target when available, elapsed milliseconds and a safe classification. Failures are also visible on case coverage and as a brief list in the user-facing report.
- The V2 test metrics include `Failed MCP reads`, while preserving duration displayed in minutes/seconds (and total seconds). Command retention remains explicitly scoped to retrieved records, not completeness of Hubitat history.
- Tests exercise failed/error MCP results, missing execution results, real host exceptions and redaction. All existing manifest/schema checks and read-only execution constraints remain intact. Normal Ask stays V1.
