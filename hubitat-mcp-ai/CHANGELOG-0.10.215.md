# Hubitat MCP AI 0.10.215

- Executes routine light and switch commands without confirmation: on, off,
  toggle, level, colour, and colour temperature.
- Retains confirmation for locks, garage/door controls, destructive device
  operations, security actions, and hub administration.
- Adds one focused function-call retry when Ollama responds to a control request
  without emitting the required MCP call.
- Adds compact per-answer Read/Stop audio controls.
- Stops answer audio whenever the microphone starts, a new question is asked,
  or automatic read-aloud is disabled.
