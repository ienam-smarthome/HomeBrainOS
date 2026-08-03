# Hubitat MCP AI 0.10.313

## Changed

- Classifies a normally returned request with a recorded cancellation as `cancelled` instead of `success`.
- Preserves grounding-refusal and mutation-verification-failure precedence.
- Keeps cancellation ahead of unresolved conditions such as expired confirmations and ambiguous device resolution.
- Uses only the existing fixed `request_cancellations` counter; no prompt, response text, device name, session identifier, or tool argument is inspected.

## Validation

- Adds focused request-metric tests for cancellation classification and outcome precedence.
