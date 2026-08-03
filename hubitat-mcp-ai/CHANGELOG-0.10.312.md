# Hubitat MCP AI 0.10.312

## Changed

- Classifies a normally returned expired confirmation as `unresolved` instead of `success`.
- Keeps grounding refusal and mutation verification failure precedence unchanged.
- Uses the existing fixed `confirmation_expired` counter; no prompt, response text, device name, session identifier, or tool argument is inspected.

## Validation

- Adds focused request-metric tests for expired confirmation classification and precedence.
