# Hubitat MCP AI 0.10.285

## Changed

- Extracted conversation-history trimming and cumulative tool-result
  compaction from `UnifiedMCPAgent` into `ModelContextPolicy`.
- Preserved the existing agent constructor options and compatibility methods
  while making provider-payload budgeting independently testable.

## Safety

- Context budgeting operates only on copied provider messages.
- Authoritative conversation history, tool results, evidence receipts,
  confirmation state, and request control flow are never mutated by the policy.
- Older tool results continue to be compacted before newer results.

## Tests

- Added focused coverage for history message and character limits, role
  normalisation, immutable tool-content compaction, labelled excerpts, and
  sanitised configuration bounds.
