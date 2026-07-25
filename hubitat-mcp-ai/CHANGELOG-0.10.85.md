# Hubitat MCP AI 0.10.85

## Unified Ollama runtime wiring

- Added regression coverage proving that `UnifiedAdaptiveMCPAgent` is the final
  request-serving Ollama implementation.
- Documented the temporary legacy agent construction performed during startup.
- Removed stale validation references to the deleted orphan `ollama_agent.py`.
- Aligned release metadata and semantic-router wiring assertions.
- Preserved the existing Ollama inheritance chain pending behaviour-level
  consolidation tests.
