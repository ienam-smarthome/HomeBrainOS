# Hubitat MCP AI 0.10.220

## Server-side cancellation and refusal safety

- Cancels the previous backend agent task when a newer request supersedes the same session.
- Detects client disconnects and cancels the in-flight Ollama and MCP await chain instead of leaving abandoned work running.
- Cancels remaining request tasks cleanly during add-on shutdown.
- Adds blocking regression tests for both evidence-retry and live-log retry refusal paths.
- Adds focused tests proving supersede and disconnect cancellation propagate to backend tasks.
- Removes the dead `tests/test_repository_hygiene.py` workflow path trigger and registers the new safety tests.
