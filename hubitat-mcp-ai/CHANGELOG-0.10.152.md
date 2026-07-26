# Hubitat MCP AI 0.10.152

## Changed

- Consolidated actuator eligibility, selected read-only device evidence and
  control-graph filtering in `control_agent_graph.py`.
- Preserved exact capability, command, live-state and conservative label checks
  used to prevent sensors from being treated as controllable devices.
- Redirected the live rescue and combined-level services plus focused safety
  tests to the graph owner.

## Removed

- Removed the superseded sibling-only
  `control_agent_capability_filter.py` module.

## Validation

- AST equivalence checks for all graph classes and seven moved filter functions.
- Capability, rescue, entity-resolution and combined-level focused suites.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
