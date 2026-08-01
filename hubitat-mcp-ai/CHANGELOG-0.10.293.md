# Hubitat MCP AI 0.10.293

- Wired the privacy-safe `RequestMetrics` component into the maintained production agent.
- Added request-local model-round, provider-time, recorded-tool-call, confirmation, cancellation, total-duration, and outcome metrics.
- Added `ObservedAgentOutcome`, preserving all existing outcome fields while carrying the metrics snapshot.
- Kept metric labels fixed so prompts, device names, credentials, and tool arguments cannot enter metric dimensions.
- Added regression coverage for provider timing, outcome metrics, confirmation counts, and prompt-data exclusion.
