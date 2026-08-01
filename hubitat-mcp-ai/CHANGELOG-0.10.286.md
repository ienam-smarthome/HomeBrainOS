# Hubitat MCP AI 0.10.286

## Changed

- Extracted consumed-confirmation execution from `UnifiedMCPAgent` into
  `ConfirmedActionCoordinator`.
- Kept the existing orchestrator compatibility methods while centralising
  upstream approval injection, sequential execution, and completion reporting.

## Safety

- Queued Rule Machine payloads are revalidated after confirmation and before
  execution.
- Rule Machine groups stop immediately after the first unverified write.
- Success requires a successful structured result, returned rule/app ID, no
  partial flag, and a healthy result.
- Generic confirmed actions continue through the shared `ToolExecutor` and
  bounded post-execution synthesis path.

## Tests

- Added focused coverage for verified multi-rule groups, upstream confirmation
  injection, fail-fast behavior, skipped-action reporting, malformed queued
  payloads, generic confirmed actions, and nested result envelopes.
