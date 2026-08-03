# Hubitat MCP AI 0.10.319

## MCP retry observability

- Records each actual retry attempt at the MCP transport loop immediately before the next HTTP POST.
- Covers both transient transport errors and retryable HTTP 5xx responses.
- Does not count cancellation during backoff as a retry that never started.
- Exposes the fixed `mcp_retries` counter through technical metrics as `MCP retries`.

## Safety

- Keeps retry eligibility unchanged: non-read tool calls remain non-retryable unless already classified as safe by the existing transport policy.
- Uses the active request metrics context and never derives counters from log text, prompts, device names, or response content.

## Validation

- Adds transport-boundary tests for transport-error retry, HTTP 5xx retry, presenter output, and cancellation during backoff.
