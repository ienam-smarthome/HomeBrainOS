# Hubitat MCP AI 0.10.294

## Added

- Added `api_response_builder.build_agent_response` as the stable serializer for `/api/ask` results.
- Included privacy-safe `ObservedAgentOutcome.metrics` in the serialized response contract without removing or renaming existing fields.
- Added regression coverage for legacy outcomes, mutable-payload isolation, elapsed-time normalization, and exclusion of prompt/session identifiers.
- Added `ProviderTokenEstimator`, a dependency-free conservative estimator for provider payload budgeting.
- Added stable profiles for Qwen, Gemma, Llama, Mistral, and unknown model families.
- Added UTF-8 byte-aware estimates, message-structure allowances, and deterministic token-to-character ceiling helpers.
- Added focused estimator tests covering empty content, family selection, Unicode, structural overhead, and fallback behaviour.

## Safety

- Evidence and metrics are deep-copied before being returned to API callers.
- Prompt text, query text, session IDs, and request IDs are not introduced by the response builder.
- Token estimates are explicitly approximate and advisory.
- Existing character limits remain the hard deterministic fallback.
- No prompt content, device names, credentials, or tool arguments are logged or persisted by the estimator.

## Follow-up

- Wire the FastAPI `/api/ask` endpoint to the response builder.
- Wire the estimator into `ModelContextPolicy` behind the existing character caps.
