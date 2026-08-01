# Hubitat MCP AI 0.10.267

- Limited prior conversation sent to Ollama to the eight newest messages and
  12,000 characters.
- Added a 48,000-character cumulative budget for retained multi-round tool
  results.
- Compacted the oldest tool results first while preserving newer results when
  the context budget is exceeded.
- Applied identical context limits to streaming and non-streaming requests.
- Kept the authoritative transcript and evidence receipts unchanged by
  compacting copied model-request messages only.
- Added regression coverage for history limits, result ordering, transport
  parity, and input immutability.
