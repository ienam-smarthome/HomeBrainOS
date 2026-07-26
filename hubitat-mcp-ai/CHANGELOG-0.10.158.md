# Hubitat MCP AI 0.10.158

## Changed

- Added `request_composition.py` as the typed owner of named request-handler
  layer composition.
- Changed the unified MCP orchestrator to expose a pure handler builder that
  receives its next route explicitly.
- Changed `entrypoint_core.py` to capture the deterministic control and legacy
  stack, build the unified layer and assign the composed handler once.
- Preserved the compatibility installer for isolated callers and existing
  integrations.

## Validation

- Handler-order, non-mutation and production-wiring structural tests.
- Unified-agent, control-gate, backup, restart, firmware and tracing regression
  suites.
- AST equivalence check for the unified request-handler body.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
