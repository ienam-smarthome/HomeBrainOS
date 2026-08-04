# Hubitat MCP AI 0.10.328

## Changed

- Extracted deterministic direct-outcome request-local setup and cleanup into `DirectOutcomeContext`.
- Kept evidence receipts, choices, request class, and mutation state isolated and restored on both success and failure.
- Added focused lifecycle tests for read/write state, evidence capture, choices, and exception cleanup.

## Compatibility

Device control, confirmation, grounding, metrics classification, transport cancellation, contact history, and Rule Machine behaviour are unchanged.
