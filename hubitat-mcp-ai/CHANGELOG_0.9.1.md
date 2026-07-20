# 0.9.1

- Recover with an authoritative `hub_list_devices` read when the unified planner stops after MCP discovery or emits no usable data-bearing tool call.
- Keep transport, authentication and model failures explicit rather than masking them as inventory recovery.
- Add regression coverage for all recoverable planner-control exits.
