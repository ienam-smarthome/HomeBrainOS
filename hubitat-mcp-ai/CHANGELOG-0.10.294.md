# Hubitat MCP AI 0.10.294

## Added

- Added `api_response_builder.build_agent_response` as the stable serializer for
  `/api/ask` results.
- Included privacy-safe `ObservedAgentOutcome.metrics` in the serialized response
  contract without removing or renaming existing fields.
- Added regression coverage for legacy outcomes, mutable-payload isolation,
  elapsed-time normalization, and exclusion of prompt/session identifiers.

## Safety

- Evidence and metrics are deep-copied before being returned to API callers.
- Prompt text, query text, session IDs, and request IDs are not introduced by the
  response builder.

## Follow-up

- The FastAPI `/api/ask` endpoint will switch to this builder in a separate narrow
  wiring change after this component passes the release gate.
