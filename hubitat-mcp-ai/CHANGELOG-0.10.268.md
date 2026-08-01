# Hubitat MCP AI 0.10.268

- Extracted Ollama HTTP and streaming behavior into a focused `ChatTransport`.
- Moved provider configuration, client ownership, native request construction,
  streamed chunk assembly, idle-stall detection, response validation, and
  shutdown out of `UnifiedMCPAgent`.
- Kept bounded-context preparation, tool execution, evidence, retries, and
  confirmation policy in the orchestrator.
- Preserved the existing agent status properties and stream timeout controls.
- Added direct transport tests alongside the existing end-to-end orchestrator
  and application integration coverage.
