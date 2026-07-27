# Hubitat MCP AI 0.10.178

## Fixed

- Restored the exact semantic home-summary route to `AnswerGuardRegistry` after
  the 0.10.177 startup hotfix reverted only its public entrypoint wiring.
- Retained the startup-safe ordering where request composition is finalised
  before `install_runtime_route_bridge()` performs HTTP route setup.

## Preserved

- Verified semantic evidence collection.
- Required-fact validation and deterministic synthesis fallback.
- Existing response metadata and passthrough behaviour.
- Direct runtime route setup, cancellable `/api/ask`, diagnostics and Web UI.

## Validation

- Added a wiring regression that requires both the semantic summary registry and
  the direct runtime route bridge setup to remain present together.
