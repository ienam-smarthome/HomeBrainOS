# Hubitat MCP AI 0.10.291

## Changed

- Wires the request-local `LiveEvidenceAuthority` into the maintained production
  agent without rewriting the established MCP tool loop.
- Uses a `ContextVar` to bind each production request to its own
  `EvidenceRecorder`, preserving isolation across concurrent requests.
- Keeps direct base-agent callers and historical tests on the original
  `GroundingPolicy` contract when no production recorder context is active.

## Safety

- Accept, retry, and refusal decisions now read the authoritative current
  request receipts directly instead of trusting a separately supplied boolean.
- Tool discovery still does not count as live evidence, and log questions still
  require a successful authoritative `hub_get_logs` call.

## Tests

- Adds production-wrapper coverage for authority selection, base-policy fallback,
  and protection against stale externally supplied evidence flags.
