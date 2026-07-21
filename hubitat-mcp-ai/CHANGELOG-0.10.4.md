# 0.10.4

- Pages detailed device-health inventory reads with bounded `limit` and `offset`
  requests, then aggregates every page before classifying devices.
- Detects the MCP `response_too_large` and `truncated` response shapes directly,
  including the byte limit reported by the server.
- Detects repeated pages from MCP servers that ignore `offset` and applies a
  bounded pagination safety limit.
- Reports incomplete coverage instead of claiming no devices are offline or stale
  when the complete inventory cannot be verified.
- Adds regression coverage for oversized responses, multi-page aggregation and
  repeated-page detection.
