# Hubitat MCP AI 0.10.219

- Classifies every request as conversational, live-read, or write.
- Requires successful live MCP evidence before returning factual live-read answers.
- Treats tool discovery as discovery rather than proof.
- Retries one missing-evidence response with a generic tool-call correction, then
  refuses to invent a live answer.
- Returns sanitized evidence receipts in `/api/ask`, including tool, sub-tool,
  timestamp, latency, success, arguments, and a compact result summary.
- Keeps the existing plain-string agent method for API compatibility.
