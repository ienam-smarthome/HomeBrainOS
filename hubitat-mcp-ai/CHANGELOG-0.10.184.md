# Hubitat MCP AI 0.10.184

## Deterministic active-room questions

- Answers “Which rooms are active based on motion or lights?” from the live cached
  dashboard snapshot.
- Avoids invoking the unified local Ollama planner for this exact dashboard-style
  read, eliminating the observed 25-second `qwen3.5:4b` timeout path.
- Returns active room names, counts and details with no model dependency.
- Leaves unrelated room questions and all controls on their existing routes.
