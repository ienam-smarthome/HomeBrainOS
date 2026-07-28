# Hubitat MCP AI 0.10.189

## RouteRegistry passive shadow diagnostics

- Observes every final HomeBrain query without changing which handler answers.
- Records the complete `RouteRegistry` match set, catalogue winner and actual runtime route.
- Calculates overlap and disagreement rates in a bounded in-memory report.
- Exposes the report at `/api/route-shadow` and emits structured `route_shadow_selection` log lines.
- Begins Phase 0 of issue #266; no route cutover or safety behavior changes are included.
