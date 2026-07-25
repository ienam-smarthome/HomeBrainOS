# Hubitat MCP AI 0.10.84

## Architecture consolidation groundwork

- Added reproducible Python import-reachability analysis.
- Added module-family and fan-in analysis for consolidation planning.
- Added architecture documentation for the maintained MCP assistant.
- Added contribution rules to prevent `_safe`, `_final`, `_verified`, and
  similar patch-history module proliferation.
- Removed the confirmed unused legacy `ollama_agent.py` module.
- Added regression checks for consolidation tooling and release metadata.
- Preserved load-bearing Ollama, control-agent, automation-workflow, and
  fallback dependency chains pending behaviour-level tests.
