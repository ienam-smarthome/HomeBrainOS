# 0.10.199

- Removed the unreachable legacy routing, resolver, Ollama, and fallback module graph.
- Migrated Gemini function calling to the official `google-genai` asynchronous SDK.
- Added host-enforced, session-scoped confirmation for sensitive MCP operations.
- Replaced legacy tests with maintained endpoint, orchestration, confirmation, cache,
  transport, backend, and repository contract coverage.
- Updated the WebUI to report Gemini status and preserve a per-browser confirmation session.
