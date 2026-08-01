# Hubitat MCP AI 0.10.292

## Request observability foundation

- Adds request-local `RequestMetrics` state for fixed counters and stage timings.
- Supports model rounds, tool calls, discovery, evidence retries, refusals,
  confirmations, mutation verification failures, cancellation, and ambiguous
  device-resolution counters.
- Supports provider, discovery, MCP, verification, and total elapsed timings.
- Rejects dynamic metric names so prompts, device labels, credentials, and tool
  arguments cannot become observability labels.
- Keeps metric state isolated between concurrent async request contexts.
- Adds regression tests for collection, validation, isolation, reset, and calls
  made outside an active request.

This release adds and validates the observability component only. Production
request wiring will follow as a separate narrow change.
