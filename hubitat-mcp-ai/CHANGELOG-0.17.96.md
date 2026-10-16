# 0.17.96 — Scoped automation status and history coverage

- Named automation status requests specifying an app ID now bypass the whole-hub 152-item inventory and use the scoped agent.
- Corrects a bounded historical-source contradiction: a response claiming all event history only covers a recent date must acknowledge verified older command-event receipts supplied in the same turn.
- Older commands are NOT evidence for the requested focal action at a later time. No assertion of direct causation is introduced.
- Adds regression tests and preserves all write confirmation safeguards.

This release does **not** yet implement automated evidence-driven paid escalation; it remains a future, separately tested capability. Current model selection/budget remain unchanged. No Hubitat mutations.
