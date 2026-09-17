# Hubitat MCP AI 0.10.439

## Rule condition integrity and latency

- Reject the unsupported `requiredExpression` Rule Machine field before confirmation and direct callers to `addRequiredExpression` or `replaceRequiredExpression` with live discovery.
- Treat non-empty `partialTriggers`, `partialActions`, or `repairHints` as an unverified Rule Machine write even when the hub returns an ID and `health.ok=true`.
- Include component-level failure details in the deterministic post-confirmation report instead of claiming that a partial rule is healthy.
- Skip the eager full-device identity manifest for model-routed rule-authoring requests; targeted device resolution remains authoritative and avoids the slow 124-device snapshot observed during live testing.
- Add regression coverage for the Big Lamp required-expression failure, component-level partial results, and the rule-authoring manifest decision.
