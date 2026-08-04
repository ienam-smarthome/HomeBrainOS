# Hubitat MCP AI 0.10.321

## Changed

- Extracted request observation into a dedicated `RequestObservationCoordinator`.
- Moved request metrics lifecycle handling, observed-outcome construction, cancellation classification, and failure classification out of `homebrain_agent.py`.
- Preserved existing routing, tool selection, confirmation, grounding, and transport behaviour.
- Added focused tests for successful, cancelled, and failed request observation paths.
- Updated the authoritative runtime module map for `request_observation.py`.
