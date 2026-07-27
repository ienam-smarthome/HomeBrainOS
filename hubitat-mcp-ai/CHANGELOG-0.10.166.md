# Hubitat MCP AI 0.10.166

## Added

- A typed `AskLayerRegistry` that observes every live request-wrapper
  assignment while preserving the existing handler order.
- Answering-layer, answering-tier and traversal-count fields in recent request
  performance diagnostics.
- `/api/request-layers` for the ordered runtime request catalogue.
- `scripts/analyze_request_layers.py` for static coverage of all 51 assignment
  sites across 38 production modules.

## Documented

- The six safety-preserving routing tiers plus the request-observability tier.
- The distinction between 38 statically instrumented modules and the 36
  wrappers currently active at startup.
- Confirmation that request layers share the single indexed MCP broker.

## Validation

- Runtime assignment, delegation and terminal-answer instrumentation tests.
- Static request-layer coverage and tier-classification tests.
- Existing composition and MCP tracing regressions.
- Import, cluster and request-layer analysis.
- Repository validation, Python compilation and blocking release gate.
