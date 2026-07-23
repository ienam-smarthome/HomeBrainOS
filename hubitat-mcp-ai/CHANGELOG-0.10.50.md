# Hubitat MCP AI 0.10.50

- Adds deterministic matching for `software update`, `firmware update`,
  `platform update`, and natural Hubitat/hub variants.
- Prevents these destructive workflow requests from leaking into the AI planner.
- Keeps update status and explicit confirmation functional while Ollama is offline.
- Fixes the filename-safe backup workflow signature so forced creation reaches the
  confirmed backup implementation before a firmware update.
