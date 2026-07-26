# Hubitat MCP AI 0.10.129

- Consolidated the maintained Ollama runtime into a substantially flatter inheritance chain.
- Moved adaptive cloud routing, final-answer enforcement, verified-evidence quality routing, and the natural answer pipeline into the unified agent.
- Retained the previous agent classes as compatibility implementations for existing imports and regression tests.
- Preserved local fallback, Ollama Cloud, MCP evidence recovery, final-answer sanitization, and planner routing behavior.
- Added architecture coverage for the reduced live runtime chain.
- Passed the complete 280-test blocking release gate.
