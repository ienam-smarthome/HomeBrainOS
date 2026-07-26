# Hubitat MCP AI 0.10.151

## Changed

- Consolidated control session and confirmation state, base control planning,
  verified level execution and rescue behavior in `control_agent_rescue.py`.
- Preserved the exact `HomeBrainControlAgent` → `FastVerifiedControlAgent` →
  `RescueControlAgent` method-resolution order.
- Retained the base, verified and final installation entrypoints under explicit
  names for structural regression coverage.
- Redirected focused control-agent tests to the live module owner.

## Removed

- Removed three superseded sibling-only modules: `control_agent_state.py`,
  `control_agent.py` and `control_agent_level_verified.py`.

## Validation

- AST equivalence checks for all ten moved classes and 60 class methods.
- Nine focused mutation, confirmation, rescue and verification suites.
- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
