# Hubitat MCP AI 0.10.246

## Hybrid device queries and clearer control choices

- Adds a high-level live device query tool for maximum, minimum, ranking, and
  count operations, including room grouping and socket-only power queries.
- Keeps routine light, switch, and socket controls deterministic and fast while
  allowing Ollama to turn computed analytical results into natural answers.
- Normalizes spacing, number words, and omitted device-kind words consistently
  for speech-derived device names.
- Returns structured ambiguity choices and renders them as clickable WebUI
  actions instead of leaving users to retype a candidate.
- Adds regression tests for highest room temperature, highest humidity, socket
  power ranking, and speech-derived target resolution.
