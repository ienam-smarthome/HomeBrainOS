# Hubitat MCP AI 0.10.243

## Canonical live state and whole-home snapshots

- Fixes deterministic filters that missed Hubitat attributes returned through
  list-shaped `currentStates` data.
- Introduces one canonical parser that merges `attributes`, `states`, and
  `currentStates`, with current live states taking precedence.
- Adds `homebrain_home_snapshot`, a high-level read tool that gathers presence,
  motion, active rooms, lights and switches on, open contacts, unlocked locks,
  low batteries, and health alerts from one internally consistent live read.
- Gives broad whole-home questions a complete deterministic answer instead of
  returning immediately after the first partial attribute filter.
- Adds regression coverage for mixed Hubitat state shapes and comprehensive
  whole-home summaries.
