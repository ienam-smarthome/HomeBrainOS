# 0.9.6

- Fix targeted device resolution when the planner catalogue contains `homebrain_search_devices` but the model actually executes only `hub_list_devices`.
- Distinguish executed MCP tools from tools merely offered to the planner.
- Re-run named or described device lookups through the complete structured Hubitat inventory before accepting the answer.
- Add regression coverage for the exact production agent response shape.
