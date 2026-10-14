# Semantic evidence completion — v0.17.54

The planner supplies validated source classes rather than a flat imperative
to "be thorough". HomeBrain compares requirements against execution
receipts, not discovered gateway names or model-generated sentences.

## Source classes

`device_state`, `device_history`, `device_logs`, `app_config`,
`app_logs`, `room_inventory`, `native_rules`, `scheduled_jobs`,
`performance_stats`, and `tool_guide`.

A *checked* source means a successful corresponding bounded read. Even
a valid empty read does not establish that a rule fired or a device was
reachable. Reads for unrelated subjects may not establish the objective:
source completeness is a necessary but never sufficient condition.

## End-of-round decision

For an opt-in investigation with declared requirements:
1. Assess executed source-class receipts.
2. If missing and the bounded retry is unused, request one focused MCP
   continuation for those missing sources.
3. If still missing, preserve a partial answer plus a machine-independent
   source-gap note.
4. Never invent an operation, retry mutation, or claim that a source read
   establishes an execution event.

Specialised finalizers, complete claim-to-source verification, target-specific
identity binding and model-planner reliability are future work.
