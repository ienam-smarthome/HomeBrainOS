# Hubitat MCP AI 0.10.295

## Changed

- Wired `ProviderTokenEstimator` into the maintained production agent through
  `TokenAwareModelContextPolicy`.
- Provider-aware token estimates can tighten retained conversation history and
  cumulative tool-result context.
- Existing configured character limits remain hard upper bounds.
- Direct base-agent callers retain the original `ModelContextPolicy` contract.

## Safety

- Token estimates can never increase the configured character budgets.
- The policy remains dependency-free and does not log or persist prompt content.
- Authoritative transcripts, evidence receipts, confirmation state, and tool
  results remain untouched; only copied provider payloads are bounded.
