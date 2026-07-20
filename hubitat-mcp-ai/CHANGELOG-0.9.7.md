# 0.9.7

- Apply the uploaded front-door routing patch.
- Recognise find, locate, where, show, check, look-up and look-for home queries.
- Expand MCP device-tool selection across doors, locks, rooms, appliances, climate, cameras and energy domains.
- Require authoritative live-home evidence for the expanded domain vocabulary.
- Repair explicit named-device lookups inside the unified MCP agent loop when a planner
  incorrectly selects the broad `hub_list_devices` inventory tool.
- Resolve requests such as `find front door` through the complete structured device index
  before generating the final response.
- Keep aggregate inventory and state questions on their intended tools instead of forcing
  every `hub_list_devices` call through targeted search.
