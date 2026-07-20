# 0.9.2

- Add `homebrain_search_devices`, a model-visible targeted search tool backed by the complete structured `hub_list_devices` MCP response.
- Rank candidates locally without truncating the device inventory.
- Return exact IDs, labels, rooms, capabilities, states and activity for relevant devices only.
- Direct the unified agent to use targeted device search before device reads or commands.
- Replace whole-inventory recovery with targeted MCP-backed recovery.
