# Hubitat MCP AI 0.10.271

- Extracted approved structured-call execution into a focused `ToolExecutor`.
- Unified local and remote dispatch, elapsed-time measurement, nested MCP
  success detection, failure capture, evidence emission, and bounded model
  payload construction.
- Routed resumed confirmed actions through the same execution path as ordinary
  model-selected calls.
- Removed duplicated try/except receipt logic and the possibility of reusing a
  stale start time after a later tool failure.
- Deep-copied structured arguments before dispatch so local handlers cannot
  mutate the caller's request or its audit snapshot.
- Kept tool visibility, confirmation approval, mutation reporting,
  live-evidence authority, retries, discovery expansion, and deterministic
  presentation in `UnifiedMCPAgent`.
- Added direct regression coverage for remote and local dispatch, failure
  receipts, nested failure envelopes, result bounding, argument isolation, and
  failed mutation metadata.
