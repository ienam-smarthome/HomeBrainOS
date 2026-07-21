# 0.10.6

- Makes the AI question guide a terminal system route outside every model-driven
  wrapper.
- Returns the existing grounded capability guide immediately for `What can Ollama
  help with?`, without invoking Ollama or Hubitat MCP.
- Prevents the 25-second local planner timeout and subsequent unified-agent error.
- Adds regression coverage proving the outer unified agent is bypassed.
