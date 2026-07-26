# Hubitat MCP AI 0.10.146

## Removed

- Removed the superseded `ollama_agent_adaptive`,
  `ollama_agent_device_resolution`, `ollama_agent_final_answer`,
  `ollama_agent_natural`, `ollama_agent_quality` and
  `ollama_agent_resilient` modules.

## Changed

- Redirected historical regression coverage to the live consolidated class
  owners.
- Restored the intended static and class-method bindings for unified-agent
  evidence formatting, model routing and final-answer cleanup helpers.
- Updated repository validation and architecture documentation for the
  maintained `fast → inference → claude → unified` chain.

## Validation

- Import and cluster analysis.
- Repository layout validation.
- Python compilation.
- Blocking release gate.
