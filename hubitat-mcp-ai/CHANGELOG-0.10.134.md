# Hubitat MCP AI 0.10.134

## Deterministic climate extrema and semantic evidence fix

- Answers highest/lowest humidity and temperature questions from verified live measurements in Python.
- Prevents Ollama from inventing room names or unsupported sensor values.
- Ignores aggregate and invalid climate readings when selecting extrema.
- Fixes `NameError: environmental_insights is not defined` in semantic home evidence collection.
- Adds focused regression coverage for climate extrema selection.
