# Hubitat MCP AI 0.10.86

## Deferred Ollama startup and control-test normalization

- Deferred redundant legacy `ClaudeStyleOllamaAgent` construction during maintained startup.
- Preserved standalone `app.py` compatibility.
- Kept `UnifiedAdaptiveMCPAgent` as the final request-serving runtime agent.
- Added regression tests for deferred initialization and runtime agent wiring.
- Updated current control-routing tests to inspect `entrypoint_core.py`.
- Aligned control tests with the maintained rescue, combined-level, postfix, and fallback wiring.
- Made cloud control fallback assertions independent of global installer order.
- Updated the main changelog and Ollama Cloud setup script to the current release.
