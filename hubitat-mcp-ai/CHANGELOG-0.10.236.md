# Hubitat MCP AI 0.10.236

- Reads the detailed Hub Info device after `updateCheck`, preserving installed
  and available firmware attributes omitted from compact device listings.
- Merges authoritative live state with cached device identity metadata for
  deterministic light, switch, and active-room summaries.
- Fixes disagreements between dashboard counts and agent answers when the live
  MCP response omits labels, rooms, or capability metadata.
- Adds regression coverage for compact live-state payloads.
