# Hubitat MCP AI 0.10.294

## Added

- `ProviderTokenEstimator`, a dependency-free conservative estimator for provider payload budgeting.
- Stable profiles for Qwen, Gemma, Llama, Mistral, and unknown model families.
- UTF-8 byte-aware estimates so non-ASCII content is not undercounted by Python character length.
- Message-structure allowances and deterministic token-to-character ceiling helpers.
- Focused tests covering empty content, family selection, Unicode, structural overhead, and fallback behaviour.

## Safety

- Estimates are explicitly approximate and advisory.
- Existing character limits remain the hard deterministic fallback.
- No prompt content, device names, credentials, or tool arguments are logged or persisted by the estimator.

## Next

- Wire the estimator into `ModelContextPolicy` behind the existing character caps after this component is validated.
