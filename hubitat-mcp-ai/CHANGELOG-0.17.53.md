# Hubitat MCP AI 0.17.53 — proposal boundary and event evidence

## Changes
- Add a distinct semantic `propose` operation. A request to design a rule without
  changing Hubitat must not be interpreted as a request to perform a write.
- Reject entire model tool-call rounds containing write operations for a
  proposal-only plan, before confirmation, tool execution or rule authoring.
- Keep the original deterministic write guards; this is an additional
  opt-in safeguard, not a replacement for MCP permission checks.
- Treat device references inside observed event `producedBy` records as
  *mentioned evidence identities* for final claim matching. These mentions
  do not prove device health, a command origin or external automation cause.
- Add regression tests for proposal intent, blocked writes and event reporters.

## Rollout
`general_task_engine_enabled` remains **false** by default. Turn it on
only for supervised validation. The general typed evidence-completion engine
and broader tooling resilience work require subsequent staged changes.
