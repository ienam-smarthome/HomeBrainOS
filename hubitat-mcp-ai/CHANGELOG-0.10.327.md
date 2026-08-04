# Hubitat MCP AI 0.10.327

## Changed

- Extracted completed-request outcome classification from `RequestMetrics` into the pure `request_outcome_policy` module.
- Made outcome precedence explicit and independently testable without inspecting prompts, model output, device names, or tool arguments.

## Assurance

- Added focused coverage for every outcome-driving counter.
- Added precedence tests for overlapping refusal, verification-failure, cancellation, expiry, ambiguity, and missing-resolution signals.
- Confirmed operational counters such as model rounds, tool calls, discovery, retries, and confirmation queuing do not alter the final outcome by themselves.

No device-control, confirmation, grounding, transport, history, or Rule Machine behaviour is changed.
