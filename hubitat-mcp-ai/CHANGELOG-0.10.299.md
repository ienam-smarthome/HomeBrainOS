# Hubitat MCP AI 0.10.299

## Added

- Recorded `evidence_retries` at the exact grounding retry decision.
- Recorded `grounding_refusals` at the exact fail-closed refusal decision.
- Passed the active request-local metrics collector into `LiveEvidenceAuthority`.

## Safety

- Metrics use only the existing fixed vocabulary.
- Prompts, device names, tool arguments, and session identifiers are not recorded.
- Accepted conversational or evidence-backed answers do not increment either counter.
- Direct base-agent callers retain the original grounding-policy behaviour.

## Tests

- Added coverage for retry, refusal, and accept metric behaviour.
