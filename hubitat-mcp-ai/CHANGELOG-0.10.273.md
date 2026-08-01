# Hubitat MCP AI 0.10.273

- Extracted the request-local evidence and log retry state machine into a
  focused `GroundingPolicy`.
- Preserved the existing one-retry limit and exact deterministic refusal
  responses for ungrounded live reads and inferred log summaries.
- Kept explicit log requests stricter than general live evidence: only a
  successful `hub_read_diagnostics` call using `hub_get_logs` satisfies them.
- Prevented unrelated live evidence, failed log calls, or tool discovery alone
  from satisfying the requested grounding requirement.
- Kept evidence authority, prompt interpretation, tool execution,
  confirmation, loop control, and successful-answer presentation outside the
  new policy.
- Preserved the existing orchestrator compatibility helper for exact live-log
  call detection.
- Added direct regression coverage for retry bounds, log priority, failed and
  unrelated diagnostic calls, conversational answers, successful evidence,
  and request isolation.
